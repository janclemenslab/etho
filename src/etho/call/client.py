import time
import numpy as np
import cv2
import logging
from itertools import cycle
from rich.progress import Progress
import rich
import threading
import _thread as thread
from typing import Optional, Union
import psutil
import threading
import signal
import os

from ..utils.tui import rich_information

from .. import config
from ..utils.config import readconfig, undefaultify
from ..utils.sound import parse_table, load_sounds, build_playlist

from ..services.ThuAZeroService import THUA
from ..services.DAQZeroService import DAQ
from ..services.GCMZeroService import GCM
from ..services.NICounterZeroService import NIC


def timed(fn, s, *args, **kwargs):
    quit_fun = thread.interrupt_main  # raises KeyboardInterrupt
    timer = threading.Timer(s, quit_fun)
    timer.start()
    try:
        result = fn(*args, **kwargs)
    except:  # catch KeyboardInterrupt for silent timeouts
        result = 1
    finally:
        timer.cancel()
    return result


def kill_child_processes():
    try:
        parent = psutil.Process()
    except psutil.NoSuchProcess:
        return
    children = parent.children(recursive=True)
    for child in children:
        child.terminate()  # friendly termination
    _, still_alive = psutil.wait_procs(children, timeout=3)
    for child in still_alive:
        child.kill()  # unfriendly termination
        # os.kill(child.pid, signal.SIGKILL)


def client(
    protocolfile: str,
    playlistfile: Optional[str] = None,
    *,
    host: str = "localhost",
    save_prefix: Optional[str] = None,
    show_test_image: bool = False,
    show_progress: bool = True,
    debug: bool = False,
    preview: bool = False,
    gui: bool = False,
    _stop_event: Optional[threading.Event] = None,
):
    """Starts an experiment.

    Args:
        host (str): _description_
        protocolfile (str): _description_
        playlistfile (Optional[str]): _description_.
        save_prefix (Optional[str]): _description_.
        show_test_image (bool): _description_.
        show_progress (bool): _description_.
        debug (bool): _description_.
        preview (bool): _description_.
        gui (bool): _description_.
        _stop_event (threading.Event): _description_.

    """

    # load config/protocols
    prot = readconfig(protocolfile)
    logging.debug(prot)

    defaults = config["GENERAL"]
    defaults.update(prot["NODE"])
    defaults["host"] = host

    if defaults['python_exe'] is None:
        defaults['python_exe'] = 'python'
    if defaults['serializer'] is None:
        defaults['serializer'] = 'pickle'

    rich.print(defaults)
    # unique file name for video and node-local logs
    if save_prefix is None:
        save_prefix = f"{defaults['host']}-{time.strftime('%Y%m%d_%H%M%S')}"
    logging.info(f"Saving as {save_prefix}.")

    new_console = debug

    services = {}
    if "THUA" in prot["NODE"]["use_services"] and not preview:
        this = defaults.copy()
        # update `this`` with service specific host params
        if "host" in prot["THUA"]:
            this.update(prot["THUA"]["host"])
        thua = THUA.make(this["serializer"], this["user"], this["host"], this["working_directory"], this["python_exe"])
        thua.setup(prot["THUA"]["port"], prot["THUA"]["interval"], this["maxduration"] + 10)
        thua.init_local_logger("{0}/{1}/{1}_thu.log".format(this["save_directory"], save_prefix))
        thua.start()
        services["THUA"] = thua

    gcm_keys = [key for key in prot["NODE"]["use_services"] if "GCM" in key]
    for gcm_cnt, gcm_key in enumerate(gcm_keys):
        # if gcm_key in prot["NODE"]["use_services"] and gcm_key in prot:
        this = defaults.copy()
        # update `this` with service specific host params
        host_is_remote = False
        if "host" in prot[gcm_key]:
            this.update(prot[gcm_key]["host"])
            host_is_remote = True

        if "port" not in prot[gcm_key]:
            prot[gcm_key]["port"] = GCM.SERVICE_PORT + gcm_cnt

        gcm = GCM.make(
            this["serializer"],
            this["user"],
            this["host"],
            this["working_directory"],
            this["python_exe"],
            host_is_remote=host_is_remote,
            new_console=new_console,
            port=prot[gcm_key]["port"],
        )

        cam_params = undefaultify(prot[gcm_key])
        if not preview:
            maxduration = this["maxduration"] + 20
        else:
            maxduration = 1_000_000

        if preview:
            cam_params["callbacks"] = {"disp_fast": None}

        save_suffix = f"_{gcm_cnt+1}" if gcm_cnt > 0 else ""
        gcm.setup(f"{this['save_directory']}/{save_prefix}/{save_prefix}{save_suffix}", maxduration, cam_params)

        if not preview:
            gcm.init_local_logger(f"{this['save_directory']}/{save_prefix}/{save_prefix}{save_suffix}_gcm.log")
        if show_test_image:
            img = gcm.attr("test_image")
            print("Press any key to continue.")
            cv2.imshow("Test image. Are you okay with this? Press any key to continue", img)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            cv2.waitKey(1)  # second call required for window to be closed on mac
        services[gcm_key] = gcm

    daq_keys = [key for key in prot["NODE"]["use_services"] if "DAQ" in key]
    daq_keys = [] if preview else daq_keys
    for daq_cnt, daq_key in enumerate(daq_keys):
        # if "DAQ2" in prot["NODE"]["use_services"]:
        this = defaults.copy()
        # update `this`` with service specific host params
        # if "GCM" in prot and "host" in prot["GCM"]:
        #     this.update(prot["GCM"]["host"])

        if "device" not in prot[daq_key]:
            prot[daq_key]["device"] = "Dev1"

        if "port" not in prot[daq_key]:
            prot[daq_key]["port"] = DAQ.SERVICE_PORT + daq_cnt

        if this["host"] in config["ATTENUATION"]:  # use node specific attenuation data
            attenuation = config["ATTENUATION"][this["host"]]
            logging.info(f"Using attenuation data specific to {this['host']}.")
        else:
            attenuation = config["ATTENUATION"]

        # Load/generate all stimuli specified in playlist
        fs = prot[daq_key]["samplingrate"]
        playlist = parse_table(playlistfile)
        sounds = load_sounds(
            playlist, fs, attenuation=attenuation, LEDamp=prot[daq_key]["ledamp"], stimfolder=config["HEAD"]["stimfolder"]
        )
        sounds = [sound.astype(np.float64) for sound in sounds]

        # Generate stimulus sequence (shuffle, loop playlist)
        playlist_items, totallen = build_playlist(sounds, this["maxduration"], fs, shuffle=prot[daq_key]["shuffle"])
        if this["maxduration"] == -1:
            logging.info(f"Setting maxduration from playlist to {totallen}.")
            this["maxduration"] = totallen
            playlist_items = cycle(playlist_items)  # iter(playlist_items)
        else:
            playlist_items = cycle(playlist_items)

        # split analog and digital outputs
        # TODO: catch errors if channel numbers are inconsistent - sounds[ii].shape[-1] should be nb_analog+nb_digital
        if prot[daq_key]["digital_chans_out"] is not None:
            nb_digital_chans_out = len(prot[daq_key]["digital_chans_out"])
            digital_data = [snd[:, -nb_digital_chans_out:].astype(np.uint8) for snd in sounds]
            analog_data = [snd[:, :-nb_digital_chans_out] for snd in sounds]  # remove digital traces from stimset
        else:
            digital_data = None
            analog_data = sounds

        daq = DAQ.make(
            this["serializer"],
            this["user"],
            this["host"],
            this["working_directory"],
            this["python_exe"],
            new_console=new_console,
            port=prot[daq_key]["port"],
        )

        save_suffix = f"_{daq_cnt+1}" if daq_cnt > 0 else ""
        daq.setup(
            f"{this['save_directory']}/{save_prefix}/{save_prefix}{save_suffix}",
            playlist_items,
            playlist,
            this["maxduration"],
            fs,
            dev_name=prot[daq_key]["device"],
            clock_source=prot[daq_key]["clock_source"],
            nb_inputsamples_per_cycle=prot[daq_key]["nb_inputsamples_per_cycle"],
            analog_chans_out=prot[daq_key]["analog_chans_out"],
            analog_chans_in=prot[daq_key]["analog_chans_in"],
            digital_chans_out=prot[daq_key]["digital_chans_out"],
            analog_data_out=analog_data,
            digital_data_out=digital_data,
            metadata={"analog_chans_in_info": prot[daq_key]["analog_chans_in_info"]},
            params=undefaultify(prot[daq_key]),
        )
        daq.init_local_logger(f"{this['save_directory']}/{save_prefix}/{save_prefix}{save_suffix}_daq.log")
        services[daq_key] = daq

    if "NIC" in prot["NODE"]["use_services"]:
        this = defaults.copy()
        # update `this`` with service specific host params
        if "host" in prot["NIC"]:
            this.update(prot["NIC"]["host"])

        nic = NIC.make(
            this["serializer"],
            this["user"],
            this["host"],
            this["working_directory"],
            this["python_exe"],
            new_console=new_console,
            port=prot[daq_key]["port"],
        )

        nic_params = undefaultify(prot["NIC"])
        nic.setup(
            nic_params["output_channel"],
            this["maxduration"] + 10,
            nic_params["frequency"],
            nic_params["duty_cycle"],
            nic_params,
        )
        nic.init_local_logger(f"{this['save_directory']}/{save_prefix}/{save_prefix}{save_suffix}_daq.log")

    # display config info
    for key, s in services.items():
        rich_information(s.information(), prefix=key)

    logging.info("Starting services")
    # First, start video services - this will start acquisition or, if external triggering is enabled, arm the cameras to wait for the triggers
    time_last_cam_started = time.time() + 5  # in case no cam was initialized
    for service_name, service in services.items():
        if "GCM" in service_name:
            logging.info(f"   {service_name}.")
            service.start()
            time_last_cam_started = time.time()
    time.sleep(0.5)

    # start the counter task for triggering frames
    if "NIC" in prot["NODE"]["use_services"]:
        logging.info("   NI Counter service.")
        nic.start()
        time_last_cam_started = time.time()

    # Wait 5 seconds for cams to run
    if daq_keys:
        while time.time() - time_last_cam_started < 5:
            time.sleep(0.1)

    # Start DAQ services
    for service_name, service in services.items():
        if "DAQ" in service_name:
            logging.info(f"   {service_name}.")
            service.start()

    logging.info("All services started.")
    if show_progress:
        cli_progress(services, save_prefix, _stop_event)
    else:
        return services


def cli_progress(services, save_prefix, stop_event=None):
    with Progress() as progress:
        tasks = {}
        for service_name, service in services.items():
            tasks[service_name] = progress.add_task(f"[red]{service_name}", total=service.progress()["total"])
        RUN = True
        while RUN and not progress.finished:
            for task_name, task_id in tasks.items():
                if progress._tasks[task_id].finished:
                    continue
                try:
                    p = timed(services[task_name].progress, 5)
                    description = None
                    if "framenumber" in p:
                        description = f"{task_name} {p['framenumber_delta'] / p['elapsed_delta']: 7.2f} fps"
                    progress.update(task_id, completed=p["elapsed"], description=description)
                except:  # if call times out, stop progress display - this will stop the display whenever a task times out - not necessarily when a task is done
                    progress.stop_task(task_id)
            time.sleep(1)

            if stop_event is not None and stop_event.is_set():
                print("STOP!")
                logging.info("Cancelling jobs:")
                for task_name, task_id in tasks.items():
                    progress.stop_task(task_id)
                RUN = False
                time.sleep(1)
                for service_name, service in services.items():
                    try:
                        logging.info(f"   {service_name}")
                        service.finish()
                    except:
                        logging.warning("     Failed.")

    logging.info("Terminating jobs.")
    kill_child_processes()
    logging.info("Done")

    logging.info(f"Done with experiment {save_prefix}.")
