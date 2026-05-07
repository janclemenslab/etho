# Tutorial

This tutorial shows the structure of a typical rig run: global configuration,
protocol, playlist, command-line execution, and output inspection. Use the
[quickstart](quickstart.md) first if you only need a hardware-free smoke test.

## Goal

The example rig:

- records camera frames with the `GCM` service
- plays audio and LED stimuli with the `DAQ` service
- records DAQ input channels with `save_h5`
- optionally triggers ScanImage or other downstream devices with digital output channels

Rig-specific wiring, calibration values, and hardware serial numbers must be
validated at the rig before collecting data.

## Prepare the Environment

Install Etho, activate the conda environment, and initialize user files:

```shell
conda activate etho
etho init
etho version --debug
```

Confirm that `etho version --debug` reports support for the hardware used by the
protocol. Missing unrelated SDKs are not a problem.

## Global Configuration

The global file `~/ethoconfig/ethoconfig.yml` stores folder paths and default
runtime settings. A typical file contains:

```yaml
savefolder: /Users/USER/data
python_exe: /Users/USER/miniforge3/envs/etho/bin/python
playlistfolder: /Users/USER/ethoconfig/playlists
protocolfolder: /Users/USER/ethoconfig/protocols
stimfolder: /Users/USER/ethoconfig/stim
ATTENUATION:
  -1: 1
  100: 1
```

Use the Python executable from the same conda environment that will run Etho
services.

## Protocol

Create a protocol such as `~/ethoconfig/protocols/camera_daq.yml`:

```yaml
maxduration: 60
use_services: [GCM, DAQ]

GCM:
  cam_type: Spinnaker
  cam_serialnumber: 30959651
  frame_rate: 100.0
  frame_width: 640
  frame_height: 200
  frame_offx: 78
  frame_offy: 10
  shutter_speed: 5000
  external_trigger: false
  callbacks:
    save_avi:
    save_timestamps:

DAQ:
  samplingrate: 10000
  device: Dev1
  shuffle: false
  clock_source:
  nb_inputsamples_per_cycle:
  analog_chans_in: [ai0, ai1]
  analog_chans_in_info: [speaker_loopback, led_loopback]
  analog_chans_out: [ao0, ao1]
  analog_chans_out_info: [speaker, led]
  digital_chans_out:
  digitial_chans_out_info:
  ledamp: 5
  callbacks:
    save_h5:
```

Use `cam_type: Dummy` for a no-hardware camera test. For multi-camera or
multi-DAQ runs, add suffixed service names such as `GCM1`, `GCM2`, `DAQ1`, and
`DAQ2`, and list those names in `use_services`.

## Playlist

Create a tab-delimited playlist such as
`~/ethoconfig/playlists/sine_led.txt`:

```text
stimFileName	silencePre	silencePost	delayPost	intensity	freq	MODE
[SIN_100_0_1000,MIRROR_LED]	1000	1000	0	[1.0,1.0]	[100,100]
```

The order of entries in `stimFileName` must match the protocol outputs: analog
outputs first, then digital outputs. In this example, the sine stimulus goes to
`ao0` and the mirrored LED pulse train goes to `ao1`.

## Run

From a terminal:

```shell
etho run ~/ethoconfig/protocols/camera_daq.yml ~/ethoconfig/playlists/sine_led.txt --save-prefix rig_test_001
```

For camera alignment:

```shell
etho run ~/ethoconfig/protocols/camera_daq.yml --preview
```

Preview mode is for camera setup only. Use a normal run when you need saved
files, DAQ output, or experiment logs.

## Outputs

Saved files are placed under:

```text
<savefolder>/<save-prefix>/
```

Common files include:

- `<save-prefix>_gcm.log` for camera service logs
- `<save-prefix>_daq.log` for DAQ service logs
- video files from camera callbacks such as `save_avi`
- timestamp files from `save_timestamps`
- HDF5 or Zarr files from DAQ callbacks such as `save_h5` or `save_zarr`

Inspect logs after a rig test before running a full experiment. Camera frame
rate, dropped frames, DAQ channel names, and callback file paths should match
the intended setup.
