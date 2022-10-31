import time
import numpy as np
from etho.head.ZeroClient import ZeroClient
from services.SndZeroService import SND
from services.CamZeroService import CAM
from services.ThuZeroService import THU
import pandas as pd
from etho import config
from etho.utils.sound import *
from etho.utils.config import readconfig


def main(ip_address, playlistfile, protocolfile):
    # load config/protocols
    prot = readconfig(protocolfile)
    maxDuration = int(prot['NODE']['maxduration'])


    user_name = config['GENERAL']['user']
    folder_name = config['GENERAL']['folder']
    snd_server_name = 'python -m {0}'.format(SND.__module__)
    snd_service_port = SND.SERVICE_PORT
    cam_server_name = 'python -m {0}'.format(CAM.__module__)
    cam_service_port = CAM.SERVICE_PORT
    thu_server_name = 'python -m {0}'.format(THU.__module__)
    thu_service_port = THU.SERVICE_PORT

    # unique file name for video and node-local logs
    filename = '{0}-{1}'.format(ip_address, time.strftime('%Y%m%d_%H%M%S'))
    dirname = 'data/'

    if 'THU' in prot['NODE']['use_services']:
        print([THU.SERVICE_PORT, THU.SERVICE_NAME])
        thu = ZeroClient("{0}@{1}".format(user_name, ip_address), 'pithu')
        print(thu.start_server(thu_server_name, folder_name, warmup=1))
        thu.connect("tcp://{0}:{1}".format(ip_address, thu_service_port))
        print('done')
        print(prot['THU']['pin'], prot['THU']['interval'], maxDuration)
        thu.setup(prot['THU']['pin'], prot['THU']['interval'], maxDuration)
        print('{0}/{1}_thu.log'.format(dirname, filename))
        thu.init_local_logger('{0}/{1}_thu.log'.format(dirname, filename))
        thu.start()

    if 'CAM' in prot['NODE']['use_services']:
        framerate = prot['CAM']['framerate']
        framewidth = prot['CAM']['framewidth']
        frameheight = prot['CAM']['frameheight']
        shutterspeed = prot['CAM']['shutterspeed']

        print([CAM.SERVICE_PORT, CAM.SERVICE_NAME])
        cam = ZeroClient("{0}@{1}".format(user_name, ip_address), 'picam')
        print(cam.start_server(cam_server_name, folder_name, warmup=1))
        cam.connect("tcp://{0}:{1}".format(ip_address, cam_service_port))
        print('done')
        cam.setup('{0}/{1}.h264'.format(dirname, filename), maxDuration + 10)
        cam.init_local_logger('{0}/{1}_cam.log'.format(dirname, filename))
        cam.start()
        time.sleep(5)

    if 'SND' in prot['NODE']['use_services']:
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
        snd.init_local_logger('{0}/{1}_snd.log'.format(dirname, filename))
        snd.start()

    print('quitting now - protocol will stop automatically on {0}'.format(ip_address))

if __name__ == '__main__':
    ip_address = 'rpi6'
    protocolfilename = 'protocols/playback_default.txt'
    playlistfilename = 'playlists/test.txt'
    main(ip_address, playlistfilename, protocolfilename)
