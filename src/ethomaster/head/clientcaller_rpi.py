import time
import numpy as np
import pandas as pd
import subprocess
import logging
from itertools import cycle

from ethomaster import config
from ethomaster.head.ZeroClient import ZeroClient
from ethomaster.utils.config import readconfig, undefaultify
from ethomaster.utils.sound import parse_table, load_sounds, build_playlist, select_channels_from_playlist, parse_pulse_parameters

from ethoservice.SndZeroService import SND
from ethoservice.CamZeroService import CAM
from ethoservice.ThuZeroService import THU
from ethoservice.Opt2ZeroService import OPT2
from ethoservice.RelayZeroService import REL

import zmq
import logging
from zmq.log.handlers import PUBHandler
import socket

logging.basicConfig(level=logging.INFO)


def clientcaller(host_name, ip_address, playlistfile, protocolfile, filename=None):


    # setup connection - publish to head_ip via LOGGIN_PORT
    LOGGING_PORT = 4248
    log_level = logging.INFO
    head_ip = 'localhost'
    ctx = zmq.Context()
    ctx.LINGER = 0
    pub = ctx.socket(zmq.PUB)
    pub.connect('tcp://{0}:{1}'.format(head_ip, LOGGING_PORT))
    log = logging.getLogger()
    log.setLevel(log_level)

    # get host name or IP to append to message
    hostname = socket.gethostname()

    prefix = "%(asctime)s.%(msecs)03d {0}@{1}:".format(
        'CC', hostname)
    body = "%(module)s:%(funcName)s:%(lineno)d - %(message)s"
    df = "%Y-%m-%d,%H:%M:%S"
    formatters = {
        logging.DEBUG: logging.Formatter(prefix + body + "\n", datefmt=df),
        logging.INFO: logging.Formatter(prefix + "%(message)s\n", datefmt=df),
        logging.WARN: logging.Formatter(prefix + body + "\n", datefmt=df),
        logging.ERROR: logging.Formatter(prefix + body + " - %(exc_info)s\n", datefmt=df),
        logging.CRITICAL: logging.Formatter(prefix + body + "\n", datefmt=df)}

    # setup log handler which publishe all log messages to the network
    handler = PUBHandler(pub)
    handler.setLevel(log_level)  # catch only important messages
    handler.formatters = formatters
    log.addHandler(handler)

    # load config/protocols
    prot = readconfig(protocolfile)
    log.debug(prot)
    maxduration = prot['NODE']['maxduration']
    user_name = prot['NODE']['user']
    folder_name = prot['NODE']['folder']
    SER = prot['NODE']['serializer']

    # unique file name for video and node-local logs
    if filename is None:
        filename = '{0}-{1}'.format(host_name, time.strftime('%Y%m%d_%H%M%S'))
    dirname = prot['NODE']['savefolder']
    log.info(f'experiment name: {filename}')

    # load playlist
    log.info(f'using playlist: {playlistfile}')
    playlist = parse_table(playlistfile)

    if 'REL' in prot['NODE']['use_services']:
        # rel = start_service(REL, SER, user_name, ip_address, folder_name)
        rel = REL.make(SER, user_name, ip_address, folder_name, remote=True)
        # rel.init_local_logger('{0}/{1}/{1}_rel.log'.format(dirname, filename))
        print(f"   setup with pin {prot['REL']['pin']}, duration {maxduration + 40}")
        rel.setup(prot['REL']['pin'],  maxduration + 40)        
        time.sleep(1)
        print('   starting service:', end='')
        rel.start()
        print(f'success')


    if 'THU' in prot['NODE']['use_services']:
        thu = THU.make(SER, user_name, ip_address, folder_name, remote=True)

        thu.init_local_logger('{0}/{1}/{1}_thu.log'.format(dirname, filename))
        print(f"   setup with pin {prot['THU']['pin']}, interval {prot['THU']['interval']}, duration {maxduration + 20}")
        thu.setup(prot['THU']['pin'], prot['THU']['interval'], maxduration + 20)        
        time.sleep(1)
        print('   starting service:', end='')
        thu.start()
        print(f'success')

    if 'CAM' in prot['NODE']['use_services']:
        cam = CAM.make(SER, user_name, ip_address, folder_name, remote=True)

        cam.init_local_logger('{0}/{1}/{1}_cam.log'.format(dirname, filename))
        cam_params = undefaultify(prot["CAM"])
        if cam_params is None:
            cam_params = {}
        cam.setup('{0}/{1}/{1}.h264'.format(dirname, filename), maxduration + 10, **cam_params)
        time.sleep(1)
        cam.start()
        cam_start_time = time.time()

    if 'SND' in prot['NODE']['use_services']:
        fs = prot['SND']['samplingrate']
        shuffle_playback = prot['SND']['shuffle']

        if host_name in config['ATTENUATION']:  # use node specific attenuation data
            attenuation = config['ATTENUATION'][host_name]
            print(f'using attenuation data specific to {host_name}.')
        else:
            attenuation = config['ATTENUATION']
            print(f'using global attenuation data (for {host_name}).')
        print(attenuation)
        
        channels_to_keep = prot['SND']['playlist_channels']
        print(f"   selecting channels {channels_to_keep} for SND from playlist.")
        sound_playlist = select_channels_from_playlist(playlist, channels_to_keep)

        led_amp = prot['SND']['ledamp']['default']
        if host_name in prot['SND']['ledamp']:
            print(f'using special LEDamp for {host_name}.')
            led_amp = prot['SND']['ledamp'][host_name]

        # get unique playlist rows
        unique_rows = playlist.to_string(header=False,
                        index=False,
                        index_names=False).split('\n')
        unique_rows = [','.join(ele.split()) for ele in unique_rows]
        uni, unique_row_idx, unique_row_inverse = np.unique(unique_rows, return_inverse=True, return_index=True)
   
        # build sound for all unqiue rows in the playlist
        sounds = load_sounds(sound_playlist.iloc[unique_row_idx], fs, attenuation=attenuation,
                             LEDamp=led_amp,
                             stimfolder=config['HEAD']['stimfolder'],
                             cast2int=True)

        # use unique_row_inverse here to build playlist_items as indices into "sounds"
        playlist_items, totallen = build_playlist(sounds, maxduration, fs,
                                                  shuffle=shuffle_playback, 
                                                  sound_order=unique_row_inverse)

        log.info(playlist.iloc[unique_row_idx].iloc[playlist_items])
        
        snd = SND.make(SER, user_name, ip_address, folder_name, remote=True)

        snd.init_local_logger('{0}/{1}/{1}_snd.log'.format(dirname, filename))

        print('sending sound data to {0} - may take a while.'.format(host_name))
        snd.setup(sounds, playlist.iloc[unique_row_idx], playlist_items, totallen, fs)
        print('  Done.')

    if 'OPT2' in prot['NODE']['use_services']:
        channels_to_keep = prot['OPT2']['playlist_channels']
        print(f"   selecting channels {channels_to_keep} for OPT2 from playlist.")
        opto_playlist = select_channels_from_playlist(playlist, channels_to_keep)
        # opto_playlist = select_channels_from_playlist(playlist.iloc[unique_row_idx], channels_to_keep)
        print(f"   parsing pulse parameters from playlist.")
        # opto_playlist.reset_index(inplace=True, drop=True)
        pulse_params = parse_pulse_parameters(opto_playlist, sounds, fs)

        #  H A C K !!!!
        # pulse_params = parse_pulse_parameters(opto_playlist[:len(sounds)], sounds, fs)
        pulse_params = pulse_params.loc[playlist_items, :]
    

        # # scale amp by attenuation values - get wavelength from FREQ field in playlist
        # if ip_address in config['ATTENUATION']:  # use node specific attenuation data
        #     attenuation_led = config['ATTENUATION_LED'][ip_address]
        #     print(f'using LED attenuation data specific to {ip_address}.')
        # else:
        #     attenuation_led = config['ATTENUATION_LED']
        #     print(f'using global LED attenuation data (for {ip_address}).')

        # led_wavelengths = fun(opto_playlist)
        # blink_amps_scaled = []
        # for blink_amp, led_wavelength in zip(blink_amps, led_wavelengths):
        #     blink_amps_scaled.append(blink_amp * led_wavelength)
        # blink_amps = blink_amps_scaled


        blink_durs = pulse_params.duration.tolist()
        blink_paus = pulse_params.pause.tolist()
        blink_nums = pulse_params.number.tolist()
        blink_dels = pulse_params.delay.tolist()
        blink_amps = pulse_params.amplitude.tolist()
        blink_pers = pulse_params.trial_period.tolist()
        print(pulse_params)
        print(blink_amps)

        opt2 = OPT2.make(SER, user_name, ip_address, folder_name, remote=True)
        
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
    host_name = 'rpi9'
    ip_address = '192.168.1.9'
    # protocolfilename = '../ethoconfig/protocols/cop_40min.yml'
    protocolfilename = '../ethoconfig/protocols/_cop_test.yml' #10min.yml'
    
    # playlistfilename = 'C:/Users/ncb/ethoconfig/playlists/IPI36_20s2min_test.txt'
    playlistfilename = '../ethoconfig/playlists/mini_test_2022.txt' #cop_IPI36_1s_10min.txt'
    clientcaller(host_name, ip_address, playlistfilename, protocolfilename)


