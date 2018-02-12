import time
import numpy as np
import pandas as pd
from ethomaster import config
from ethomaster.head.ZeroClient import ZeroClient
from ethoservice.SndZeroService import SND
from ethoservice.CamZeroService import CAM
from ethoservice.ThuZeroService import THU
from ethoservice.OptZeroService import OPT
from ethomaster.utils.sound import *
from ethomaster.utils.config import readconfig


def clientcaller(ip_address, playlistfile, protocolfile):
    # load config/protocols
    prot = readconfig(protocolfile)
    maxDuration = int(prot['NODE']['maxduration'])
    user_name = prot['NODE']['user']
    folder_name = prot['NODE']['folder']

    # unique file name for video and node-local logs
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
        thu.setup(prot['THU']['pin'], prot['THU']['interval'], maxDuration)
        thu.init_local_logger('{0}/{1}/{1}_thu.log'.format(dirname, filename))
        time.sleep(1)
        thu.start()

    if 'CAM' in prot['NODE']['use_services']:
        cam_server_name = 'python -m {0}'.format(CAM.__module__)
        cam_service_port = CAM.SERVICE_PORT
        framerate = prot['CAM']['framerate']
        framewidth = prot['CAM']['framewidth']
        frameheight = prot['CAM']['frameheight']
        shutterspeed = prot['CAM']['shutterspeed']

        print([CAM.SERVICE_PORT, CAM.SERVICE_NAME])
        cam = ZeroClient("{0}@{1}".format(user_name, ip_address), 'picam')
        print(cam.start_server(cam_server_name, folder_name, warmup=1))
        cam.connect("tcp://{0}:{1}".format(ip_address, cam_service_port))
        print('done')
        cam.setup('{0}/{1}/{1}.h264'.format(dirname, filename), maxDuration + 10)
        cam.init_local_logger('{0}/{1}/{1}_cam.log'.format(dirname, filename))
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
        sounds = load_sounds(playlist, fs)
        playlist_items = build_playlist(sounds, maxDuration, fs, shuffle=shuffle_playback)

        print([SND.SERVICE_PORT, SND.SERVICE_NAME])
        snd = ZeroClient("{0}@{1}".format(user_name, ip_address), 'pisnd')
        print(snd.start_server(snd_server_name, folder_name, warmup=1))
        snd.connect("tcp://{0}:{1}".format(ip_address, snd_service_port))
        print('done')
        print('sending sound data to {0} - may take a while.'.format(ip_address))
        snd.setup(sounds, playlist.to_msgpack(), playlist_items, maxDuration, fs)
        snd.init_local_logger('{0}/{1}/{1}_snd.log'.format(dirname, filename))
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

    print('quitting now - protocol will stop automatically on {0}'.format(ip_address))

if __name__ == '__main__':
    ip_address = 'rpi8'
    protocolfilename = 'protocols/default.txt'
    playlistfilename = 'playlists/sine_short.txt'
    clientcaller(ip_address, playlistfilename, protocolfilename)
