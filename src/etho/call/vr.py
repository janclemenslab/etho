import time
import numpy as np
import pandas as pd
import os
import subprocess
import logging
from itertools import cycle
from pprint import pprint
import shutil

from .. import config
from ..utils.zeroclient import ZeroClient
from ..utils.config import readconfig, undefaultify
from ..utils.sound import parse_table, load_sounds, build_playlist

from ..services.DAQZeroService import DAQ
from ..services.GCMZeroService import GCM
from ..services.BLTZeroService import BLT
from ..services.DLPZeroService import DLP


def clientcaller(ip_address, playlistfile, protocolfile, filename=None):
    # load config/protocols
    pprint(config)
    prot = readconfig(os.path.join(config["HEAD"]["protocolfolder"], protocolfile))
    pprint(undefaultify(prot))
    maxduration = prot["NODE"]["maxduration"]
    user_name = prot["NODE"]["user"]
    folder_name = prot["NODE"]["folder"]
    SER = prot["NODE"]["serializer"]
    python_exe = config["GENERAL"]["python_exe"]
    # unique file name for video and node-local logs
    if filename is None:
        filename = "{0}-{1}".format(ip_address, time.strftime("%Y%m%d_%H%M%S"))
    dirname = prot["NODE"]["savefolder"]
    os.makedirs(f"{dirname}/{filename}", exist_ok=True)

    shutil.copy2(
        os.path.join(config["HEAD"]["protocolfolder"], protocolfile), f"{dirname}/{filename}/{os.path.basename(protocolfile)}"
    )

    if "DLP" in prot["NODE"]["use_services"]:
        dlp_save_filename = "{0}/{1}/{1}".format(dirname, filename)
        dlp = DLP.make(SER, user_name, ip_address, folder_name, python_exe)
        dlp_params = undefaultify(prot["DLP"])
        dlp.setup(maxduration + 10, dlp_save_filename, params=dlp_params)
        dlp.init_local_logger("{0}/{1}/{1}_dlp.log".format(dirname, filename))
        if "ObjectMoverSizer" in prot["DLP"]["runners"].keys():
            shutil.copy2(
                prot["DLP"]["runners"]["ObjectMoverSizer"]["filename"], f"{dirname}/{filename}/{filename}_movieparams.npz"
            )

    if "SPN" in prot["NODE"]["use_services"]:
        ptg = GCM.make(SER, user_name, ip_address, folder_name, python_exe)
        cam_params = undefaultify(prot["SPN"])
        ptg.setup("{0}/{1}/{1}_ball".format(dirname, filename), maxduration + 10, cam_params)
        ptg.init_local_logger("{0}/{1}/{1}_ball_spn.log".format(dirname, filename))
        ptg.start()
        # time.sleep(5)

    if "BLT" in prot["NODE"]["use_services"]:
        blt = BLT.make(SER, user_name, ip_address, folder_name, python_exe)
        blt_params = undefaultify(prot["BLT"])
        blt.setup("{0}/{1}/{1}".format(dirname, filename), maxduration + 10, blt_params)
        blt.init_local_logger("{0}/{1}/{1}_blt.log".format(dirname, filename))
        blt.start()

    # if 'SPN2' in prot['NODE']['use_services']:
    #     ptg2 = GCM.make(SER, user_name, ip_address, folder_name, python_exe, port=4247)
    #     cam_params = undefaultify(prot['SPN2'])
    #     ptg2.setup('{0}/{1}/{1}_2'.format(dirname, filename), maxduration + 10, cam_params)
    #     ptg2.init_local_logger('{0}/{1}/{1}_spn2.log'.format(dirname, filename))
    #     ptg2.start()

    # if 'SPN' in prot['NODE']['use_services']:
    #     ptg_server_name = f'{python_exe} -m {GCM.__module__} {SER}'
    #     print([GCM.SERVICE_PORT, GCM.SERVICE_NAME])
    #     ptg = ZeroClient("{0}@{1}".format(user_name, ip_address), 'spn', serializer=SER)
    #     subprocess.Popen(ptg_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
    #     ptg.connect("tcp://{0}:{1}".format(ip_address, GCM.SERVICE_PORT))
    #     print('done')
    #     cam_params = undefaultify(prot['SPN'])
    #     ptg.setup('{0}/{1}/{1}'.format(dirname, filename), maxduration + 10, cam_params)
    #     ptg.init_local_logger('{0}/{1}/{1}_spn.log'.format(dirname, filename))
    #     ptg.start()
    #     # services.append(ptg)

    if "SPN2" in prot["NODE"]["use_services"]:
        port = 4247  # 4247  # use custom port so we can start two SPN instances
        ptg_server_name = f"{python_exe} -m {GCM.__module__} {SER} {port}"
        print([port, GCM.SERVICE_NAME])
        ptg2 = ZeroClient("{0}@{1}".format(user_name, ip_address), "spnzoom", serializer=SER)
        subprocess.Popen(ptg_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
        ptg2.connect("tcp://{0}:{1}".format(ip_address, port))
        print("done")
        cam_params = undefaultify(prot["SPN2"])
        print(cam_params)
        ptg2.setup("{0}/{1}/{1}".format(dirname, filename), maxduration + 10, cam_params)
        ptg2.init_local_logger("{0}/{1}/{1}_spn.log".format(dirname, filename))
        ptg2.start()
        # services.append(ptg2)

    if "DAQ" in prot["NODE"]["use_services"]:
        if prot["DAQ"]["run_locally"]:
            print("   Running DAQ job locally.")
            ip_address = "localhost"
            daq_save_folder = "C:/Users/ncb/data"
        else:
            daq_save_folder = dirname
        fs = prot["DAQ"]["samplingrate"]
        shuffle_playback = prot["DAQ"]["shuffle"]

        playlist = parse_table(playlistfile)

        if ip_address in config["ATTENUATION"]:  # use node specific attenuation data
            attenuation = config["ATTENUATION"][ip_address]
            print(f"using attenuation data specific to {ip_address}.")
        else:
            attenuation = config["ATTENUATION"]

        sounds = load_sounds(
            playlist, fs, attenuation=attenuation, LEDamp=prot["DAQ"]["ledamp"], stimfolder=config["HEAD"]["stimfolder"]
        )
        sounds = [sound.astype(np.float64) for sound in sounds]
        playlist_items, totallen = build_playlist(sounds, maxduration, fs, shuffle=shuffle_playback)
        if maxduration == -1:
            print(f"setting maxduration from playlist to {totallen}.")
            maxduration = totallen
            playlist_items = cycle(playlist_items)  # iter(playlist_items)
        else:
            playlist_items = cycle(playlist_items)
        # TODO: catch errors if channel numbers are inconsistent - sounds[ii].shape[-1] should be nb_analog+nb_digital
        if prot["DAQ"]["digital_chans_out"] is not None:
            nb_digital_chans_out = len(prot["DAQ"]["digital_chans_out"])
            digital_data = [snd[:, -nb_digital_chans_out:].astype(np.uint8) for snd in sounds]
            analog_data = [snd[:, :-nb_digital_chans_out] for snd in sounds]  # remove digital traces from stimset
        else:
            digital_data = None
            analog_data = sounds
        daq_save_filename = "{0}/{1}/{1}".format(daq_save_folder, filename)
        daq = DAQ.make(SER, user_name, ip_address, folder_name, python_exe)
        print("sending sound data to {0} - may take a while.".format(ip_address))

        daq.setup(
            daq_save_filename,
            playlist_items,
            playlist,
            maxduration,
            fs,
            display=prot["DAQ"]["display"],
            realtime=prot["DAQ"]["realtime"],
            clock_source=prot["DAQ"]["clock_source"],
            nb_inputsamples_per_cycle=prot["DAQ"]["nb_inputsamples_per_cycle"],
            analog_chans_out=prot["DAQ"]["analog_chans_out"],
            analog_chans_in=prot["DAQ"]["analog_chans_in"],
            digital_chans_out=prot["DAQ"]["digital_chans_out"],
            analog_data_out=analog_data,
            digital_data_out=digital_data,
            metadata={"analog_chans_in_info": prot["DAQ"]["analog_chans_in_info"]},
            params=undefaultify(prot["DAQ"]),
        )
        daq.init_local_logger("{0}/{1}/{1}_daq.log".format(daq_save_folder, filename))
        daq.start()
        logging.info("DAQ started")
        print("DAQ started")

    if "DLP" in prot["NODE"]["use_services"]:
        dlp.start()
        logging.info("DLP started")
        print("DLP started")

    print("quitting now - protocol will stop automatically on {0}".format(ip_address))


# def cli(protocolfilename: str = 'test_vr.yml', playlistfilename: str = 'ethoconfig/playlists/sine_short.txt'):
#     ip_address = 'localhost'
#     clientcaller(ip_address, playlistfilename, protocolfilename)


if __name__ == "__main__":
    ip_address = "localhost"

    # to run for size (300s)
    # protocolfilename = 'test_new_runners_size.yml'
    # playlistfilename = '../ethoconfig/playlists/sine.txt'
    # clientcaller(ip_address, playlistfilename, protocolfilename)

    # to position fly in the center
    # protocolfilename = 'kimia_size_1.yml'
    # playlistfilename = '../ethoconfig/playlists/silence.txt'
    # clientcaller(ip_address, playlistfilename, protocolfilename)

    # to test
    protocolfilename = "mini_test_3.yml"
    playlistfilename = "../ethoconfig/playlists/silence.txt"
    clientcaller(ip_address, playlistfilename, protocolfilename)
