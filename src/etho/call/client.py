import time
import numpy as np
import cv2
import logging
from itertools import cycle
from rich.progress import Progress
import rich
from ..utils.tui import rich_information

from .. import config
from ..utils.config import readconfig, undefaultify
from ..utils.sound import parse_table, load_sounds, build_playlist

from ..services.ThuAZeroService import THUA
from ..services.DAQZeroService import DAQ
from ..services.GCMZeroService import GCM


import threading
import _thread as thread
import defopt
from typing import Optional


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


def client(
    host: str,
    protocolfile: str,
    playlistfile: Optional[str] = None,
    *,
    save_prefix: Optional[str] = None,
    show_test_image: bool = False,
    show_progress: bool = True,
    debug: bool = False,
):
    """_summary_

    Args:
        host (str): _description_
        protocolfile (str): _description_
        playlistfile (Optional[str]): _description_.
        save_prefix (Optional[str]): _description_.
        show_test_image (bool): _description_.
        show_progress (bool): _description_.
        debug (bool): desc
    """
    # load config/protocols
    prot = readconfig(protocolfile)
    logging.debug(prot)

    defaults = config["GENERAL"]
    defaults.update(prot["NODE"])
    defaults["host"] = host
    rich.print(defaults)
    # unique file name for video and node-local logs
    if save_prefix is None:
        save_prefix = f"{defaults['host']}-{time.strftime('%Y%m%d_%H%M%S')}"
    logging.info(f"Saving as {save_prefix}.")

    new_console = debug

    services = {}
    if "THUA" in prot["NODE"]["use_services"]:
        this = defaults.copy()
        # update `this`` with service specific host params
        if "host" in prot["THUA"]:
            this.update(prot["THUA"]["host"])
        thua = THUA.make(this["serializer"], this["user"], this["host"], this["working_directory"], this["python_exe"])
        thua.setup(prot["THUA"]["port"], prot["THUA"]["interval"], this["maxduration"] + 10)
        thua.init_local_logger("{0}/{1}/{1}_thu.log".format(this["save_directory"], save_prefix))
        thua.start()
        services["THUA"] = thua

    if "GCM" in prot["NODE"]["use_services"] and "GCM" in prot:
        this = defaults.copy()
        # update `this` with service specific host params
        host_is_remote = False
        if "host" in prot["GCM"]:
            this.update(prot["GCM"]["host"])
            host_is_remote = True
        gcm = GCM.make(
            this["serializer"],
            this["user"],
            this["host"],
            this["working_directory"],
            this["python_exe"],
            host_is_remote=host_is_remote,
            new_console=new_console,
        )
        cam_params = undefaultify(prot["GCM"])
        gcm.setup(f"{this['save_directory']}/{save_prefix}/{save_prefix}", this["maxduration"] + 20, cam_params)
        gcm.init_local_logger("{0}/{1}/{1}_gcm.log".format(this["save_directory"], save_prefix))
        if show_test_image:
            img = gcm.attr("test_image")
            print("Press any key to continue.")
            cv2.imshow("Test image. Are you okay with this?", img)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            cv2.waitKey(1)  # second call required for window to be closed on mac
        gcm.start()
        services["camera"] = gcm

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

        save_suffix = f"_{gcm_cnt+1}" if gcm_cnt > 0 else ""
        gcm.setup(
            f"{this['save_directory']}/{save_prefix}/{save_prefix}{save_suffix}",
            this["maxduration"] + 20,
            undefaultify(prot[gcm_key]),
        )
        gcm.init_local_logger(f"{this['save_directory']}/{save_prefix}{save_suffix}/{save_prefix}{save_suffix}_gcm.log")
        if show_test_image:
            img = gcm.attr("test_image")
            print("Press any key to continue.")
            cv2.imshow("Test image. Are you okay with this?", img)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            cv2.waitKey(1)  # second call required for window to be closed on mac
        # gcm.start()
        services[gcm_key] = gcm

    # if "DAQ" in prot["NODE"]["use_services"]:
    #     this = defaults.copy()
    #     # update `this`` with service specific host params
    #     if "GCM" in prot and "host" in prot["GCM"]:
    #         this.update(prot["GCM"]["host"])

    #     fs = prot["DAQ"]["samplingrate"]
    #     playlist = parse_table(playlistfile)

    #     if this["host"] in config["ATTENUATION"]:  # use node specific attenuation data
    #         attenuation = config["ATTENUATION"][this["host"]]
    #         logging.info(f"Using attenuation data specific to {this['host']}.")
    #     else:
    #         attenuation = config["ATTENUATION"]

    #     sounds = load_sounds(
    #         playlist, fs, attenuation=attenuation, LEDamp=prot["DAQ"]["ledamp"], stimfolder=config["HEAD"]["stimfolder"]
    #     )
    #     sounds = [sound.astype(np.float64) for sound in sounds]
    #     playlist_items, totallen = build_playlist(sounds, this["maxduration"], fs, shuffle=prot["DAQ"]["shuffle"])
    #     if this["maxduration"] == -1:
    #         logging.info(f"Setting maxduration from playlist to {totallen}.")
    #         this["maxduration"] = totallen
    #         playlist_items = cycle(playlist_items)  # iter(playlist_items)
    #     else:
    #         playlist_items = cycle(playlist_items)
    #     # TODO: catch errors if channel numbers are inconsistent - sounds[ii].shape[-1] should be nb_analog+nb_digital
    #     if prot["DAQ"]["digital_chans_out"] is not None:
    #         nb_digital_chans_out = len(prot["DAQ"]["digital_chans_out"])
    #         digital_data = [snd[:, -nb_digital_chans_out:].astype(np.uint8) for snd in sounds]
    #         analog_data = [snd[:, :-nb_digital_chans_out] for snd in sounds]  # remove digital traces from stimset
    #     else:
    #         digital_data = None
    #         analog_data = sounds

    #     if 'device' not in prot['DAQ']:
    #         prot['DAQ']['device'] = 'Dev1'

    #     daq = DAQ.make(this["serializer"], this["user"], this["host"], this["working_directory"], this["python_exe"], new_console=new_console)

    #     daq_params = undefaultify(prot["DAQ"])
    #     daq.setup(
    #         "{0}/{1}/{1}".format(this["save_directory"], save_prefix),
    #         playlist_items,
    #         playlist,
    #         this["maxduration"],
    #         fs,
    #         dev_name=prot['DAQ']['device'],
    #         clock_source=prot["DAQ"]["clock_source"],
    #         nb_inputsamples_per_cycle=prot["DAQ"]["nb_inputsamples_per_cycle"],
    #         analog_chans_out=prot["DAQ"]["analog_chans_out"],
    #         analog_chans_in=prot["DAQ"]["analog_chans_in"],
    #         digital_chans_out=prot["DAQ"]["digital_chans_out"],
    #         analog_data_out=analog_data,
    #         digital_data_out=digital_data,
    #         metadata={"analog_chans_in_info": prot["DAQ"]["analog_chans_in_info"]},
    #         params=daq_params,
    #     )
    #     daq.init_local_logger(f"{this['save_directory']}/{save_prefix}/{save_prefix}_daq.log")

    #     if "gcm" in services:
    #         while services["gcm"].progress()["elapsed"] < 5:
    #             time.sleep(0.1)
    #             print(f"\rWaiting for camera {services['gcm'].progress()['elapsed']: 2.1f}/5.0 seconds", end="", flush=True)
    #         print("\n")

    #     services["daq"] = daq

    daq_keys = [key for key in prot["NODE"]["use_services"] if "DAQ" in key]
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
            dev_name=prot["DAQ2"]["device"],
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

    # if "DAQ1" in prot["NODE"]["use_services"]:
    #     this = defaults.copy()
    #     # update `this`` with service specific host params
    #     if "GCM" in prot and "host" in prot["GCM"]:
    #         this.update(prot["GCM"]["host"])

    #     fs = prot["DAQ1"]["samplingrate"]
    #     playlist = parse_table(playlistfile)

    #     if this["host"] in config["ATTENUATION"]:  # use node specific attenuation data
    #         attenuation = config["ATTENUATION"][this["host"]]
    #         logging.info(f"Using attenuation data specific to {this['host']}.")
    #     else:
    #         attenuation = config["ATTENUATION"]

    #     sounds = load_sounds(
    #         playlist, fs, attenuation=attenuation, LEDamp=prot["DAQ1"]["ledamp"], stimfolder=config["HEAD"]["stimfolder"]
    #     )
    #     sounds = [sound.astype(np.float64) for sound in sounds]
    #     playlist_items, totallen = build_playlist(sounds, this["maxduration"], fs, shuffle=prot["DAQ1"]["shuffle"])
    #     if this["maxduration"] == -1:
    #         logging.info(f"Setting maxduration from playlist to {totallen}.")
    #         this["maxduration"] = totallen
    #         playlist_items = cycle(playlist_items)  # iter(playlist_items)
    #     else:
    #         playlist_items = cycle(playlist_items)
    #     # TODO: catch errors if channel numbers are inconsistent - sounds[ii].shape[-1] should be nb_analog+nb_digital
    #     if prot["DAQ1"]["digital_chans_out"] is not None:
    #         nb_digital_chans_out = len(prot["DAQ1"]["digital_chans_out"])
    #         digital_data = [snd[:, -nb_digital_chans_out:].astype(np.uint8) for snd in sounds]
    #         analog_data = [snd[:, :-nb_digital_chans_out] for snd in sounds]  # remove digital traces from stimset
    #     else:
    #         digital_data = None
    #         analog_data = sounds

    #     if 'device' not in prot['DAQ1']:
    #         prot['DAQ1']['device'] = 'Dev1'

    #     daq1 = DAQ.make(this["serializer"], this["user"], this["host"], this["working_directory"], this["python_exe"], new_console=new_console, port=DAQ.SERVICE_PORT+1)

    #     daq_params = undefaultify(prot["DAQ1"])
    #     daq1.setup(
    #         "{0}/{1}/{1}_1".format(this["save_directory"], save_prefix),
    #         playlist_items,
    #         playlist,
    #         this["maxduration"],
    #         fs,
    #         dev_name=prot['DAQ1']['device'],
    #         clock_source=prot["DAQ1"]["clock_source"],
    #         nb_inputsamples_per_cycle=prot["DAQ1"]["nb_inputsamples_per_cycle"],
    #         analog_chans_out=prot["DAQ1"]["analog_chans_out"],
    #         analog_chans_in=prot["DAQ1"]["analog_chans_in"],
    #         digital_chans_out=prot["DAQ1"]["digital_chans_out"],
    #         analog_data_out=analog_data,
    #         digital_data_out=digital_data,
    #         metadata={"analog_chans_in_info": prot["DAQ1"]["analog_chans_in_info"]},
    #         params=daq_params,
    #     )
    #     daq1.init_local_logger(f"{this['save_directory']}/{save_prefix}/{save_prefix}_1_daq.log")

    #     services["daq1"] = daq1

    # First, start video services
    for service_name, service in services.items():
        if "GCM" in service_name:
            logging.info(f"starting {service_name}.")
            service.start()
    time_last_cam_started = time.time()

    # if "gcm" in services:
    #     while services["gcm"].progress()["elapsed"] < 5:
    #         time.sleep(0.1)
    #         print(f"\rWaiting for camera {services['gcm'].progress()['elapsed']: 2.1f}/5.0 seconds", end="", flush=True)
    #     print("\n")

    # Wait 5 seconds for cams to run
    while time.time() - time_last_cam_started < 5:
        time.sleep(0.1)

    # Start DAQ services
    for service_name, service in services.items():
        if "DAQ" in service_name:
            logging.info(f"starting {service_name}.")
            service.start()

    # for key, val in services.items():
    #     if 'daq' in key:
    #         logging.info(f"starting {key}.")
    #         val.start()

    # display config info
    for key, s in services.items():
        rich_information(s.information(), prefix=key)

    if show_progress:
        with Progress() as progress:
            tasks = {}
            for service_name, service in services.items():
                tasks[service_name] = progress.add_task(f"[red]{service_name}", total=service.progress()["total"])

            while not progress.finished:
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
        logging.info(f"Done with experiment {save_prefix}.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    defopt.run(client)
