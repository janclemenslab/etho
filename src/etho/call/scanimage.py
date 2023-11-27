import time
import numpy as np
import subprocess
import defopt
import logging
from itertools import cycle
import os
import cv2
# from rich.progress import Progress
import rich
from typing import Optional

# from ..utils.tui import rich_information
from .. import config
from ..utils.sound import parse_table, load_sounds, build_playlist
from ..utils.shuffled_cycle import shuffled_cycle
from ..utils.config import readconfig, saveconfig, undefaultify

from ..services.DAQZeroService import DAQ
from ..services.NITriggerZeroService import oneshot_trigger
from ..services.GCMZeroService import GCM


def client(
    filename: str,
    filecounter: int,
    protocolfile: str,
    playlistfile: str,
    save: bool = False,
    shuffle: bool = False,
    loop: bool = False,
    selected_stim: int = None,
):
    args = locals()  # input save args

    # load config/protocols
    prot = readconfig(protocolfile)
    defaults = config["GENERAL"]
    defaults.update(prot["NODE"])
    defaults["host"] = 'localhost'
    defaults['args'] = args
    new_console=True
    services = {}
    rich.print(defaults)

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
            cv2.imshow("Test image. Are you okay with this?", img)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            cv2.waitKey(1)  # second call required for window to be closed on mac
        services[gcm_key] = gcm

    daq_keys = [key for key in prot["NODE"]["use_services"] if "DAQ" in key]
    for daq_cnt, daq_key in enumerate(daq_keys):
        this = defaults.copy()

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
        if selected_stim:
            playlist = playlist.iloc[selected_stim - 1:selected_stim]
        rich.print(playlist)

        sounds = load_sounds(
            playlist, fs, attenuation=attenuation, LEDamp=prot[daq_key]["ledamp"], stimfolder=config["HEAD"]["stimfolder"],
            ignore_stop=shuffle or loop,
        )
        sounds = [sound.astype(np.float64) for sound in sounds]

        # Generate stimulus sequence (shuffle, loop playlist)
        playlist_items, totallen = build_playlist(sounds, this["maxduration"], fs, shuffle=shuffle)
        if not loop:
            logging.info(f"Setting maxduration from playlist to {totallen}.")
            this["maxduration"] = totallen
            # even though we do not want to loop need to use `cycle`` here
            # so daq continues until the end and scanimage receives the last NEXT and STOP triggers
            playlist_items = cycle(playlist_items)
        else:
            this["maxduration"] = -1
            if shuffle:
                playlist_items = shuffled_cycle(playlist_items)
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

        if save:
            daq_save_filename = filename
        else:
            daq_save_filename = None
            keys = list(prot[daq_key]['callbacks'].keys())
            for key in keys:
                if 'save' in key.lower():
                    del prot[daq_key]['callbacks'][key]

        daq.setup(
            daq_save_filename,
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
        daq.init_local_logger(f"{filename}_daq.log")
        services[daq_key] = daq

    if save:
        daq.init_local_logger("{0}_daq.log".format(filename))
        # dump protocol file as yaml
        saveconfig("{0}_prot.yml".format(filename), prot)

    daq.start()

    # MONITOR PROGRESS
    t0 = time.clock()
    while daq.is_busy(ai=True, ao=False):
        time.sleep(1.0)
        t1 = time.clock()
        # print(f"   Busy {t1-t0:1.2f} seconds.\r", end="", flush=True)

    logging.info(f"   Finished after {t1-t0:1.2f} seconds.")
    daq.close()
    # send STOP trigger
    time.sleep(4)  # wait for daq process to free resources
    oneshot_trigger(this,["NEXT", "STOP"])
    logging.info("   ScanImage stopped")
    time.sleep(4)  # wait for daq process to free resources
    os.system('taskkill /IM python.exe /F')


if __name__ == "__main__":
    defopt.run(client)
