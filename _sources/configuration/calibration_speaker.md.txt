# Speaker Calibration

Speaker calibration sets the attenuation values used when Etho loads playlist
stimuli. The goal is that playlist `intensity` values correspond to the sound
unit convention used by the rig.

## Hardware Setup

1. Place the microphone at the animal position.
2. Record the distance and geometry relative to the speaker.
3. Connect the microphone amplifier output to a DAQ analog input.
4. Use the same playback output path and amplifier settings used during experiments.
5. Record the microphone calibration file, date, and gain settings.

## Run Calibration Stimuli

Use a calibration playlist that covers the frequency and intensity range needed
for experiments. During the run, save:

- raw microphone recording
- protocol file
- playlist file
- current `ethoconfig.yml`
- microphone calibration metadata
- rig name and date

## Analyze And Update

Analyze the recorded response to calculate attenuation factors for the
frequencies used in playlists. Store the resulting mapping in
`~/ethoconfig/ethoconfig.yml` under `ATTENUATION`.

Example:

```yaml
ATTENUATION:
  -1: 1
  100: 0.82
  150: 0.77
  200: 0.74
```

After updating attenuation, run a validation playlist and confirm the measured
output matches the target within the tolerance used by the rig.

## Suggested File Layout

```text
playback/
  calibration/
    mic_calibration/
      mic_calibration_YYYYMMDD.yml
    YYYYMMDD/
      rig_name_before.csv
      ethoconfig_rig_name_before.yml
      rig_name_after.csv
      ethoconfig_rig_name_after.yml
      figures/
```

Keep enough metadata with the calibration data that another operator can repeat
or audit the calibration later.
