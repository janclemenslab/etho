import pandas as pd
from etho.utils.sound import parse_table, load_sounds
# import matplotlib.pyplot as plt


def test_playlist():
    # plt.ion()
    for playlistfile in ['tests/test_sound_playlist_mono.txt', 'tests/test_sound_playlist_stereo.txt']:
        print(playlistfile)
        dtypes = [str, float, float, float, float]
        df = parse_table(playlistfile, dtypes)
        playlist = pd.read_table(playlistfile, dtype=None, delimiter='\t')
        df = parse_table(playlist, dtypes)
        with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.width', 1000):
            print(df)
        sounds = load_sounds(df, fs=10000)
        # plt.clf()
        # for chn in range(sounds[0].shape[1]):
        #     plt.subplot(sounds[0].shape[1], 1, chn+1)
        #     plt.plot(sounds[0][:, chn])
        # plt.title(playlistfile)
        # plt.show()
        # plt.pause(1)


def test_parse_table_ignores_unused_playlist_columns():
    playlist = pd.DataFrame(
        {
            "stimFileName": ["SIN_100_0_3000"],
            "silencePre": [1000],
            "silencePost": [1000],
            "unused": [0],
            "intensity": [1.0],
            "freq": [100],
            "also_unused": [None],
        }
    )

    parsed = parse_table(playlist)

    assert list(parsed.columns) == ["stimFileName", "silencePre", "silencePost", "intensity", "freq"]
    assert parsed.loc[0, "stimFileName"] == ["SIN_100_0_3000"]
    assert parsed.loc[0, "intensity"] == [1.0]


def test_parse_table_accepts_quoted_bracketed_stimulus_name():
    playlist = pd.DataFrame(
        [["['SIN_100_0_3000']", 1000, 1000, 1.0, 100]],
        columns=["stimFileName", "silencePre", "silencePost", "intensity", "freq"],
    )

    assert parse_table(playlist).loc[0, "stimFileName"] == ["SIN_100_0_3000"]
