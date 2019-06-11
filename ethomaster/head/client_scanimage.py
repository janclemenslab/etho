import time
import numpy as np
import subprocess
import defopt
from itertools import cycle
import yaml

from ethomaster import config
from ethomaster.head.ZeroClient import ZeroClient
from ethomaster.utils.sound import parse_table, load_sounds, build_playlist
from ethomaster.utils.shuffled_cycle import shuffled_cycle
from ethomaster.utils.config import readconfig, saveconfig

from ethoservice.DAQZeroService import DAQ
from ethoservice.PTGZeroService import PTG
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
    #
    nb_digital_chans_out = len(prot['DAQ']['digital_chans_out'])
    nb_analog_chans_out = len(prot['DAQ']['analog_chans_out'])
    triggers = list()
    for cnt, sound in enumerate(sounds):
        this_trigger = np.zeros((sound.shape[0], nb_digital_chans_out), dtype=np.uint8)
        this_trigger[:5, 2] = 1  # add NEXT trigger at beginning of each sound,
        if len(triggers) == 0:  # add START trigger to beginning of FIRST sound
            this_trigger[:5, 0] = 1
        if len(triggers) == len(sounds):  # add STOP trigger at end of last sound
            this_trigger[-5:, 1] = 1
        # split off trailing digital channels and cast to uint8?
        for chn in range(3, nb_digital_chans_out):
            this_trigger[:, chn] = sound[:, nb_analog_chans_out + chn - 3]
        triggers.append(this_trigger.astype(np.uint8))
        sounds[cnt] = sound[:, :nb_analog_chans_out]

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

    # SETUP CAM
    if 'PTG' in prot['NODE']['use_services']:
        ptg_server_name = 'python -m {0} {1}'.format(PTG.__module__, SER)
        print([PTG.SERVICE_PORT, PTG.SERVICE_NAME])
        ptg = ZeroClient(ip_address, 'ptgcam', serializer=SER)
        ptg_sp = subprocess.Popen(ptg_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
        ptg.connect("tcp://{0}:{1}".format(ip_address, PTG.SERVICE_PORT))
        print('done')
        cam_params = dict(prot['PTG'])
        ptg.setup(filename, -1, cam_params)
        ptg.init_local_logger('{0}_ptg.log'.format(filename))

    # SETUP DAQ
    print([DAQ.SERVICE_PORT, DAQ.SERVICE_NAME])
    daq_server_name = 'python -m {0} {1}'.format(DAQ.__module__, SER)
    daq = ZeroClient(ip_address, 'nidaq', serializer=SER)
    daq_sp = subprocess.Popen(daq_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)

    daq.connect("tcp://{0}:{1}".format(ip_address, DAQ.SERVICE_PORT))
    print('done')
    print('sending sound data to {0} - may take a while.'.format(ip_address))
    if save:
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

    # START PROCESSES
    if 'PTG' in prot['NODE']['use_services']:
        ptg.start()
    daq.start()

    # MONITOR PROGRESS
    t0 = time.clock()
    while daq.is_busy(ai=True, ao=False):
        time.sleep(0.5)
        t1 = time.clock()
        print(f'   Busy {t1-t0:1.2f} seconds.\r', end='', flush=True)
    print(f'   Finished after {t1-t0:1.2f} seconds.')
    # send STOP trigger
    print(f'   DAQ finished after {t1-t0:1.2f} seconds')
    time.sleep(2)  # wait for daq process to free resources
    trigger('STOP')
    print('    sent STOP to scientifica')

    # STOP PROCESSES
    if 'PTG' in prot['NODE']['use_services']:
        print('    terminate PTG process')
        ptg.finish(stop_service=True)


if __name__ == '__main__':
    defopt.run(clientcc)
