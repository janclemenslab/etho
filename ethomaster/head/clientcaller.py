import time
import numpy as np
import pandas as pd
import subprocess

from ethomaster import config
from ethomaster.head.ZeroClient import ZeroClient
from ethoservice.SndZeroService import SND
from ethoservice.CamZeroService import CAM
from ethoservice.ThuZeroService import THU
from ethoservice.ThuAZeroService import THUA
from ethoservice.OptZeroService import OPT
from ethoservice.DAQZeroService import DAQ
from ethoservice.PTGZeroService import PTG

from ethomaster.utils.sound import *
from ethomaster.utils.config import readconfig


def clientcaller(ip_address, playlistfile, protocolfile, filename=None):
    # load config/protocols
    prot = readconfig(protocolfile)
    print(prot)
    maxDuration = int(prot['NODE']['maxduration'])
    user_name = prot['NODE']['user']
    folder_name = prot['NODE']['folder']

    # unique file name for video and node-local logs
    if filename is None:
        filename = '{0}-{1}'.format(ip_address, time.strftime('%Y%m%d_%H%M%S'))
    dirname = prot['NODE']['savefolder']
    print(filename)

    if 'THU' in prot['NODE']['use_services']:
        thu_server_name = 'python -m {0}'.format(THU.__module__)
        thu_service_port = THU.SERVICE_PORT
        print([THU.SERVICE_PORT, THU.SERVICE_NAME])
        thu = ZeroClient("{0}@{1}".format(user_name, ip_address), 'pithu')
        print(thu.start_server(thu_server_name, folder_name, warmup=1))
        thu.connect("tcp://{0}:{1}".format(ip_address, thu_service_port))
        print('done')
        print(prot['THU']['pin'], prot['THU']['interval'], maxDuration)
        thu.init_local_logger('{0}/{1}/{1}_thu.log'.format(dirname, filename))
        thu.setup(prot['THU']['pin'], prot['THU']['interval'], maxDuration + 20)
        time.sleep(1)
        thu.start()

    if 'CAM' in prot['NODE']['use_services']:
        cam_server_name = 'python -m {0}'.format(CAM.__module__)
        cam_service_port = CAM.SERVICE_PORT

        print([CAM.SERVICE_PORT, CAM.SERVICE_NAME])
        cam = ZeroClient("{0}@{1}".format(user_name, ip_address), 'picam')
        print(cam.start_server(cam_server_name, folder_name, warmup=1))
        cam.connect("tcp://{0}:{1}".format(ip_address, cam_service_port))
        print('done')
        cam.init_local_logger('{0}/{1}/{1}_cam.log'.format(dirname, filename))
        cam.setup('{0}/{1}/{1}.h264'.format(dirname, filename), maxDuration + 10)
        time.sleep(1)
        cam.start()
        time.sleep(5)

    if 'SND' in prot['NODE']['use_services']:
        snd_server_name = 'python -m {0}'.format(SND.__module__)
        snd_service_port = SND.SERVICE_PORT
        fs = int(prot['SND']['samplingrate'])
        shuffle_playback = bool(prot['SND']['shuffle'])
        # load playlist, sounds, and enumerate play order
        playlist = pd.read_table(playlistfile, dtype=None, delimiter='\t')
        print(config)
        sounds = load_sounds(playlist, fs, attenuation=config['ATTENUATION'],
                    LEDamp=prot['SND']['ledamp'], stimfolder=config['HEAD']['stimfolder'])
        playlist_items = build_playlist(sounds, maxDuration, fs, shuffle=shuffle_playback)

        print([SND.SERVICE_PORT, SND.SERVICE_NAME])
        snd = ZeroClient("{0}@{1}".format(user_name, ip_address), 'pisnd')
        print(snd.start_server(snd_server_name, folder_name, warmup=1))
        snd.connect("tcp://{0}:{1}".format(ip_address, snd_service_port))
        print('done')
        print('sending sound data to {0} - may take a while.'.format(ip_address))
        snd.init_local_logger('{0}/{1}/{1}_snd.log'.format(dirname, filename))
        # COMPRESS SOUNDS? use gzip
        snd.setup(sounds, playlist.to_msgpack(), playlist_items, maxDuration, fs)
        snd.start()

    if 'OPT' in prot['NODE']['use_services']:
        opt_server_name = 'python -m {0}'.format(OPT.__module__)
        opt_service_port = OPT.SERVICE_PORT
        print([OPT.SERVICE_PORT, OPT.SERVICE_NAME])
        opt = ZeroClient("{0}@{1}".format(user_name, ip_address), 'piopt')
        print(opt.start_server(opt_server_name, folder_name, warmup=1))
        opt.connect("tcp://{0}:{1}".format(ip_address, opt_service_port))
        print('done')
        print(prot['OPT']['pin'], prot['OPT']['blinkinterval'], prot['OPT']['blinkduration'], maxDuration)
        opt.setup(prot['OPT']['pin'], maxDuration, prot['OPT']['blinkinterval'], prot['OPT']['blinkduration'])
        opt.init_local_logger('{0}/{1}/{1}_opt.log'.format(dirname, filename))
        opt.start()

    if 'THUA' in prot['NODE']['use_services']:
        thua_server_name = 'python -m {0}'.format(THUA.__module__)
        thua_service_port = THUA.SERVICE_PORT
        print([THUA.SERVICE_PORT, THUA.SERVICE_NAME])

        thua = ZeroClient("{0}@{1}".format(user_name, ip_address), 'thuarduino')
        # print(thua.start_server(thua_server_name, folder_name, warmup=1))
        subprocess.Popen(thua_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
        thua.connect("tcp://{0}:{1}".format(ip_address, thua_service_port))
        print('done')
        print(prot['THUA'])
        thua.setup(prot['THUA']['port'], float(prot['THUA']['interval']), maxDuration + 10)
        thua.init_local_logger('{0}/{1}/{1}_thu.log'.format(dirname, filename))
        thua.start()

    if 'PTG' in prot['NODE']['use_services']:
        ptg_server_name = 'python -m {0}'.format(PTG.__module__)
        ptg_service_port = PTG.SERVICE_PORT
        print([PTG.SERVICE_PORT, PTG.SERVICE_NAME])

        ptg = ZeroClient("{0}@{1}".format(user_name, ip_address), 'ptgcam')
        # print(ptg.start_server(ptg_server_name, folder_name, warmup=1))
        subprocess.Popen(ptg_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
        ptg.connect("tcp://{0}:{1}".format(ip_address, ptg_service_port))
        print('done')
        ptg.setup('{0}/{1}/{1}'.format(dirname, filename), maxDuration + 10, prot['PTG'])
        ptg.init_local_logger('{0}/{1}/{1}_ptg.log'.format(dirname, filename))
        ptg.start()
        time.sleep(5)

    if 'DAQ' in prot['NODE']['use_services']:
        daq_server_name = 'python -m {0}'.format(DAQ.__module__)
        daq_service_port = DAQ.SERVICE_PORT

        fs = int(prot['DAQ']['samplingrate'])
        shuffle_playback = eval(prot['DAQ']['shuffle'])
        # load playlist, sounds, and enumerate play order
        playlist = pd.read_table(playlistfile, dtype=None, delimiter='\t')
        sounds = load_sounds(playlist, fs, attenuation=config['ATTENUATION'],
                    LEDamp=prot['DAQ']['ledamp'], stimfolder=config['HEAD']['stimfolder'],
                    mirrorsound=True, cast2int=False)
        playlist_items = build_playlist(sounds, maxDuration, fs, shuffle=shuffle_playback)

        if not isinstance(prot['DAQ']['channels_in'], list):
            prot['DAQ']['channels_in'] = [prot['DAQ']['channels_in']]
        if not isinstance(prot['DAQ']['channels_out'], list):
            prot['DAQ']['channels_out'] = [prot['DAQ']['channels_out']]

        print([DAQ.SERVICE_PORT, DAQ.SERVICE_NAME])
        daq = ZeroClient("{0}@{1}".format(user_name, ip_address), 'pidaq')
        # print(daq.start_server(daq_server_name, folder_name, warmup=1))
        subprocess.Popen(daq_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
        daq.connect("tcp://{0}:{1}".format(ip_address, daq_service_port))
        print('done')
        print('sending sound data to {0} - may take a while.'.format(ip_address))
        daq.setup('{0}/{1}/{1}_daq.h5'.format(dirname, filename), sounds, playlist.to_msgpack(), playlist_items, maxDuration, fs, prot['DAQ'])
        daq.init_local_logger('{0}/{1}/{1}_daq.log'.format(dirname, filename))
        daq.start()

    print('quitting now - protocol will stop automatically on {0}'.format(ip_address))


if __name__ == '__main__':
    ip_address = 'rpi8'
    protocolfilename = 'protocols/default.txt'
    playlistfilename = 'playlists/sine_short.txt'
    clientcaller(ip_address, playlistfilename, protocolfilename)
