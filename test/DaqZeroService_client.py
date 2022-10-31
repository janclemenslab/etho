import time
from etho.head.ZeroClient import ZeroClient
from services.DAQZeroService import DAQ
import pandas as pd
from etho import config
from etho.utils.sound2 import *
from etho.utils.config import readconfig


ip_address = 'localhost'
protocolfile = 'protocols/default.txt'
playlistfile = 'playlists/IPItuneChaining.txt'

# load config/protocols
prot = readconfig(protocolfile)
maxDuration = int(3600)


user_name = config['GENERAL']['user']
folder_name = config['GENERAL']['folder']
daq_server_name = 'python -m {0}'.format(DAQ.__module__)
daq_service_port = DAQ.SERVICE_PORT

# unique file name for video and node-local logs
filename = '{0}-{1}'.format(ip_address, time.strftime('%Y%m%d_%H%M%S'))
dirname = 'data/'

fs = int(prot['DAQ']['samplingrate'])
shuffle_playback = bool(prot['DAQ']['shuffle'])
# load playlist, sounds, and enumerate play order
playlist = pd.read_table(playlistfile, dtype=None, delimiter='\t')
sounds = load_sounds(playlist, fs)
playlist_items = build_playlist(sounds, maxDuration, fs, shuffle=shuffle_playback)
print(playlist_items)

print([DAQ.SERVICE_PORT, DAQ.SERVICE_NAME])
daq = ZeroClient("{0}@{1}".format(user_name, ip_address), 'nidaq')
# print(daq.start_server(daq_server_name, folder_name, warmup=1))
subprocess.Popen('python -m ethoservice.PTGZeroService')
daq.connect("tcp://{0}:{1}".format(ip_address, daq_service_port))
print('done')
print('sending sound data to {0} - may take a while.'.format(ip_address))
daq.setup('{0}/{1}.h5'.format(dirname, filename), sounds, playlist.to_msgpack(), playlist_items, maxDuration, fs)
daq.init_local_logger('{0}/{1}_daq.log'.format(dirname, filename))
daq.start()

# np_sounds = list()
# for sound in sounds:
#     np_sounds.append(np.array(sound, dtype=np.float64))
