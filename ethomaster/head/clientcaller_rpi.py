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
from ethoservice.Opt2ZeroService import OPT2
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
        time.sleep(2)
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
            print(f'using global attenuation data (for {ip_address}).')
        print(attenuation)
        
        # do this only for the first two channels - sound and sync LED, all remaining channels are OPTO pins
        # need yo remove these opto channels from the playlist pased to load_sounds
        # sound_playlist.stimFilenames
        sound_playlist = playlist.copy()
        sound_playlist.stimFileName = [stimFileName[:2] for stimFileName in sound_playlist.stimFileName]
        sounds = load_sounds(sound_playlist, fs, attenuation=attenuation,
                             LEDamp=prot['SND']['ledamp'],
                             stimfolder=config['HEAD']['stimfolder'],
                             cast2int=True)
        # do this for all channels - 
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

    if 'OPT2' in prot['NODE']['use_services']:
        # parse playlists

        # extract blink duration, pulse dur/pau/num from the playlist - make list for each trial
        # def name(playlist, playlist_items) -> blink_*:
       
        nb_rows = playlist.shape[0]
        nb_led = len(prot['OPT2']['pin'])   # max over rows of len(stimFileNames) - 2
        blink_durs = np.zeros((nb_rows, nb_led), dtype=np.int)
        blink_paus = np.zeros_like(blink_durs)
        blink_nums = np.zeros_like(blink_durs)
        blink_dels = np.zeros_like(blink_durs)
        blink_amps = np.zeros_like(blink_durs)
        for index, row in playlist.iterrows():
            pdurs, ppaus, pnums, pdels = [],[],[],[]

            for stim_num, stim_amp in enumerate(row.intensity[2:]):
                blink_amps[index, stim_num] = stim_amp
            for stim_num, stim in enumerate(row.stimFileName[2:]):
                if stim.startswith('PUL'):
                    blink_durs[index, stim_num], blink_paus[index, stim_num], blink_nums[index, stim_num], blink_dels[index, stim_num] = [int(token) for token in stim.split('_')[1:]]
        blink_pers = np.array([sound.shape[0] / fs for sound in sounds ]) # determined by sound duration for each trial

        # now make the blink_* lists into np.arrays and create full playlist by using playlist_items as index
        # make this a pd.DataFrame?
        blink_durs = blink_durs[playlist_items, :]/1000
        blink_paus = blink_paus[playlist_items, :]/1000
        blink_nums = blink_nums[playlist_items, :]
        blink_dels = blink_dels[playlist_items, :]/1000
        blink_amps = blink_amps[playlist_items, :]
        blink_pers = blink_pers[playlist_items]
        # blink_params = pd.DataFrame({'duration': blink_durs, 
        #                              'pause': blink_paus,
        #                              'number': blink_nums,
        #                              'delay': blink_dels,
        #                              'amplitude': blink_amps,
        #                              'period': blink_pers})

        opt2_server_name = 'python -m {0} {1}'.format(OPT2.__module__, SER)
        print([OPT2.SERVICE_PORT, OPT2.SERVICE_NAME])
        opt2 = ZeroClient("{0}@{1}".format(user_name, ip_address), 'piopt', serializer=SER)
        # print(opt2.start_server(opt2_server_name, folder_name, warmup=1))
        opt2.connect("tcp://{0}:{1}".format(ip_address,  OPT2.SERVICE_PORT))
        print('done')
        print(*prot['OPT2'], maxduration)
        opt2.setup(prot['OPT2']['pin'], maxduration, blink_pers, blink_durs, blink_paus, blink_nums, blink_dels, blink_amps)
        opt2.init_local_logger('{0}/{1}/{1}_opt2.log'.format(dirname, filename))

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

    if 'OPT2' in prot['NODE']['use_services']:
        opt2.start()
        print('   OPT2 started.')

    print('quitting now - protocol will stop automatically on {0}'.format(ip_address))


if __name__ == '__main__':
    ip_address = 'rpi8'
    protocolfilename = 'protocols/default.txt'
    playlistfilename = 'playlists/sine_short.txt'
    clientcaller(ip_address, playlistfilename, protocolfilename)
