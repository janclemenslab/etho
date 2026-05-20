# ScanImage

Etho can drive ScanImage acquisition with DAQ digital output triggers generated
from playlist entries.

## ScanImage Setup

Rig-specific settings must be validated locally, but the common setup is:

- enable external triggering in ScanImage
- set acquisition duration or frame count high enough for the Etho-controlled run
- use a rising edge for start triggers
- use falling edges for stop and next-file triggers when that matches the rig wiring
- confirm trigger input channels against the DAQ digital output lines

See the ScanImage trigger documentation for the ScanImage-side controls.

## Etho Protocol

Add digital output channels to the DAQ service:

```yaml
DAQ:
  digital_chans_out: [port0/line1, port0/line2, port0/line3]
  digital_chans_out_info: [si_start, si_stop, si_next]
```

## Playlist Triggers

Add ScanImage trigger entries in the playlist. Digital outputs come after analog
outputs in `stimFileName`.

```text
stimFileName	silencePre	silencePost	intensity	freq
[SIN_100_0_1000,SI_START,SI_STOP,SI_NEXT]	1000	1000	1.0	100
```

Trigger names:

- `SI_START`: start acquisition at the beginning of the trial.
- `SI_NEXT`: advance to the next ScanImage file near the end of each trial.
- `SI_STOP`: stop acquisition near the end of the final trial unless stop triggers are intentionally ignored.

`SI_START`, `SI_NEXT`, and `SI_STOP` are aligned to trial edges, not to
`silencePre` or `silencePost`.
