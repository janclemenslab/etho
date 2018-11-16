import time
import subprocess
from itertools import cycle

from ethomaster import config
from ethomaster.head.ZeroClient import ZeroClient
from ethomaster.utils.sound import parse_table, load_sounds, build_playlist
from ethomaster.utils.config import readconfig

from ethoservice.ThuAZeroService import THUA
from ethoservice.DAQZeroService import DAQ
from ethoservice.PTGZeroService import PTG


def clientcaller(ip_address, playlistfile, protocolfile, filename=None):
    # load config/protocols
    prot = readconfig(protocolfile)
    print(prot)
    maxduration = prot['NODE']['maxduration']
    user_name = prot['NODE']['user']
    SER = prot['NODE']['serializer']

    # unique file name for video and node-local logs
    if filename is None:
        filename = '{0}-{1}'.format(ip_address, time.strftime('%Y%m%d_%H%M%S'))
    dirname = prot['NODE']['savefolder']
    print(filename)

    if 'THUA' in prot['NODE']['use_services']:
        thua_server_name = 'python -m {0}'.format(THUA.__module__, SER)
        print([THUA.SERVICE_PORT, THUA.SERVICE_NAME])

        thua = ZeroClient("{0}@{1}".format(user_name, ip_address), 'thuarduino')
        subprocess.Popen(thua_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
        thua.connect("tcp://{0}:{1}".format(ip_address, THUA.SERVICE_PORT))
        print('done')
        print(prot['THUA'])
        thua.setup(prot['THUA']['port'], float(prot['THUA']['interval']), maxduration + 10)
        thua.init_local_logger('{0}/{1}/{1}_thu.log'.format(dirname, filename))
        thua.start()

    if 'PTG' in prot['NODE']['use_services']:
        ptg_server_name = 'python -m {0}'.format(PTG.__module__, SER)
        print([PTG.SERVICE_PORT, PTG.SERVICE_NAME])

        ptg = ZeroClient("{0}@{1}".format(user_name, ip_address), 'ptgcam')
        subprocess.Popen(ptg_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
        ptg.connect("tcp://{0}:{1}".format(ip_address, PTG.SERVICE_PORT))
        print('done')
        ptg.setup('{0}/{1}/{1}'.format(dirname, filename), maxduration + 10, prot['PTG'])
        ptg.init_local_logger('{0}/{1}/{1}_ptg.log'.format(dirname, filename))
        ptg.start()
        time.sleep(5)

    if 'DAQ' in prot['NODE']['use_services']:
        daq_server_name = 'python -m {0} {1}'.format(DAQ.__module__, SER)

        fs = int(prot['DAQ']['samplingrate'])
        shuffle_playback = eval(prot['DAQ']['shuffle'])
        playlist = parse_table(playlistfile)
        sounds = load_sounds(playlist, fs, attenuation=config['ATTENUATION'],
                             LEDamp=prot['DAQ']['ledamp'], stimfolder=config['HEAD']['stimfolder'])
        playlist_items, totallen = build_playlist(sounds, maxduration, fs, shuffle=shuffle_playback)
        if maxduration == -1:
            print(f'setting maxduration from playlist to {totallen}.')
            maxduration = totallen
            playlist_items = cycle(playlist_items)  # iter(playlist_items)
        else:
            playlist_items = cycle(playlist_items)

        daq_save_filename = '{0}/{1}/{1}_daq_test.h5'.format(dirname, filename)
        print([DAQ.SERVICE_PORT, DAQ.SERVICE_NAME])
        daq = ZeroClient("{0}@{1}".format(user_name, ip_address), 'nidaq', serializer=SER)
        # print(daq.start_server(daq_server_name, folder_name, warmup=1))
        subprocess.Popen(daq_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
        daq.connect("tcp://{0}:{1}".format(ip_address, DAQ.SERVICE_PORT))
        print('done')
        print('sending sound data to {0} - may take a while.'.format(ip_address))
        # daq.setup(daq_save_filename, sounds, playlist.to_msgpack(), playlist_items, maxduration, fs, prot['DAQ'])
        daq.setup(daq_save_filename, playlist_items, maxduration, fs, prot['DAQ'].get('display', 'False'),
                  analog_chans_out=prot['DAQ'].get('analog_chans_out', []),
                  analog_chans_in=prot['DAQ'].get('analog_chans_in', []),
                  analog_data_out=sounds)


        daq.init_local_logger('{0}/{1}/{1}_daq.log'.format(dirname, filename))
        daq.start()

    print('quitting now - protocol will stop automatically on {0}'.format(ip_address))


if __name__ == '__main__':
    ip_address = 'rpi8'
    protocolfilename = 'protocols/default.txt'
    playlistfilename = 'playlists/sine_short.txt'
    clientcaller(ip_address, playlistfilename, protocolfilename)
