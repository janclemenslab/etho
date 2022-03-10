from typing import Callable, List, Union, Dict
import os
import random
import numpy as np
import pandas as pd
import scipy.io.wavfile as wav
import scipy.signal
import h5py


def parse_cell(cell, dtype: Callable=None) -> List:
    """Cast cell to desired type and wrap into list."""
    if isinstance(cell, str):
        cell = cell.strip()
        token = cell.lstrip('[').rstrip(']').split(',')
        token = [tok.strip() for tok in token]
        if dtype:
            token = [dtype(tok) for tok in token]
    else:
        token = [cell]
    return token


def parse_table(table: Union[pd.DataFrame, str],
                dtypes: List[Callable] = [str, float, float, float, float, float, str],
                normalize: bool = True) -> pd.DataFrame:
    """Parse table to desired types.

    Args:
        table - either string (filepath pointing to playlist file) or dataframe
        dtypes - types each col to cast to - methods which return the desired type
    Returns:
        table (dataframe)
    """
    if isinstance(table, str):
        table = pd.read_table(table, dtype=None, delimiter='\t')
    tb = table.values
    for row, row_values in enumerate(tb):
        for col, cell in enumerate(row_values):
            tb[row, col] = parse_cell(cell, dtypes[col])
    df = pd.DataFrame(tb, columns=table.columns)
    if normalize:
        df = normalize_table(df)
    return df


def normalize_table(table: pd.DataFrame) -> pd.DataFrame:
    """Make sure each cell in a row has one entry for stimFileName.

    E.g. if two stimFileName but only one intensity, will duplicate the intensity entries.
    """
    # strict - throw error in case of inconsistencies
    tb = table.values
    for row, row_values in enumerate(tb):
        nchans = len(row_values[0])         # 1. get n stim channels from len(stimFileName)
        for col, cell in enumerate(row_values[1:]):
            if len(cell) < nchans:
                tb[row, col + 1] = [cell[0]] * nchans        # 2. fill remaining cols to match len(stimFileName)
    df = pd.DataFrame(tb, columns=table.columns)
    return df


def select_channels_from_playlist(playlist: pd.DataFrame, channels_to_keep: List[str]):
    """[summary]
    
    Args:
        playlist (pd.DataFrame): [description]
        channels_to_keep (List[str]): [description]
    
    Returns:
        pd.DataFrame: playlist with selected channels
    """
    playlist_new = playlist.copy()
    for col_name, col_data in playlist_new.iteritems():
        for row_name, row_data in col_data.iteritems():
            if isinstance(row_data, (list, tuple)):
                # playlist_new.set_value(row_name, col_name, [row_data[channel] for channel in channels_to_keep])
                playlist_new.at[row_name, col_name] = [row_data[channel] for channel in channels_to_keep]
            if isinstance(row_data, np.ndarray):
                # playlist_new.set_value(row_name, col_name, np.array(row_data)[channels_to_keep])
                playlist_new.at[row_name, col_name] = np.array(row_data)[channels_to_keep]
    return playlist_new


def parse_pulse_parameters(playlist, sounds, fs):
    """[summary]

    Args:
        playlist ([type]): [description]
        sounds ([type]): list of np.arrays, the length of which  determines the trial period
        fs (float): sampling rate for translating nb_samples in sounds to seconds
    
    Returns:
        [type]: [description]
    """
    
    nb_led = len(playlist.stimFileName[0]) # max over rows of len(stimFileNames) - 2
    blink_durs = np.zeros((nb_led, ), dtype=np.int)
    blink_paus = np.zeros_like(blink_durs)
    blink_nums = np.zeros_like(blink_durs)
    blink_dels = np.zeros_like(blink_durs)
    blink_amps = np.zeros_like(blink_durs)
    pulse_params = pd.DataFrame(columns=['duration', 'pause', 'number', 'delay', 'amplitude', 'trial_period'],
                                dtype=object)
    for index, row in playlist.iterrows():
        
        for stim_num, stim_amp in enumerate(row.intensity):
            blink_amps[stim_num] = stim_amp
        pulse_params.loc[index, 'amplitude'] = row.intensity

        for stim_num, stim in enumerate(row.stimFileName):
            if stim.startswith('PUL'):
                dur, pau, num, dey = [int(token) for token in stim.split('_')[1:]]
                blink_durs[stim_num], blink_paus[stim_num], blink_nums[stim_num], blink_dels[stim_num] = [int(token) for token in stim.split('_')[1:]]
        pulse_params.loc[index, 'duration'] = blink_durs / 1000
        pulse_params.loc[index, 'pause'] = blink_paus / 1000
        pulse_params.loc[index, 'number'] = blink_nums
        pulse_params.loc[index, 'delay'] = blink_dels / 1000
        pulse_params.loc[index, 'trial_period'] = sounds[index].shape[0] / fs
    return pulse_params


def make_sine(frequency: float, phase: float, duration: float, samplingrate: float) -> np.array:
    """Make sinusoidal from parameters.

    Args:
        frequency [Hz], phase [pi], duration [ms], samplingrate [Hz]
    Returns:
        np.array with stimulus waveform
    """
    t = np.arange(0, duration / 1000, 1 / samplingrate)
    x = np.sin(2 * np.pi * t * frequency + phase)
    return x


def make_pulse(pulseDur: float, pulsePau: float, pulseNumber: float, pulseDelay: float, samplingrate: float) -> np.array:
    """Make square pulse train.

    Args:
        pulseDur [ms], pulsePau [ms], pulseNumber, pulseDelay [ms], samplingrate [Hz]
    Returns:
        np.array with stimulus waveform
    """
    x = np.concatenate((np.ones((np.intp(samplingrate * pulseDur / 1000),)),
                        np.zeros((np.intp(samplingrate * pulsePau / 1000),))))
    x = np.tile(x, (np.intp(pulseNumber),))
    x = np.concatenate((np.ones((np.intp(samplingrate * pulseDelay / 1000),)), x))
    return x


def build_playlist(soundlist: List[np.array], duration: float, fs: float, shuffle=True, sound_order=None):
    """Block-shuffle playlist and concatenate to duration."""
    if sound_order is None:
        sound_order = np.arange(len(soundlist))

    totallen = 0
    if duration > 0:
        playlist_items = list()
        # add sounds to list as long as total duration is shorter than max duration
        while totallen < duration:
            # re-shuffle at the end of each block
            if shuffle and len(playlist_items) % len(sound_order)==0:
                sound_order = np.random.permutation(sound_order)

            next_item = sound_order[len(playlist_items) % len(sound_order)]
            playlist_items.append(next_item)
            totallen += len(soundlist[playlist_items[-1]]) / fs
    elif duration == -1:  # play sound_order once
        if shuffle:
            sound_order = np.random.permutation(sound_order)
        playlist_items = sound_order.tolist()
        
        # get total duration of playlist
        for item in playlist_items:
            totallen += len(soundlist[item]) / fs
    return playlist_items, totallen


def load_sounds(playlist: pd.DataFrame, fs: float, attenuation: Dict[float, float]=None,
                LEDamp: float=1.0, stimfolder: str='./', cast2int: bool=False, aslist: bool=False,
                stim_key: str = 'stimulus'):
    sounddata = []
    for row_name, listitem in playlist.iterrows():
        mirror_led_channel = []
        xx = [None] * len(listitem.stimFileName)
        for stimIdx, stimName in enumerate(listitem.stimFileName):
            x = np.zeros((0, 1))
            if stimName[:3] == 'SIN':  # SIN_FREQ_PHASE_DURATION
                # print('sine')
                token = stimName[4:].split('_')
                token = [float(item) for item in token]
                freq, phase, duration = token[:3]
                x = make_sine(freq, phase, duration, fs)
            elif stimName[:3] == 'PUL':  # PUL_DUR_PAU_NUM_DEL
                # print('pulse')
                token = stimName[4:].split('_')
                token = [float(item) for item in token]
                pulsedur, pulsepause, pulsenumber, pulsedelay = token[:4]
                x = make_pulse(pulsedur, pulsepause, pulsenumber, pulsedelay, fs)
            elif stimName == 'MIRROR_LED':  # this channel contains a pulse train which mirrors the sound from another channel
                mirror_led_channel.append(stimIdx)  # mirror led
            elif stimName.endswith('.wav'):  # WAV file
                # return time x channels
                wav_rate, x = wav.read(os.path.join(stimfolder, stimName))
                x = x.astype(np.float32) / 32768
                if wav_rate != fs:  # resample to fs
                    x = scipy.signal.resample_poly(x, int(fs), int(wav_rate), axis=0)
            elif stimName.endswith('.h5'):  # HDF5 file
                with h5py.File(os.path.join(stimfolder, stimName), 'r') as f:
                    try:
                        x = f[stim_key][:].astype(np.float32)
                    except KeyError as e:
                        print(e)
            # else:
            #     x = None

            # if `attenuation` arg is provided:
            if attenuation:
                x = x * float(attenuation[listitem.freq[stimIdx]])
            # set_volume
            if len(x):
                x = x * float(listitem.intensity[stimIdx])  # "* 20" NOT USED FOR DAQ

                # pre/post pend silence
                sample_start = np.intp(listitem.silencePre[stimIdx] / 1000 * fs)
                sample_end = np.intp(listitem.silencePost[stimIdx] / 1000 * fs)
                sample_sound = x.shape[0]

                x = np.insert(x, 0, np.zeros((sample_start,)))
                x = np.insert(x, x.shape[0], np.zeros((sample_end,)))
                x = x.reshape((x.shape[0], 1))
            xx[stimIdx] = x
        non_mirror_led_chan = [x for x in list(range(len(xx))) if not x in mirror_led_channel][0]
        for chan in mirror_led_channel:
            xLED = np.zeros(xx[non_mirror_led_chan].shape)  # second channel is all zeros unless we mirrorsound
            # copy channel for led
            # duration of the LED pattern at least 100ms if possible so it registers in video
            minLEDduration = 3000 / 1000 * fs  # at least 100ms
            # set to minimal duration
            LEDduration = np.max((sample_sound, minLEDduration))
            # prevent overflow (if 100ms exceeds duration of sound)
            LEDduration = np.min((xLED.shape[0] - sample_start, LEDduration))
            # parameters of the LED pattern
            pdur = 5  # ms
            ppau = 5  # ms
            pdel = 0  # ms
            LEDpattern = make_pulse(pdur, ppau, LEDduration / (pdur + ppau) / fs * 1000, pdel, fs)
            xLED[sample_start:sample_start + LEDpattern.shape[0], 0] = (LEDpattern - 0.5) * float(LEDamp)
            xx[chan] = xLED

        # make sure each channel in xx has the same length
        max_len = max([len(ii) for ii in xx])
        xx = [np.insert(ii, ii.shape[0], np.zeros((max_len - len(ii),))) for ii in xx]
        xx = [x.reshape((x.shape[0], 1)) for x in xx]

        x = np.concatenate(xx, axis=1)
        # TODO: move these backend-specific things out of this function
        if cast2int:  # needed for RPI - gets sound as int16 at max range, do not do this for DAQ!!
            x = x.astype(np.int16)
        if aslist:
            x = x.tolist()
        sounddata.append(x)
    return sounddata
