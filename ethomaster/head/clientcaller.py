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

    if 'THU' in prot['NODE']['use_services']:
        thu_server_name = 'python -m {0} {1}'.format(THU.__module__, SER)
        print([THU.SERVICE_PORT, THU.SERVICE_NAME])
        thu = ZeroClient("{0}@{1}".format(user_name, ip_address), 'pithu', serializer=SER)
        print(' starting server:', end='')
        ret = thu.start_server(thu_server_name, folder_name, warmup=1)
        print(f'{"success" if ret else "FAILED"}.')
        print(' connecting to server:', end='')
        thu.connect("tcp://{0}:{1}".format(ip_address,  THU.SERVICE_PORT))
        print(f'{"success" if ret else "FAILED"}.')
        print(prot['THU']['pin'], prot['THU']['interval'], maxduration)

        thu.init_local_logger('{0}/{1}/{1}_thu.log'.format(dirname, filename))
        thu.setup(prot['THU']['pin'], prot['THU']['interval'], maxduration + 20)
        time.sleep(1)
        thu.start()

    if 'CAM' in prot['NODE']['use_services']:
        cam_server_name = 'python -m {0} {1}'.format(CAM.__module__, SER)
        print([CAM.SERVICE_PORT, CAM.SERVICE_NAME])
        cam = ZeroClient("{0}@{1}".format(user_name, ip_address), 'picam', serializer=SER)
        print(' starting server:', end='')
        ret = cam.start_server(cam_server_name, folder_name, warmup=1)
        print(f'{"success" if ret else "FAILED"}.')
        cam.connect("tcp://{0}:{1}".format(ip_address, CAM.SERVICE_PORT))
        print('done')
        cam.init_local_logger('{0}/{1}/{1}_cam.log'.format(dirname, filename))
        cam.setup('{0}/{1}/{1}.h264'.format(dirname, filename), maxduration + 10)
        time.sleep(1)
        cam.start()
        cam_start_time = time.time() # time.sleep(5)

    if 'SND' in prot['NODE']['use_services']:
        snd_server_name = 'python -m {0} {1}'.format(SND.__module__, SER)
        fs = prot['SND']['samplingrate']
        shuffle_playback = prot['SND']['shuffle']

        # load playlist, sounds, and enumerate play order
        playlist = parse_table(playlistfile)

        if ip_address in config['ATTENUATION']:  # use node specific attenuation data
            attenuation = config['ATTENUATION'][ip_address]
            print(f'using attenuation data specific to {ip_address}.')
        else:
            attenuation = config['ATTENUATION']

        sounds = load_sounds(playlist, fs, attenuation=attenuation,
                             LEDamp=prot['SND']['ledamp'],
                             stimfolder=config['HEAD']['stimfolder'],
                             cast2int=True)

        playlist_items, totallen = build_playlist(sounds, maxduration, fs, shuffle=shuffle_playback)

        print([SND.SERVICE_PORT, SND.SERVICE_NAME])
        snd = ZeroClient("{0}@{1}".format(user_name, ip_address), 'pisnd', serializer=SER)
        print(' starting server:', end='')
        ret = snd.start_server(snd_server_name, folder_name, warmup=1)
        print(f'{"success" if ret else "FAILED"}.')
        snd.connect("tcp://{0}:{1}".format(ip_address, SND.SERVICE_PORT))
        print('done')
        print('sending sound data to {0} - may take a while.'.format(ip_address))
        snd.init_local_logger('{0}/{1}/{1}_snd.log'.format(dirname, filename))
        snd.setup(sounds, playlist, playlist_items, totallen, fs)

    if 'OPT' in prot['NODE']['use_services']:
        opt_server_name = 'python -m {0} {1}'.format(OPT.__module__, SER)
        print([OPT.SERVICE_PORT, OPT.SERVICE_NAME])
        opt = ZeroClient("{0}@{1}".format(user_name, ip_address), 'piopt', serializer=SER)
        print(opt.start_server(opt_server_name, folder_name, warmup=1))
        opt.connect("tcp://{0}:{1}".format(ip_address,  OPT.SERVICE_PORT))
        print('done')
        print(prot['OPT']['pin'], prot['OPT']['blinkinterval'], prot['OPT']['blinkduration'], maxduration)
        opt.setup(prot['OPT']['pin'], maxduration, prot['OPT']['blinkinterval'], prot['OPT']['blinkduration'])
        opt.init_local_logger('{0}/{1}/{1}_opt.log'.format(dirname, filename))

    if 'THUA' in prot['NODE']['use_services']:
        thua_server_name = 'python -m {0} {1}'.format(THUA.__module__, SER)
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
        ptg_server_name = 'python -m {0} {1}'.format(PTG.__module__, SER)
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

    if 'DAQ' in prot['NODE']['use_services']:
        daq_server_name = 'python -m {0} {1}'.format(DAQ.__module__, SER)
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
              maxduration, fs, prot['DAQ']['display'],
              analog_chans_out=prot['DAQ']['analog_chans_out'],
              analog_chans_in=prot['DAQ']['analog_chans_in'],
              digital_chans_out=prot['DAQ']['digital_chans_out'],
              analog_data_out=analog_data,
              digital_data_out=digital_data,
              metadata={'analog_chans_in_info': prot['DAQ']['analog_chans_in_info']})
        daq.init_local_logger('{0}/{1}/{1}_daq.log'.format(daq_save_folder, filename))
        daq.start()
        logging.info('DAQ started')

    if 'CAM' in prot['NODE']['use_services']:
        # make sure 5seconds have elapsed
        while time.time() - cam_start_time <= 5:
            time.sleep(0.01)
        print(f'   {time.time() - cam_start_time:1.4f} seconds elapsed. Ready to start SND and/or OPT.')

    if 'SND' in prot['NODE']['use_services']:
        time0 = time.time()
        snd.start()
        print(f'waited {time.time() - time0:1.4f} seconds.')
        print('   SND started.')
        time0 = time.time()
        while not snd.is_busy():
            time.sleep(0.001)
        print(f'waited {time.time() - time0:1.4f} seconds.')

    if 'OPT' in prot['NODE']['use_services']:
        opt.start()
        print('   OPT started.')

    print('quitting now - protocol will stop automatically on {0}'.format(ip_address))


if __name__ == '__main__':
    ip_address = 'rpi8'
    protocolfilename = 'protocols/default.txt'
    playlistfilename = 'playlists/sine_short.txt'
    clientcaller(ip_address, playlistfilename, protocolfilename)
