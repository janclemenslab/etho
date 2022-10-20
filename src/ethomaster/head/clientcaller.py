import time
import numpy as np
import pandas as pd
import subprocess
import logging
import rich
from itertools import cycle
from rich.progress import Progress

from ethomaster import config
from ethomaster.head.ZeroClient import ZeroClient
from ethomaster.utils.config import readconfig, undefaultify
from ethomaster.utils.sound import parse_table, load_sounds, build_playlist

from ethoservice.ThuAZeroService import THUA
from ethoservice.DAQZeroService import DAQ
from ethoservice.GCMZeroService import GCM


import threading
import _thread as thread
import sys


def timed(fn, s, *args, **kwargs):
    quit_fun = thread.interrupt_main  # raises KeyboardInterrupt
    timer = threading.Timer(s, quit_fun)
    timer.start()
    try:
        result = fn(*args, **kwargs)
    except:  # catch KeyboardInterrupt for silent timeouts
        result = 1
    finally:
        timer.cancel()
    return result


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
        python_exe = config['GENERAL']['python_exe']
    else:
        python_exe = 'C:/Users/ncb.UG-MGEN/miniconda3/python.exe'

    services = {}
    if 'THUA' in prot['NODE']['use_services']:
        thua = THUA.make(SER, user_name, ip_address, folder_name, python_exe)
        print(prot['THUA'])
        thua.setup(prot['THUA']['port'], prot['THUA']['interval'], maxduration + 10)
        thua.init_local_logger('{0}/{1}/{1}_thu.log'.format(dirname, filename))
        thua.start()
        services['THUA'] = thua

    if 'GCM' in prot['NODE']['use_services']:
        gcm = GCM.make(SER, user_name, ip_address, folder_name, python_exe)
        cam_params = undefaultify(prot['GCM'])
        gcm.setup('{0}/{1}/{1}'.format(dirname, filename), maxduration + 20, cam_params)
        gcm.init_local_logger('{0}/{1}/{1}_gcm.log'.format(dirname, filename))
        img = gcm.attr('test_image')
        print('Press any key to continue.')
        import cv2
        cv2.imshow('Are you happy?',img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        gcm.start()
        services['camera'] = gcm

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

        sounds = load_sounds(playlist,
                             fs,
                             attenuation=attenuation,
                             LEDamp=prot['DAQ']['ledamp'],
                             stimfolder=config['HEAD']['stimfolder'])
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
        daq_params = undefaultify(prot['DAQ'])
        daq.setup(daq_save_filename,
                  playlist_items,
                  playlist,
                  maxduration,
                  fs,
                  clock_source=prot['DAQ']['clock_source'],
                  nb_inputsamples_per_cycle=prot['DAQ']['nb_inputsamples_per_cycle'],
                  analog_chans_out=prot['DAQ']['analog_chans_out'],
                  analog_chans_in=prot['DAQ']['analog_chans_in'],
                  digital_chans_out=prot['DAQ']['digital_chans_out'],
                  analog_data_out=analog_data,
                  digital_data_out=digital_data,
                  metadata={'analog_chans_in_info': prot['DAQ']['analog_chans_in_info']},
                  params=daq_params)
        daq.init_local_logger('{0}/{1}/{1}_daq.log'.format(daq_save_folder, filename))
        print('waiting for camera', end='', flush=True)
        while gcm.progress()['elapsed'] < 5:
            time.sleep(1)
            print('.', end='', flush=True)
        print(' done.')
        daq.start()
        # logging.info('DAQ started')
        services['daq'] = daq
    # print('quitting now - protocol will stop automatically on {0}'.format(ip_address))
    with Progress() as progress:
        tasks = {}
        for key, s in services.items():
            tasks[key] = progress.add_task(f"[red]{key}", total=s.progress()['total'])
        # import ipdb;ipdb.set_trace()

        while not progress.finished:
            for key, task_id in tasks.items():
                if progress._tasks[task_id].finished:
                    continue
                try:
                    p = timed(services[key].progress, 5)
                    progress.update(task_id, completed=p['elapsed'])
                except:  # if call times out, stop progress display - this will stop the display whenever a task times out - not necessarily when a task is done
                    progress.stop_task(task_id)
            time.sleep(1)


if __name__ == '__main__':
    ip_address = 'localhost'
    protocolfilename = 'ethoconfig/protocols/mic35mm_5min.yml'
    playlistfilename = 'ethoconfig/playlists/0 silence.txt'
    clientcaller(ip_address, playlistfilename, protocolfilename)
