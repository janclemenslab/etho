# Stimulus playlists

### General format
Playlists are tables saved as tab-delimited text files:

| stimFileName                     | silencePre   | silencePost  | delayPost | intensity  | freq       | MODE |
|----------------------------------|--------------|--------------|-----------|------------|------------|------|
| superstimulus.wav                    | 1000         | 1000         | 0         | 1.0        | 100        |      |
| SIN_100_0_3000                   | 1000         | 1000         | 0         | 1.0        | 100        |      |
| mediocre_stim.wav, MIRROR_LED        | 1000         | 1000         | 0         | 1.0        | 100        |      |
| [PUL_5_10_10_0, SIN_200_0_2000]      | 1000         | 1000         | 0         | 1.0        | 100        |      |
| [SIN_100_0_3000, SIN_200_0_2000] | 1000         | 1000         | 0         | 1.0        | 100        |      |
| [SIN_100_0_3000, SIN_200_0_2000] | [1000, 1000] | [1000, 1000] | [0, 0]    | [1.0, 1.0] | [100, 100] |      |
| [SIN_100_0_3000, SIN_200_0_2000] | [1000, 2000] | [1000, 3000] | [0, 0]    | [1.0, 2.0] | [100, 200] |      |
| [, SIN_200_0_2000] | 1000         | 1000         | 0         | 1.0        | 100        |      |

The first row is a header that contain the following column names:
* `stimFileName`: If not a magic name, full filename (w/ extension but w/o directory). File needs to be single-channel `*.wav`. Currently defined magic names are: `SIN*`, `PUL*`, `MIRROR_LED` (see below for details what these do - typically define on-the-fly generated stimuli).
* `silencePre` (ms): zeros _pre_-pended to the stimulus
* `silencePost` (ms): zeros _post_-pended to the stimulus
* `delayPost` (ms, _unused_):description
* `intensity` (mm/s or dB for sound, mW/mm2 for light): Stimulus intensity.
* `freq` (Hz for sound or nm for light): Used as a key into the attenuation dictionary defined in the global, rig-specific configuration file `ethoconfig.ini`. The frequency specific attenuation value scales the stimulus such that 1V in the stimulus maps to 1 intensity unit.
* `MODE` (_unused_): Can be used to define callbacks.

### Magic stimulus names
- `SIN_frequency_phase_duration`: Generate sinusoid with frequency (Hz), phase (rad), and duration (ms) specified in the stimulus name.
- `PUL_pulseDur_pulsePau_pulseNumber_pulseDelay`: Generate pulse train (square pulses) with pulse duration, pause, numnber and intial delay specified in stimulus name (all time units in ms).
- `MIRROR_LED`: Will mirror the stimulus in the first channel that does not as a pulse train (pdur & ppau 5ms).

### Multi-channel stimulation
- Comma-delimited lists of entries in the table `[stim1, stim2]` (`[...]` not required but should add for readability, whitespace surrounding stimulus names is stripped).
- Duration given by that of the longest stimulus across channels. Shorter stimuli will be filled with zeros to match duration of longest stimulus in the channel set.
- `[,stim2]` defines stimulation in which the first output channels is filled with zeros.
- Remaining columns will be duplicated to at least have same number of elements as stimulus channels. Rows #5 will  be converted implicitly to row #6 - note that this can be problematic if stimuli required different attenuations (e.g. if stimuli on different channels have different frequencies) since the `frequency` field will also be duplicated.


### Parsing
Load the playlist like so:
```python
from ethomaster.utils.sound import parse_table, normalize_table
# returns a raw pandas dataframe
raw_table = pd.read_table(playlistfilename, dtype=None, delimiter='\t')
# casts all cells in the table to lists of the correct type and
parsed_table = parse_table(raw_table, dtypes=[str, float, float, float, float, float, str])
# normalizes all cells in a row to have the same number of entries as there are stimuli
playlist = normalize_table(parsed_table)
```
Or simply `playlist = parse_table(playlistfilename)`.

Sounds can be generated from the playlist via:
```python
from ethomaster.utils.sound import load_sounds
sounds = load_sounds(playlist, fs=1000, attenuation=None, stimfolder='~/stimuli'):
```
This will return a list of multidimensional numpy arrays, one item per row in the playlist file.