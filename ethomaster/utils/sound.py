import numpy as np
import pandas as pd
import scipy.io.wavfile as wav
import scipy.signal


def make_sine(frequency, phase, duration, samplingrate):
    """make sinusoidal from parameters
    Args:
    frequency [Hz], phase [pi], duration [ms], samplingrate [Hz]
    """
    t = np.arange(0, duration / 1000, 1 / samplingrate)
    x = np.sin(2 * np.pi * t * frequency + phase)
    return x


def make_pulse(pulseDur, pulsePau, pulseNumber, pulseDelay, samplingrate):
    """make square pulse train
    Args:
    pulseDur [ms], pulsePau [ms], pulseNumber, pulseDelay [ms], samplingrate [Hz]
    """
    # NOT TESTED
    x = np.concatenate((np.ones((np.intp(samplingrate * pulseDur / 1000),)),
                        np.zeros((np.intp(samplingrate * pulsePau / 1000),))))
    x = np.tile(x, (np.intp(pulseNumber),))
    x = np.concatenate((np.ones((np.intp(samplingrate * pulseDelay / 1000),)), x))
    return x


def build_playlist(soundlist, duration, fs, shuffle=True):
    """block-shuffle playlist and concatenate to duration"""
    totallen = 0
    playlist_items = list()
    while totallen < duration:
        if shuffle:
            # cast to int - otherwise fails since msgpack can't serialize numpy arrays
            next_item = int(np.random.permutation(len(soundlist))[0])
        else:
            next_item = len(playlist_items)%len(soundlist)
        playlist_items.append(next_item)
        totallen += len(soundlist[playlist_items[-1]])/fs
    return playlist_items


def attenuate(sounds, frequencies, attenuationfactors):
    # sounds = [sound = sound * attenuationfactors[str(frequency)] for sound, frequency in zip(sounds, frequencies)]
    for idx, sound in enumerate(sounds):
        sounds[idx] = sound * float(attenuationfactors[str(frequencies[idx])])
    return sounds


def load_sounds(playlist, fs, mirrorsound=True, attenuation=None, LEDamp=250):
    # load_sounds(playlist, fs, mirrorsound=True, attenuation=None, LEDamp=250)
    # attenuation should be dict with string freq values as keys and attenuation values as value
    # LEDamp should be 1 with DAQ
    sounddata = list()
    for name, listitem in playlist.iterrows():
        x = np.zeros((0,1))
        if listitem.stimFileName[:3] == 'SIN':  # SIN_FREQ_PHASE_DURATION
            # print('sine')
            token = listitem.stimFileName[4:].split('_')
            token = [float(item) for item in token]
            freq, phase, duration = token[:3]
            x = make_sine(freq, phase, duration, fs)
        elif listitem.stimFileName[:3] == 'PUL':  # PUL_DUR_PAU_NUM_DEL
            # print('pulse')
            token = listitem.stimFileName[4:].split('_')
            token = [float(item) for item in token]
            pulsedur, pulsepause, pulsenumber, pulsedelay = token[:4]
            x = make_pulse(pulsedur, pulsepause, pulsenumber,
                           pulsedelay, fs)
        else:  # other
            # return time x channels
            wav_rate, x = wav.read(listitem.stimFileName + ".wav")
            # x = x.astype(np.float32)/32768 # NEEDED ONLY WHEN USING DAQ? OR ALWAYS??

            if wav_rate!=fs:  # resample to fs
                x = scipy.signal.resample(x, np.intp(x.shape[0]/wav_rate*fs), axis=0)

        # if `attenuation` arg is provided:
        if attenuation:
            x = x * float(attenuation[str(listitem.freq)])

        # set_volume
        x = x * listitem.intensity * 20 # "* 20" NOT USED FOR DAQ

        # pre/post pend silence
        sample_start = np.intp(listitem.silencePre / 1000 * fs)
        sample_end = np.intp(listitem.silencePost / 1000 * fs)
        sample_sound = x.shape[0]

        x = np.insert(x, 0, np.zeros((sample_start,)))
        x = np.insert(x, x.shape[0], np.zeros((sample_end,)))

        x = x.reshape((x.shape[0], 1))
        xLED = np.zeros(x.shape)  # second channel is all zeros unless we mirrorsound
        print(x.shape)
        if mirrorsound:
            # copy channel for led
            # duration of the LED pattern at least 100ms if possible so it registers in video
            minLEDduration = 3000 / 1000 * fs  # at least 100ms
            # set to minimal duration
            LEDduration = np.max((sample_sound, minLEDduration))
            # prevent overflow (if 100ms exceeds duration of sound)
            LEDduration = np.min((xLED.shape[0]-sample_start, LEDduration))
            # parameters of the LED pattern
            pdur = 5  # ms
            ppau = 5  # ms
            pdel = 0  # ms
            LEDpattern = make_pulse(pdur, ppau, LEDduration/(pdur+ppau)/fs*1000, pdel, fs)
            xLED[sample_start:sample_start+LEDpattern.shape[0],0] = (LEDpattern-0.5) * LEDamp
        x = np.concatenate((x, xLED), axis=1)  # add LED trace as second channel
        sounddata.append(x.astype(np.int16).tolist())
    return sounddata
