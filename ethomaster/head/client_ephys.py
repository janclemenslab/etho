import time
import numpy as np
import subprocess
import defopt
from itertools import cycle
import yaml
import os
import zerorpc

from ethomaster import config
from ethomaster.head.ZeroClient import ZeroClient
from ethomaster.utils.sound import parse_table, load_sounds, build_playlist
from ethomaster.utils.shuffled_cycle import shuffled_cycle
from ethomaster.utils.config import readconfig, saveconfig

from ethoservice.DAQZeroService import DAQ


def clientcc(filename: str, filecounter: int, protocolfile: str, playlistfile: str,
             save: bool=False, shuffle: bool=False, loop: bool=False, selected_stim: int=None):
    # load config/protocols
    print(filename)
    print(filecounter)
    print(protocolfile)
    print(playlistfile)
    print('save:', save)
    print('shuffle:', shuffle)
    print('loop:', loop)
    print('selected stim:', selected_stim)

    if protocolfile.partition('.')[-1] not in ['yml', 'yaml']:
        print(protocolfile.partition('.')[-1])
        raise ValueError('protocol must be a yaml file (end in yml or yaml).')

    prot = readconfig(protocolfile)
    # maxduration = prot['NODE']['maxduration']
    fs = prot['DAQ']['samplingrate']
    SER = prot['NODE']['serializer']
    ip_address = 'localhost'

    daq_server_name = 'python -m {0} {1}'.format(DAQ.__module__, SER)

    # load playlist, sounds, and enumerate play order
    playlist = parse_table(playlistfile)
    if selected_stim:
        playlist = playlist.iloc[selected_stim-1:selected_stim]
    print(playlist)
    sounds = load_sounds(playlist, fs,
                         attenuation=config['ATTENUATION'],
                         LEDamp=prot['DAQ']['led_amp'],
                         stimfolder=config['HEAD']['stimfolder'])
    sounds = [sound.astype(np.float64) for sound in sounds]

    # get digital pattern from analog_data_out - duplicate analog_data_out,
    triggers = list()
    for sound in sounds:
        nb_digital_chans_out = len(prot['DAQ']['digital_chans_out'])
        this_trigger = np.zeros((sound.shape[0], nb_digital_chans_out), dtype=np.uint8)
        this_trigger[:5, 0] = 1  # add trigger at beginning of each trial
        triggers.append(this_trigger.astype(np.uint8))

    maxduration = prot['NODE']['maxduration']
    playlist_items, totallen = build_playlist(sounds, maxduration, fs,
                                              shuffle=prot['DAQ']['shuffle'])
    if maxduration==-1:
        print(f'setting maxduration from playlist to {totallen} seconds.')
        maxduration = totallen + 10.0  # make sure we don't miss the end - will abort earlier anyway
    else:
        print(f'maxduration from protocol is {maxduration} seconds.')
    playlist_items = iter(playlist_items)

    print([DAQ.SERVICE_PORT, DAQ.SERVICE_NAME])
    daq = ZeroClient(ip_address, 'nidaq', serializer=SER)
    sp = subprocess.Popen(daq_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
    daq.connect("tcp://{0}:{1}".format(ip_address, DAQ.SERVICE_PORT))
    print('done')
    print('sending sound data to {0} - may take a while.'.format(ip_address))
    if save:
        filename = os.path.join(prot['NODE']['savefolder'], filename, filename)
        daq_save_filename = '{0}_daq.h5'.format(filename)
    else:
        daq_save_filename = None
    print(daq_save_filename)
    daq.setup(daq_save_filename, playlist_items, playlist,
              maxduration, fs, prot['DAQ']['display'],
              analog_chans_out=prot['DAQ']['analog_chans_out'],
              analog_chans_in=prot['DAQ']['analog_chans_in'],
              digital_chans_out=prot['DAQ']['digital_chans_out'],
              analog_data_out=sounds,
              digital_data_out=triggers,
              metadata={'analog_chans_in_info': prot['DAQ']['analog_chans_in_info']})
    if save:
        daq.init_local_logger('{0}_daq.log'.format(filename))
        # dump protocol file as yaml
        saveconfig('{0}_prot.yml'.format(filename), prot)
        np.save(f'{filename}_sounds.npy', sounds)
    daq.start()
    t0 = time.clock()
    try:
        while daq.is_busy():
            time.sleep(0.5)
            t1 = time.clock()
            print(f'   Busy {t1-t0:1.2f} seconds.\r', end='', flush=True)
    except zerorpc.exceptions.RemoteError as e:
        daq.finish()
    print(f'   Finished after {t1-t0:1.2f} seconds.')
    time.sleep(1)
    # sp.terminate()
    # sp.kill()
    print('DONE.')

if __name__ == '__main__':
    defopt.run(clientcc)
