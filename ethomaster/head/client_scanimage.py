import time
import numpy as np
import subprocess
import defopt
from itertools import cycle

from ethomaster import config
from ethomaster.head.ZeroClient import ZeroClient
from ethomaster.utils.sound import parse_table, load_sounds, build_playlist
from ethomaster.utils.shuffled_cycle import shuffled_cycle
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
    except Exception as e:
        print(e)
    nit.finish()
    nit.stop_server()
    del(nit)
    sp.terminate()
    sp.kill()


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
        raise ValueError('protocol must be a yaml file (end in yml or yaml).')

    prot = readconfig(protocolfile)
    # maxduration = prot['NODE']['maxduration']
    fs = prot['DAQ']['samplingrate']
    SER = prot['NODE']['serializer']
    ip_address = 'localhost'
    trigger('START')
    print('sent START')

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
    maxduration = -1
    playlist_items, totallen = build_playlist(sounds, maxduration, fs,
                                              shuffle=prot['DAQ']['shuffle'])

    # get digital pattern from analog_data_out - duplicate analog_data_out,
    triggers = list()
    for sound in sounds:
        nb_digital_chans_out = len(prot['DAQ']['digital_chans_out'])
        this_trigger = np.zeros((sound.shape[0], nb_digital_chans_out), dtype=np.uint8)
        this_trigger[:5, 2] = 1  # add NEXT trigger at beginning of each sound,
        if len(triggers) == len(sounds):  # add STOP trigger at end of last sound
            this_trigger[-5:, 1] = 1
        triggers.append(this_trigger.astype(np.uint8))

    if not loop:
        print(f'setting maxduration from playlist to {totallen}.')
        maxduration = totallen
    else:
        print(f'endless playback.')
        maxduration = -1

    if shuffle:
        playlist_items = shuffled_cycle(playlist_items, shuffle='block')  # iter(playlist_items)
    else:
        playlist_items = cycle(playlist_items)  # iter(playlist_items)
    print([DAQ.SERVICE_PORT, DAQ.SERVICE_NAME])
    daq = ZeroClient(ip_address, 'nidaq', serializer=SER)
    sp = subprocess.Popen(daq_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
    daq.connect("tcp://{0}:{1}".format(ip_address, DAQ.SERVICE_PORT))
    print('done')
    print('sending sound data to {0} - may take a while.'.format(ip_address))
    if save:
        daq_save_filename = '{0}_daq_test.h5'.format(filename)
    else:
        daq_save_filename = None
    print(daq_save_filename)
    daq.setup(daq_save_filename, playlist_items, playlist,
              maxduration, fs, prot['DAQ']['display'],
              analog_chans_out=prot['DAQ']['analog_chans_out'],
              analog_chans_in=prot['DAQ']['analog_chans_in'],
              digital_chans_out=prot['DAQ']['digital_chans_out'],
              analog_data_out=sounds,
              digital_data_out=triggers)
    if save:
        daq.init_local_logger('{0}_daq.log'.format(filename))

    daq.start()
    t0 = time.clock()
    while daq.is_busy():
        time.sleep(1)
        t1 = time.clock()
        print(f'   Busy {t1-t0:1.2f} seconds.\r', end='', flush=True)
    # send STOP trigger here
    time.sleep(1)
    trigger('STOP')
    print('sent STOP')

    sp.terminate()
    sp.kill()


if __name__ == '__main__':
    defopt.run(clientcc)
