# Stimulus Playlists

Playlists define the trial-level output for the DAQ service. They are
tab-delimited text files.

## Playlist Format

The parser expects these columns in this order:

```text
stimFileName	silencePre	silencePost	intensity	freq
```

Example:

| stimFileName                     | silencePre   | silencePost  | intensity  | freq       |
|----------------------------------|--------------|--------------|------------|------------|
| superstimulus.wav                | 1000         | 1000         | 1.0        | 100        |
| SIN_100_0_3000                   | 1000         | 1000         | 1.0        | 100        |
| [mediocre_stim.wav, MIRROR_LED]  | 1000         | 1000         | 1.0        | 100        |
| [PUL_5_10_10_0, SIN_200_0_2000]  | 1000         | 1000         | 1.0        | 100        |
| [SIN_100_0_3000, SIN_200_0_2000] | [1000, 2000] | [2000, 1000] | [1.0, 2.0] | [100, 200] |

Column meanings:

- `stimFileName`: WAV/HDF5 stimulus filename or a generated stimulus name.
- `silencePre`: Silence before the stimulus, in milliseconds.
- `silencePost`: Silence after the stimulus, in milliseconds.
- `intensity`: Output multiplier. For calibrated sounds or LEDs, use the unit convention established by the rig calibration.
- `freq`: Key into the attenuation table in `ethoconfig.yml`.

Each row defines one trial. The trial duration is `silencePre`, plus the longest
stimulus across output channels, plus `silencePost`. Shorter output channels are
zero-padded to match the longest channel.

(multi-channel)=
## Multi-Channel Stimulation

For multi-channel output, write list values in brackets:

```text
[stim_on_chan1, stim_on_chan2, stim_on_chan3]
```

Channel order follows the DAQ protocol: analog outputs first, then digital
outputs. For example, if the protocol defines two analog outputs and one digital
output, the playlist order is:

```text
[first_analog_output, second_analog_output, digital_output]
```

Other columns may also use bracketed lists, such as `[1.0, 0.5]` for
channel-specific intensity. If a list has fewer entries than `stimFileName`, the
last provided value is repeated for the remaining channels.

(magic)=
## Generated Stimulus Names

Stimulus names can point to files in `stimfolder`, or they can request generated
signals:

- `SIN_frequency_phase_duration`: Generate a sine wave. Frequency is in Hz, phase is in radians, and duration is in milliseconds.
- `PUL_pulseDur_pulsePau_pulseNumber_pulseDelay`: Generate a pulse train. Time fields are in milliseconds.
- `MIRROR_LED`: Generate a pulse train on this channel aligned to another non-`MIRROR_LED` channel. Protocols using this should define `ledamp`.
- `CLOCK_pulseDur_pulsePau`: Generate a continuous clock signal for the full trial.
- `SI_START`: Set the channel high for the first samples of a trial to start ScanImage acquisition.
- `SI_STOP`: Set the channel high near the end of the final trial to stop ScanImage acquisition.
- `SI_NEXT`: Set the channel high near the end of each trial to advance ScanImage files.

`CLOCK`, `SI_START`, `SI_STOP`, and `SI_NEXT` are aligned to the trial edges, not
to `silencePre` or `silencePost`.
