# LED Calibration

LED calibration is rig-specific. The goal is to map playlist `intensity` values
to the optical output units used by the lab, then record the mapping in the rig
configuration or analysis notes.

## Recommended Record

For each calibrated LED path, record:

- rig name and date
- LED driver model and gain/current or other hardware settings
- DAQ output channel
- measurement sensor and calibration date
- distance and geometry at the sample position
- playlist or script used to drive the LED
- measured output values
- final conversion used for experiment playlists

## Operator Workflow

1. Warm up the light source and measurement device according to local rig practice.
2. Connect the DAQ output to the LED driver input used during experiments.
3. Run a short playlist that steps through the expected intensity range.
4. Measure optical output at the sample position.
5. Update the rig's attenuation/calibration notes.
6. Re-run at the playlist and record the measured value.
