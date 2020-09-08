import time
import numpy as np
import pandas as pd
import os
import subprocess
import logging
from itertools import cycle

from ethomaster import config
from ethomaster.head.ZeroClient import ZeroClient
from ethomaster.utils.config import readconfig, undefaultify
from ethomaster.utils.sound import parse_table, load_sounds, build_playlist

from ethoservice.ThuAZeroService import THUA
from ethoservice.DAQZeroService import DAQ
from ethoservice.GCMZeroService import GCM
from ethoservice.BLTZeroService import BLT


def clientcaller(ip_address, playlistfile, protocolfile, filename=None):
    # load config/protocols
    print(config)
    prot = readconfig(os.path.join(config['HEAD']['protocolfolder'], protocolfile))
    print(prot)
    maxduration = prot['NODE']['maxduration']
    user_name = prot['NODE']['user']
    folder_name = prot['NODE']['folder']
    SER = prot['NODE']['serializer']
    python_exe = config['GENERAL']['python_exe']
    # unique file name for video and node-local logs
    if filename is None:
        filename = '{0}-{1}'.format(ip_address, time.strftime('%Y%m%d_%H%M%S'))
    dirname = prot['NODE']['savefolder']
    print(filename)
    
    if 'THUA' in prot['NODE']['use_services']:
        thua = THUA.make(SER, user_name, ip_address, folder_name, python_exe)
        print(prot['THUA'])
        thua.setup(prot['THUA']['port'], prot['THUA']['interval'], maxduration + 10)
        thua.init_local_logger('{0}/{1}/{1}_thu.log'.format(dirname, filename))
        thua.start()

    if 'SPN' in prot['NODE']['use_services']:
        ptg = GCM.make(SER, user_name, ip_address, folder_name, python_exe)
        cam_params = undefaultify(prot['SPN'])
        ptg.setup('{0}/{1}/{1}'.format(dirname, filename), maxduration + 10, cam_params)
        ptg.init_local_logger('{0}/{1}/{1}_spn.log'.format(dirname, filename))
        ptg.start()
        # time.sleep(5)

    if 'BLT' in prot['NODE']['use_services']:
        blt = BLT.make(SER, user_name, ip_address, folder_name, python_exe)
        blt_params = undefaultify(prot['BLT'])
        blt.setup('{0}/{1}/{1}'.format(dirname, filename), maxduration + 10, blt_params)
        blt.init_local_logger('{0}/{1}/{1}_bltn.log'.format(dirname, filename))
        blt.start()
    
    print('DDDDDDDDDDDDDDDDDDDDDDDDDD')
        
    if 'DAQ' in prot['NODE']['use_services']:
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
            digital_data = [snd[:, -nb_digital_chans_out:].astype(np.uint8) for snd in sounds]
            analog_data = [snd[:, :-nb_digital_chans_out] for snd in sounds]  # remove digital traces from stimset
        else:
            digital_data = None
            analog_data = sounds
        daq_save_filename = '{0}/{1}/{1}_daq.h5'.format(daq_save_folder, filename)
        daq = DAQ.make(SER, user_name, ip_address, folder_name, python_exe)
        print('sending sound data to {0} - may take a while.'.format(ip_address))

        daq.setup(daq_save_filename, playlist_items, playlist,
              maxduration, fs,
              display=prot['DAQ']['display'],
              realtime=prot['DAQ']['realtime'],
              clock_source=prot['DAQ']['clock_source'],
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
    ip_address = 'localhost'
    protocolfilename = 'test.yml'
    playlistfilename = 'ethoconfig/playlists/sine_short.txt'
    clientcaller(ip_address, playlistfilename, protocolfilename)
