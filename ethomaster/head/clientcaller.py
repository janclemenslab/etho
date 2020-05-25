import time
import numpy as np
import pandas as pd
import subprocess
import logging
from itertools import cycle

from ethomaster import config
from ethomaster.head.ZeroClient import ZeroClient
from ethomaster.utils.config import readconfig
from ethomaster.utils.sound import parse_table, load_sounds, build_playlist

from ethoservice.SndZeroService import SND
from ethoservice.CamZeroService import CAM
from ethoservice.ThuZeroService import THU
from ethoservice.ThuAZeroService import THUA
from ethoservice.OptZeroService import OPT
from ethoservice.DAQZeroService import DAQ
from ethoservice.PTGZeroService import PTG
from ethoservice.SPNZeroService import SPN


def clientcaller(ip_address, playlistfile, protocolfile, filename=None):
    # load config/protocols
    # import tensorflow as tf
    # print('tpip ensorflow version', tf.__version__)
    prot = readconfig(protocolfile)
    print(prot)
    maxduration = prot['NODE']['maxduration']
    user_name = prot['NODE']['user']
    folder_name = prot['NODE']['folder']
    SER = prot['NODE']['serializer']

    # unique file name for video and node-local logs
    if filename is None:
        filename = '{0}-{1}'.format(ip_address, time.strftime('%Y%m%d_%H%M%S'))
    dirname = prot['NODE']['savefolder']
    print(filename)

    python_exe = 'C:/Miniconda3/envs/ethod_dss/python.exe'

    if 'THUA' in prot['NODE']['use_services']:
        thua_server_name = f'{python_exe} -m {THUA.__module__} {SER}'#.format(THUA.__module__, SER)
        print([THUA.SERVICE_PORT, THUA.SERVICE_NAME])
        thua = ZeroClient("{0}@{1}".format(user_name, ip_address), 'thuarduino', serializer=SER)
        subprocess.Popen(thua_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
        thua.connect("tcp://{0}:{1}".format(ip_address, THUA.SERVICE_PORT))
        print('done')
        print(prot['THUA'])
        thua.setup(prot['THUA']['port'], prot['THUA']['interval'], maxduration + 10)
        thua.init_local_logger('{0}/{1}/{1}_thu.log'.format(dirname, filename))
        thua.start()

    if 'PTG' in prot['NODE']['use_services']:
        ptg_server_name = f'{python_exe} -m {PTG.__module__} {SER}'#'python -m {0} {1}'.format(PTG.__module__, SER)
        print([PTG.SERVICE_PORT, PTG.SERVICE_NAME])
        ptg = ZeroClient("{0}@{1}".format(user_name, ip_address), 'ptgcam', serializer=SER)
        subprocess.Popen(ptg_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
        ptg.connect("tcp://{0}:{1}".format(ip_address, PTG.SERVICE_PORT))
        print('done')
        cam_params = dict(prot['PTG'])
        ptg.setup('{0}/{1}/{1}'.format(dirname, filename), maxduration + 10, cam_params)
        ptg.init_local_logger('{0}/{1}/{1}_ptg.log'.format(dirname, filename))
        ptg.start()
        time.sleep(5)

    if 'SPN' in prot['NODE']['use_services']:
        ptg_server_name = f'{python_exe} -m {SPN.__module__} {SER}'#'python -m {0} {1}'.format(PTG.__module__, SER)
        print([SPN.SERVICE_PORT, SPN.SERVICE_NAME])
        ptg = ZeroClient("{0}@{1}".format(user_name, ip_address), 'spncam', serializer=SER)
        subprocess.Popen(ptg_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
        ptg.connect("tcp://{0}:{1}".format(ip_address, PTG.SERVICE_PORT))
        print('done')
        cam_params = dict(prot['SPN'])
        ptg.setup('{0}/{1}/{1}'.format(dirname, filename), maxduration + 10, cam_params)
        ptg.init_local_logger('{0}/{1}/{1}_spn.log'.format(dirname, filename))
        ptg.start()
        time.sleep(5)

    if 'DAQ' in prot['NODE']['use_services']:
        daq_server_name = f'{python_exe} -m {DAQ.__module__} {SER}'#'python -m {0} {1}'.format(DAQ.__module__, SER)
        if prot['DAQ']['run_locally']:
            print('   Running DAQ job locally.')
            ip_address = 'localhost'
            daq_save_folder = 'C:/Users/ncb/data'
        else:
            daq_save_folder = dirname
        fs = prot['DAQ']['samplingrate']
        shuffle_playback = prot['DAQ']['shuffle']

        playlist = parse_table(playlistfile)

        if ip_address in config['ATTENUATION']:  # use node specific attenuation data
            attenuation = config['ATTENUATION'][ip_address]
            print(f'using attenuation data specific to {ip_address}.')
        else:
            attenuation = config['ATTENUATION']

        sounds = load_sounds(playlist, fs, attenuation=attenuation,
                             LEDamp=prot['DAQ']['ledamp'], stimfolder=config['HEAD']['stimfolder'])
        sounds = [sound.astype(np.float64) for sound in sounds]
        playlist_items, totallen = build_playlist(sounds, maxduration, fs, shuffle=shuffle_playback)
        if maxduration == -1:
            print(f'setting maxduration from playlist to {totallen}.')
            maxduration = totallen
            playlist_items = cycle(playlist_items)  # iter(playlist_items)
        else:
            playlist_items = cycle(playlist_items)

        # TODO: catch errors if channel numbers are inconsistent - sounds[ii].shape[-1] should be nb_analog+nb_digital
        if prot['DAQ']['digital_chans_out'] is not None:
            nb_digital_chans_out = len(prot['DAQ']['digital_chans_out'])
            digital_data = [snd[:, -nb_digital_chans_out].astype(np.uint8) for snd in sounds]
            analog_data = [snd[:, :nb_digital_chans_out+1] for snd in sounds]  # remove digital traces from stimset
        else:
            digital_data = None
            analog_data = sounds
        daq_save_filename = '{0}/{1}/{1}_daq.h5'.format(daq_save_folder, filename)
        print([DAQ.SERVICE_PORT, DAQ.SERVICE_NAME])
        daq = ZeroClient("{0}@{1}".format(user_name, ip_address), 'nidaq', serializer=SER)

        subprocess.Popen(daq_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
        daq.connect("tcp://{0}:{1}".format(ip_address, DAQ.SERVICE_PORT))
        print('done')
        print('sending sound data to {0} - may take a while.'.format(ip_address))

        daq.setup(daq_save_filename, playlist_items, playlist,
              maxduration, fs,
              display=prot['DAQ']['display'],
              realtime=prot['DAQ']['realtime'],
              nb_inputsamples_per_cycle=prot['DAQ']['nb_inputsamples_per_cycle'],
              analog_chans_out=prot['DAQ']['analog_chans_out'],
              analog_chans_in=prot['DAQ']['analog_chans_in'],
              digital_chans_out=prot['DAQ']['digital_chans_out'],
              analog_data_out=analog_data,
              digital_data_out=digital_data,
              metadata={'analog_chans_in_info': prot['DAQ']['analog_chans_in_info']})
        daq.init_local_logger('{0}/{1}/{1}_daq.log'.format(daq_save_folder, filename))
        daq.start()
        logging.info('DAQ started')

    print('quitting now - protocol will stop automatically on {0}'.format(ip_address))


if __name__ == '__main__':
    ip_address = 'rpi8'
    protocolfilename = 'protocols/default.txt'
    playlistfilename = 'playlists/sine_short.txt'
    clientcaller(ip_address, playlistfilename, protocolfilename)
