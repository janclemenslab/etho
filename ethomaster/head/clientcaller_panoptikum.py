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
    if 'python_exe' in config['GENERAL']:
        python_exe =  config['GENERAL']['python_exe']
    else:
        python_exe = 'C:/Users/ncb/Miniconda3/python.exe'


    if 'SPN' in prot['NODE']['use_services']:
        ptg_server_name = f'{python_exe} -m {SPN.__module__} {SER}'
        print([SPN.SERVICE_PORT, SPN.SERVICE_NAME])
        ptg = ZeroClient("{0}@{1}".format(user_name, ip_address), 'spn', serializer=SER)
        subprocess.Popen(ptg_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
        ptg.connect("tcp://{0}:{1}".format(ip_address, PTG.SERVICE_PORT))
        print('done')
        cam_params = dict(prot['SPN'])
        ptg.setup('{0}/{1}/{1}'.format(dirname, filename), maxduration + 10, cam_params)
        ptg.init_local_logger('{0}/{1}/{1}_spn.log'.format(dirname, filename))
        
    if 'SPN_ZOOM' in prot['NODE']['use_services']:
        port = 4247  # use custom port so we can start two SPN instances
        ptg_server_name = f'{python_exe} -m {SPN.__module__} {SER} {port}'
        print([port, SPN.SERVICE_NAME])
        ptg2 = ZeroClient("{0}@{1}".format(user_name, ip_address), 'spnzoom', serializer=SER)
        subprocess.Popen(ptg_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
        ptg2.connect("tcp://{0}:{1}".format(ip_address, port))
        print('done')
        cam_params = dict(prot['SPN_ZOOM'])
        ptg2.setup('{0}/{1}/{1}_zoom'.format(dirname, filename), maxduration + 10, cam_params)
        ptg2.init_local_logger('{0}/{1}/{1}_spnzoom.log'.format(dirname, filename))   
        ptg2.start()

    if 'SPN' in prot['NODE']['use_services']:
        ptg.start()

    time.sleep(5)

    if 'DAQ' in prot['NODE']['use_services']:
        daq_server_name = f'{python_exe} -m {DAQ.__module__} {SER}'
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
    #protocolfilename = 'C:/Users/ncb/ethoconfig/protocols/panoptikum_zoom-only_5min.yml'
    protocolfilename = 'C:/Users/ncb/ethoconfig/protocols/panoptikum_zoom-zoom_5min.yml'
    playlistfilename = 'C:/Users/ncb/ethoconfig/playlists/0 silence.txt'
    clientcaller(ip_address, playlistfilename, protocolfilename)