import time
import numpy as np
from etho.head.ZeroClient import ZeroClient
from ethoservice.DAQZeroService import DAQ
from ethoservice.PTGZeroService import PTG
from ethoservice.ThuZeroService import THU
import pandas as pd
from etho import config
from etho.utils.sound2 import *
from etho.utils.config import readconfig
import subprocess

def main(ip_address, playlistfile, protocolfile):
    # load config/protocols
    prot = readconfig(protocolfile)
    maxDuration = int(prot['NODE']['maxduration'])


    user_name = config['GENERAL']['user']
    folder_name = config['GENERAL']['folder']
    daq_server_name = 'python -m {0}'.format(DAQ.__module__)
    daq_service_port = DAQ.SERVICE_PORT
    ptg_server_name = 'python -m {0}'.format(PTG.__module__)
    ptg_service_port = PTG.SERVICE_PORT

    # unique file name for video and node-local logs
    filename = '{0}-{1}'.format(ip_address, time.strftime('%Y%m%d_%H%M%S'))
    dirname = 'C:/Users/ncb/'#prot['NODE']['savefolder']#'data/'

    if 'PTG' in prot['NODE']['use_services']:
        framerate = prot['PTG']['framerate']
        framewidth = prot['PTG']['framewidth']
        frameheight = prot['PTG']['frameheight']
        # shutterspeed = prot['PTG']['shutterspeed']

        print([PTG.SERVICE_PORT, PTG.SERVICE_NAME])
        ptg = ZeroClient("{0}@{1}".format(user_name, ip_address), 'ptgcam')
        # print(ptg.start_server(ptg_server_name, folder_name, warmup=1))
        subprocess.Popen('python -m ethoservice.PTGZeroService')
        ptg.connect("tcp://{0}:{1}".format(ip_address, ptg_service_port))
        print('done')
        ptg.setup('{0}/{1}'.format(dirname, filename), maxDuration + 10)
        ptg.init_local_logger('{0}/{1}_ptg.log'.format(dirname, filename))
        ptg.start()
        time.sleep(5)

    if 'DAQ' in prot['NODE']['use_services']:
        fs = int(prot['DAQ']['samplingrate'])
        shuffle_playback = bool(prot['DAQ']['shuffle'])
        # load playlist, sounds, and enumerate play order
        playlist = pd.read_table(playlistfile, dtype=None, delimiter='\t')
        sounds = load_sounds(playlist, fs)
        playlist_items = build_playlist(sounds, maxDuration, fs, shuffle=shuffle_playback)

        print([DAQ.SERVICE_PORT, DAQ.SERVICE_NAME])
        daq = ZeroClient("{0}@{1}".format(user_name, ip_address), 'pidaq')
        # print(daq.start_server(daq_server_name, folder_name, warmup=1))
        subprocess.Popen('python -m ethoservice.DAQZeroService')
        daq.connect("tcp://{0}:{1}".format(ip_address, daq_service_port))
        print('done')
        print('sending sound data to {0} - may take a while.'.format(ip_address))
        daq.setup('{0}/{1}.h5'.format(dirname, filename), sounds, playlist.to_msgpack(), playlist_items, maxDuration, fs)
        daq.init_local_logger('{0}/{1}_daq.log'.format(dirname, filename))
        daq.start()

    print('quitting now - protocol will stop automatically on {0}'.format(ip_address))

if __name__ == '__main__':
    ip_address = 'localhost'
    protocolfilename = 'protocols/chain_default.txt'
    playlistfilename = 'playlists/IPItuneChaining.txt'
    main(ip_address, playlistfilename, protocolfilename)
