import numpy as np
from etho.head.ZeroClient import ZeroClient
from ethoservice.SndZeroService import SND
import pandas as pd
from etho import config
from etho.utils.sound import *
import sys
import time
import matplotlib.pyplot as plt

def read_header(filename):
    header = None
    with open('ctrl/wnHeader.txt', 'r') as fid:
        raw_line = fid.readline()
        line = ''
        while raw_line[0]=='#':
            line = line + raw_line[1:].lstrip().rstrip() + ';'
            raw_line = fid.readline()  # read next line
        header = {item.split('=')[0].strip(): item.split('=')[1].strip() for item in line.split(';') if len(item)}
    return header


fs = 44100
maxDuration = 740  # seconds

playlist = pd.read_table('playlists/test.txt', dtype=None, delimiter='\t', comment='#')
print(playlist)


sounds = load_sounds(playlist, fs)
# playlist_items = list(range(len(sounds)))
# playlist_items = build_playlist(sounds, maxDuration, fs)
# print(playlist_items)
playlist_items = build_playlist(sounds, maxDuration, fs, shuffle=False)
print(playlist_items)

user_name = config['GENERAL']['user']
ip_address = 'rpi8'
snd_server_name = 'python -m {0}'.format(SND.__module__)
snd_folder_name = config['GENERAL']['folder']
snd_service_port = SND.SERVICE_PORT
#
print([SND.SERVICE_PORT, SND.SERVICE_NAME])
snd = ZeroClient("{0}@{1}".format(user_name, ip_address))

print(snd.start_server(snd_server_name, snd_folder_name, warmup=1))
snd.connect("tcp://{0}:{1}".format(ip_address, snd_service_port))
print('init logger')
try:
    snd.init_local_logger('test/test_snd.log')
    print('setup')
    snd.setup(sounds, playlist.to_msgpack(), playlist_items, maxDuration, fs)
    print('  done')
except Exception as e:
    print(e)
    snd.sr.kill_service('SndZeroService')
    sys.exit(0)
snd.start()
time.sleep(1)  # wait for playback to start (is_busy==True)
while snd.is_busy():
    try:
        sys.stdout.write("\rplaying {0}, {1}.                                           ".format(
            pd.read_msgpack(snd.info()).stimFileName,  snd.progress()))
    except Exception as e:
        print(e)
    time.sleep(1)
print('\n')
print('done')
# snd.finish()
#
# print('stopping server:')
# try:
#  print('SND: {0}'.format(snd.stop_server()))
# except Exception as e:
# #  print(e)
