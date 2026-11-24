# National Instruments DAQ

The `DAQ` service coordinates analog output, digital output, and analog input
tasks for NI-DAQmx devices.

## Dependencies

Install NI-DAQmx on the Windows rig and ensure `pydaqmx` imports in the `etho`
conda environment:

```powershell
conda activate etho
etho version
```


## Channel Naming

Run `etho hardware` to list the NI-DAQmx device names. Use the reported
`device` value in the `DAQ` block. You can enumerate NI-DAQmx devices via `etho hardware`. The `NIC` and `SIT` services use the same device names in their channel paths. Use NI-MAX to check available channels.

Example protocol fields:

```yaml
DAQ:
  samplingrate: 10000
  device: Dev1
  clock_source:
  nb_inputsamples_per_cycle:
  analog_chans_in: [ai0, ai1]
  analog_chans_in_info: [speaker_loopback, led_loopback]
  analog_chans_out: [ao0, ao1]
  analog_chans_out_info: [speaker, led]
  digital_chans_out: [port0/line1, port0/line2, port0/line3]
  digital_chans_out_info: [si_start, si_stop, si_next]
  callbacks:
    save_h5:
```

Playlist output channels are ordered as all analog outputs first, followed by
digital outputs.

## Clocking

Leave `clock_source` empty for the default AI-synchronized behavior. Use
`OnboardClock` for DAQ devices that cannot use the default trigger/clock setup.
This is a rig-validation item because supported clocking differs across NI
devices.

## Operator Checklist

- Confirm `device` matches NI-MAX.
- Confirm every listed channel exists and is wired to the intended rig signal.
- Record loopbacks for analog outputs when possible.
- Run a short playlist at the intended `samplingrate`.
- Inspect saved HDF5/Zarr files and `_daq.log` before starting a full experiment.
