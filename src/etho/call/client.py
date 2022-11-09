import time
import numpy as np
import cv2
import logging
from itertools import cycle
from rich.progress import Progress
import rich
from ..utils.tui import rich_information

from .. import config
from ..utils.config import readconfig, undefaultify
from ..utils.sound import parse_table, load_sounds, build_playlist

from ..services.ThuAZeroService import THUA
from ..services.DAQZeroService import DAQ
from ..services.GCMZeroService import GCM


import threading
import _thread as thread
import defopt
from typing import Optional


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


def clientcaller(host: str, protocolfile: str, playlistfile: Optional[str] = None, *, save_prefix: Optional[str] = None, show_test_image: bool = False):
    """_summary_

    Args:
        host (str): _description_
        protocolfile (str): _description_
        playlistfile (Optional[str]): _description_.
        save_prefix (Optional[str]): _description_.
        show_test_image (bool): _description_.
    """
    # load config/protocols
    prot = readconfig(protocolfile)
    logging.debug(prot)

    defaults = config['GENERAL']
    defaults.update(prot['NODE'])
    defaults['host'] = host
    rich.print(defaults)
    # unique file name for video and node-local logs
    if save_prefix is None:
        save_prefix = f"{defaults['host']}-{time.strftime('%Y%m%d_%H%M%S')}"
    logging.info(f"Saving as {save_prefix}.")


    services = {}
    if 'THUA' in prot['NODE']['use_services']:
        this = defaults.copy()
        # update `this`` with service specific host params
        if 'host' in prot['THUA']:
            this.update(prot['THUA']['host'])
        thua = THUA.make(this['serializer'], this['user'], this['host'], this['working_directory'], this['python_exe'])
        thua.setup(prot['THUA']['port'], prot['THUA']['interval'], this['maxduration'] + 10)
        thua.init_local_logger('{0}/{1}/{1}_thu.log'.format(this['save_directory'], save_prefix))
        thua.start()
        services['THUA'] = thua

    if 'GCM' in prot['NODE']['use_services'] and 'GCM' in prot:
        this = defaults.copy()
        # update `this` with service specific host params
        host_is_remote = False
        if 'host' in prot['GCM']:
            this.update(prot['GCM']['host'])
            host_is_remote = True
        gcm = GCM.make(this['serializer'], this['user'], this['host'], this['working_directory'], this['python_exe'],
                       host_is_remote=host_is_remote, new_console=False)
        cam_params = undefaultify(prot['GCM'])
        gcm.setup(f"{this['save_directory']}/{save_prefix}/{save_prefix}", this['maxduration'] + 20, cam_params)
        gcm.init_local_logger('{0}/{1}/{1}_gcm.log'.format(this['save_directory'], save_prefix))
        if show_test_image:
            img = gcm.attr('test_image')
            print('Press any key to continue.')
            cv2.imshow('Test image. Are you okay with this?', img)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            cv2.waitKey(1)  # second call required for window to be closed on mac
        gcm.start()
        services['camera'] = gcm

    if 'DAQ' in prot['NODE']['use_services']:
        this = defaults.copy()
        # update `this`` with service specific host params
        if 'host' in prot['GCM']:
            this.update(prot['GCM']['host'])

        fs = prot['DAQ']['samplingrate']
        playlist = parse_table(playlistfile)

        if this['host'] in config['ATTENUATION']:  # use node specific attenuation data
            attenuation = config['ATTENUATION'][this['host']]
            logging.info(f"Using attenuation data specific to {this['host']}.")
        else:
            attenuation = config['ATTENUATION']

        sounds = load_sounds(playlist,
                             fs,
                             attenuation=attenuation,
                             LEDamp=prot['DAQ']['ledamp'],
                             stimfolder=config['HEAD']['stimfolder'])
        sounds = [sound.astype(np.float64) for sound in sounds]
        playlist_items, totallen = build_playlist(sounds, this['maxduration'], fs, shuffle=prot['DAQ']['shuffle'])
        if this['maxduration'] == -1:
            logging.info(f"Setting maxduration from playlist to {totallen}.")
            this['maxduration'] = totallen
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

        daq = DAQ.make(this['serializer'], this['user'], this['host'], this['working_directory'], this['python_exe'])

        daq_params = undefaultify(prot['DAQ'])
        daq.setup('{0}/{1}/{1}'.format(this['save_directory'], save_prefix),
                  playlist_items,
                  playlist,
                  this['maxduration'],
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
        daq.init_local_logger(f"{this['save_directory']}/{save_prefix}/{save_prefix}_daq.log")

        if 'gcm' in services:
            while services['gcm'].progress()['elapsed'] < 5:
                time.sleep(.1)
                print(f"\rWaiting for camera {services['gcm'].progress()['elapsed']: 2.1f}/5.0 seconds", end='', flush=True)
            print('\n')

        daq.start()
        services['daq'] = daq

    for key, s in services.items():
        rich_information(s.information(), prefix=key)

    with Progress() as progress:
        tasks = {}
        for key, s in services.items():
            tasks[key] = progress.add_task(f"[red]{key}", total=s.progress()['total'])

        while not progress.finished:
            for key, task_id in tasks.items():
                if progress._tasks[task_id].finished:
                    continue
                try:
                    p = timed(services[key].progress, 5)
                    description = None
                    if 'framenumber' in p:
                        description = f"{key} {p['framenumber_delta'] / p['elapsed_delta']: 7.2f} fps"
                    progress.update(task_id, completed=p['elapsed'], description=description)
                except:  # if call times out, stop progress display - this will stop the display whenever a task times out - not necessarily when a task is done
                    progress.stop_task(task_id)
            time.sleep(1)
    logging.info(f"Done with experiment {save_prefix}.")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    defopt.run(clientcaller)
