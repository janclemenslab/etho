import time
import numpy as np
import subprocess
import defopt
from itertools import cycle
import os

from .. import config
from ..utils.zeroclient import ZeroClient
from ..utils.sound import parse_table, load_sounds, build_playlist
from ..utils.shuffled_cycle import shuffled_cycle
from ..utils.config import readconfig, saveconfig

from ..services.DAQZeroService import DAQ
from ..services.NITriggerZeroService import NIT
from ..services.GCMZeroService import GCM


def trigger(trigger_name):
    ip_address = "localhost"
    port = "/Dev1/port0/line1:3"
    trigger_types = {"START": [1, 0, 0], "STOP": [0, 1, 0], "NEXT": [0, 0, 1], "NULL": [0, 0, 0]}
    print([NIT.SERVICE_PORT, NIT.SERVICE_NAME])
    nit = ZeroClient("{0}".format(ip_address), "nidaq")
    try:
        sp = subprocess.Popen("python -m ethoservice.NITriggerZeroService")
        nit.connect("tcp://{0}:{1}".format(ip_address, NIT.SERVICE_PORT))
        print("done")
        nit.setup(-1, port)
        # nit.init_local_logger('{0}/{1}_nit.log'.format(dirname, filename))
        print("sending START")
        nit.send_trigger(trigger_types[trigger_name])
    except Exception as e:
        print(e)
    nit.finish()
    nit.stop_server()
    del nit
    sp.terminate()
    sp.kill()


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
    # load config/protocols
    print(filename)
    print(filecounter)
    print(protocolfile)
    print(playlistfile)
    print("save:", save)
    print("shuffle:", shuffle)
    print("loop:", loop)
    print("selected stim:", selected_stim)

    if os.path.splitext(protocolfile)[-1] not in [".yml", ".yaml"]:
        raise ValueError(
            "Protocol must be a yaml file (end in .yml or .yaml). Is "
            + protocolfile
            + " and ends in "
            + os.path.splitext(protocolfile)
            + "."
        )

    prot = readconfig(protocolfile)
    # maxduration = prot['NODE']['maxduration']
    fs = prot["DAQ"]["samplingrate"]
    SER = prot["NODE"]["serializer"]
    ip_address = "localhost"

    # load playlist, sounds, and enumerate play order
    playlist = parse_table(playlistfile)
    if selected_stim:
        playlist = playlist.iloc[selected_stim - 1 : selected_stim]
    print(playlist)
    sounds = load_sounds(
        playlist, fs, attenuation=config["ATTENUATION"], LEDamp=prot["DAQ"]["led_amp"], stimfolder=config["HEAD"]["stimfolder"]
    )
    sounds = [sound.astype(np.float64) for sound in sounds]
    maxduration = -1
    playlist_items, totallen = build_playlist(sounds, maxduration, fs, shuffle=shuffle)
    #
    nb_digital_chans_out = len(prot["DAQ"]["digital_chans_out"])
    nb_analog_chans_out = len(prot["DAQ"]["analog_chans_out"])

    # make START/NEXT/STOP triggers for scanimage
    triggers = list()
    for cnt, sound in enumerate(sounds):
        this_trigger = np.zeros((sound.shape[0], nb_digital_chans_out), dtype=np.uint8)
        # this_trigger[:20, 0] = 1  # add START trigger at BEGINNING of each sound (will be ignored if acquisition is already running)
        # if not loop and cnt == len(sounds) - 1:  # if we do not loop: add STOP trigger at end of last sound
        #     this_trigger[-20:-2, 1] = 1
        # this_trigger[-20:-2, 2] = 1  # add NEXT trigger at END of each sound,
        # # take the remaining digitial output channels [3:] from each sound as generated via the playlist
        for chn in range(3, nb_digital_chans_out):
            this_trigger[:, chn] = sound[:, nb_analog_chans_out + chn - 3]
        triggers.append(this_trigger.astype(np.uint8))  # cast digitial data to uint8
        # split off trailing digital channels from each sound
        sounds[cnt] = sound[:, :nb_analog_chans_out]

    if not loop:
        print(f"setting maxduration from playlist to {totallen}.")
        maxduration = totallen + 4
        playlist_items = iter(playlist_items)
    else:
        print(f"endless playback.")
        maxduration = -1
        if shuffle:
            playlist_items = shuffled_cycle(playlist_items, shuffle="block")
        else:
            playlist_items = cycle(playlist_items)  # iter(playlist_items)

    # SETUP CAM
    if "GCM" in prot["NODE"]["use_services"]:
        gcm_server_name = "python -m {0} {1}".format(GCM.__module__, SER)
        print([GCM.SERVICE_PORT, GCM.SERVICE_NAME])
        gcm = ZeroClient(ip_address, "gcmcam", serializer=SER)
        gcm_sp = subprocess.Popen(gcm_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
        gcm.connect("tcp://{0}:{1}".format(ip_address, GCM.SERVICE_PORT))
        print("done")
        cam_params = dict(prot["GCM"])
        gcm.setup(filename, -1, cam_params)
        gcm.init_local_logger("{0}_gcm.log".format(filename))

    # SETUP DAQ
    print([DAQ.SERVICE_PORT, DAQ.SERVICE_NAME])
    daq_server_name = "python -m {0} {1}".format(DAQ.__module__, SER)
    daq = ZeroClient(ip_address, "nidaq", serializer=SER)
    daq_sp = subprocess.Popen(daq_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)

    daq.connect("tcp://{0}:{1}".format(ip_address, DAQ.SERVICE_PORT))
    print("done")
    print("sending sound data to {0} - may take a while.".format(ip_address))
    if save:
        daq_save_filename = "{0}_daq.h5".format(filename)
    else:
        daq_save_filename = None
    print(daq_save_filename)
    daq.setup(
        daq_save_filename,
        playlist_items,
        playlist,
        maxduration,
        fs,
        prot["DAQ"]["display"],
        analog_chans_out=prot["DAQ"]["analog_chans_out"],
        analog_chans_in=prot["DAQ"]["analog_chans_in"],
        digital_chans_out=prot["DAQ"]["digital_chans_out"],
        analog_data_out=sounds,
        digital_data_out=triggers,
        metadata={"analog_chans_in_info": prot["DAQ"]["analog_chans_in_info"]},
    )
    if save:
        daq.init_local_logger("{0}_daq.log".format(filename))
        # dump protocol file as yaml
        saveconfig("{0}_prot.yml".format(filename), prot)

    # START PROCESSES
    if "GCM" in prot["NODE"]["use_services"]:
        gcm.start()
        time.sleep(3)  # give cam a headstart so we don't miss the beginning of the daq/ca recording
    daq.start()

    # MONITOR PROGRESS
    t0 = time.clock()
    while daq.is_busy(ai=True, ao=False):
        time.sleep(0.5)
        t1 = time.clock()
        print(f"   Busy {t1-t0:1.2f} seconds.\r", end="", flush=True)
    print(f"   Finished after {t1-t0:1.2f} seconds.")
    # send STOP trigger
    print(f"   DAQ finished after {t1-t0:1.2f} seconds")
    time.sleep(2)  # wait for daq process to free resources
    trigger("STOP")
    print("    sent STOP to scientifica")

    # STOP PROCESSES
    if "GCM" in prot["NODE"]["use_services"]:
        print("    terminate GCM process")
        gcm.finish(stop_service=True)


if __name__ == "__main__":
    defopt.run(client)
