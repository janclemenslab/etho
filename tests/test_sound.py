import pandas as pd
from etho.utils.sound import parse_table, load_sounds
import matplotlib.pyplot as plt
plt.ion()


def test_playlist():
    for playlistfile in ['tests/test_sound_playlist_mono.txt', 'tests/test_sound_playlist_mirrorled.txt', 'tests/test_sound_playlist_stereo.txt']:
        print(playlistfile)
        df = parse_table(playlistfile, [str, float, float, float, float, float, str])
        playlist = pd.read_table(playlistfile, dtype=None, delimiter='\t')
        df = parse_table(playlist, [str, float, float, float, float, float, str])
        with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.width', 1000):
            print(df)
        sounds = load_sounds(df, fs=10000)
        plt.clf()
        for chn in range(sounds[0].shape[1]):
            plt.subplot(sounds[0].shape[1], 1, chn+1)
            plt.plot(sounds[0][:, chn])
        plt.title(playlistfile)
        plt.show()
        plt.pause(1)
