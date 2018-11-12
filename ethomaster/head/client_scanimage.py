import time
import numpy as np
import pandas as pd
import subprocess
import defopt

from ethomaster import config
from ethomaster.head.ZeroClient import ZeroClient
from ethomaster.utils.sound import *
from ethomaster.utils.config import readconfig
from ethoservice.DAQZeroService import DAQ
from ethoservice.NITriggerZeroService import NIT


def trigger(trigger_name):
    ip_address = 'localhost'
    port = "/Dev1/port0/line1:3"
    trigger_types = {'START': [1, 0, 0],
                     'STOP': [0, 1, 0],
                     'NEXT': [0, 0, 1],
                     'NULL': [0, 0, 0]}
    print([NIT.SERVICE_PORT, NIT.SERVICE_NAME])
    nit = ZeroClient("{0}".format(ip_address), 'nidaq')
    try:
        sp = subprocess.Popen('python -m ethoservice.NITriggerZeroService')
        nit.connect("tcp://{0}:{1}".format(ip_address, NIT.SERVICE_PORT))
        print('done')
        nit.setup(-1, port)
        # nit.init_local_logger('{0}/{1}_nit.log'.format(dirname, filename))
        print('sending START')
        nit.send_trigger(trigger_types[trigger_name])
    except:
        pass
    nit.finish()
    nit.stop_server()
    del(nit)
    sp.terminate()
    sp.kill()


def clientcc(filename: str, filecounter: int, protocolfile: str, playlistfile: str, save: bool=False):
    # load config/protocols
    print(filename)
    print(filecounter)
    print(protocolfile)
    print(playlistfile)
    print(save)
    prot = readconfig(protocolfile)
    maxDuration = int(prot['NODE']['maxduration'])
    user_name = prot['NODE']['user']
    folder_name = prot['NODE']['folder']

    ip_address = 'localhost'

    # unique file name for video and node-local logs
    # if filename is None:
    #     filename = '{0}-{1}'.format(ip_address, time.strftime('%Y%m%d_%H%M%S'))
    # dirname = prot['NODE']['savefolder']
    print(filename)

    # SETUP TRIGGER
    trigger('START')
    print('sent START')
    daq_server_name = 'python -m {0}'.format(DAQ.__module__)
    daq_service_port = DAQ.SERVICE_PORT

    fs = int(prot['DAQ']['samplingrate'])
    shuffle_playback = eval(prot['DAQ']['shuffle'])
    # load playlist, sounds, and enumerate play order
    playlist = pd.read_table(playlistfile, dtype=None, delimiter='\t')
    sounds = load_sounds(playlist, fs, attenuation=config['ATTENUATION'],
                LEDamp=prot['DAQ']['ledamp'], stimfolder=config['HEAD']['stimfolder'],
                mirrorsound=True, cast2int=False)
    playlist_items, totallen = build_playlist(sounds, maxDuration, fs, shuffle=shuffle_playback)
    if maxDuration == -1:
        print(f'setting maxduration from playlist to {totallen}.')
        maxDuration = totallen

    if not isinstance(prot['DAQ']['channels_in'], list):
        prot['DAQ']['channels_in'] = [prot['DAQ']['channels_in']]
    if not isinstance(prot['DAQ']['channels_out'], list):
        prot['DAQ']['channels_out'] = [prot['DAQ']['channels_out']]

    # send START trigger here
    print([DAQ.SERVICE_PORT, DAQ.SERVICE_NAME])
    daq = ZeroClient("{0}@{1}".format(user_name, ip_address), 'nidaq')
    # print(daq.start_server(daq_server_name, folder_name, warmup=1))
    sp = subprocess.Popen(daq_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
    daq.connect("tcp://{0}:{1}".format(ip_address, daq_service_port))
    print('done')
    print('sending sound data to {0} - may take a while.'.format(ip_address))
    if save:
        daq_save_filename = '{0}_daq_test.h5'.format(filename)
    else:
        daq_save_filename = None
    daq.setup(daq_save_filename, sounds, playlist.to_msgpack(), playlist_items, maxDuration, fs, prot['DAQ'])
    if save:
        daq.init_local_logger('{0}_daq.log'.format(filename))
    # NEXTFILE triggers should be sent during playback
    daq.start()

    while daq.is_busy():
        time.sleep(1)
        print('\rbusy')
    # send STOP trigger here
    trigger('STOP')
    print('sent STOP')

    sp.terminate()
    sp.kill()


if __name__ == '__main__':
    defopt.run(clientcc)
