(experimental-protocols)=
# Experimental Protocols

Protocols are YAML files that define the services used for an experiment and
the hardware parameters passed to those services.


## Minimal Camera And DAQ Example

```yaml
maxduration: 90  # duration of the experiment, in seconds
use_services: [GCM, DAQ]  # use the GCM and DAQ services - these need to have blocks below.

GCM:
  cam_type: Spinnaker  # use the spinnaker interface for FLIR cameras
  cam_serialnumber: 30959651  # serial numner of the camera - important if you want to address different cameras attached to the same rig
  frame_rate: 100.0  # fps
  frame_width: 640  # px
  frame_height: 200  # px
  frame_offx: 78  # px
  frame_offy: 10  # px
  shutter_speed: 5000  # us
  callbacks:
    save_avi:
    save_timestamps:

DAQ:
  samplingrate: 10000
  shuffle: true
  analog_chans_in: [ai0, ai1, ai2]
  analog_chans_in_info: [speaker_loopback, led_loopback, microphone]
  analog_chans_out: [ao0, ao1]
  analog_chans_out_info: [speaker, led]
  callbacks:
    save_h5:  # callback accepts no parameters but needs to be delimited with `:`
```


## Top-Level Fields

- `maxduration`: Experiment duration in seconds. Use `-1` to play the playlist once and derive duration from the playlist.
- `use_services`: List of service blocks to start. Examples: `[GCM]`, `[GCM, DAQ]`, `[GCM1, GCM2, DAQ]`. These service names need to have corresponding blocks in the protocol file.
- `serializer`: Optional ZeroRPC serializer. Defaults to `pickle`.


## Shared Service Fields

- `python_exe`: Optional service-level Python executable override. This allows you to run certain services in separate python environments, by providing the environment's python exe.
- `callbacks`: Optional mapping of callback names to callback parameters. Use an empty mapping value when a callback has no parameters.
- `port`: Optional service port override. Defaults are assigned by service type.


## DAQ Service

DAQ service address National Instruments DAQmx compatible devices. The block names must start with `DAQ`. Use suffixes for multiple DAQ services, such as `DAQ1` and `DAQ2`.

DAQ fields:

- `samplingrate`: Sampling rate in Hz.
- `device`: NI device name from NI-MAX. Defaults to `Dev1`.
- `clock_source`: Leave empty for the AI-synchronized default. Use `OnboardClock` for devices that need the onboard clock (some low-level USB boards do not implement the default).
- `nb_inputsamples_per_cycle`: Optional chunk size for analog input callbacks.
- `shuffle`: Block-randomize playlist order. Defaults to `false` (presents stimuli in order).
- `analog_chans_in`: Analog input channels, such as `[ai0, ai1]`.
- `analog_chans_in_info`: Human-readable labels for analog input channels.
- `analog_chans_out`: Analog output channels, such as `[ao0, ao1]`.
- `analog_chans_out_info`: Human-readable labels for analog output channels.
- `digital_chans_out`: Digital output channels, such as `[port0/line1, port0/line2]`.
- `digital_chans_out_info`: Human-readable labels for digital output channels.

Common DAQ callbacks:

- `save_h5`: Save analog input data and metadata to HDF5.
- `save_zarr`: Save analog input data and metadata to Zarr.
- `plot_fast`: Display analog traces with pyqtgraph.
- `plot`: Display analog traces with matplotlib.
- `savedlp_h5`: Save DLP frame/stimulus metadata.


## Camera Service

Camera service block names must start with `GCM`. Use suffixes for multiple
cameras, such as `GCM1` and `GCM2`.

Camera fields:

- `cam_type`: One of `Dummy`, `Spinnaker`, `Basler`, `Ximea`, or `Hamamatsu`.
- `cam_serialnumber`: Camera serial number. The dummy camera accepts arbitrary values.
- `frame_rate`: Requested frame rate in frames per second.
- `frame_width`: ROI width in pixels.
- `frame_height`: ROI height in pixels.
- `shutter_speed`: Exposure time in microseconds for the generic camera service.
- `frame_offx`: ROI x offset in pixels. Defaults to `0`.
- `frame_offy`: ROI y offset in pixels. Defaults to `0`.
- `binning`: Horizontal and vertical binning factor. Defaults to `1`.
- `brightness`: Camera brightness or black level. Defaults to `0`.
- `gamma`: Gamma value. Defaults to `1`.
- `gain`: Digital gain. Defaults to `0`.
- `optimize_auto_exposure`: Run backend-specific auto-exposure optimization before acquisition.
- `external_trigger`: Arm the camera for external triggering after a test image has been acquired.

Common camera callbacks:

- `disp`: Display frames with OpenCV.
- `disp_fast`: Display frames with pyqtgraph.
- `disp_back`: Display a center/back view helper.
- `disp_top`: Display a center/top view helper.
- `save_timestamps`: Save system and camera timestamps.
- `save_avi`: Save video with OpenCV `VideoWriter`.
- `save_ffmpegcv`: Save video with an ffmpegcv backend.
- `save_vidgear`: Save video through VidGear.
- `save_vidgear_round`: Save long videos, chunked into a sequences of individual files using the VidGear output.
- `save_avi_fast`: Save video with the NVIDIA Video Processing Framework.
- `saveimg_h5`: Save frames to HDF5.
- `saveimg_zarr`: Save frames to Zarr.

## GOV Sensor Service

The `GOV` service logs Govee H5075 temperature/humidity BLE advertisements.

```yaml
GOV:
  address: AA:BB:CC:DD:EE:FF
  interval: 60
```

- `address`: Required device address.
- `interval`: Logging interval in seconds. Defaults to `60`.

## DLP Projector Service

DLP support is rig-specific and depends on optional projector software. A
typical block has this shape:

```yaml
DLP:
  warpfile: Z:/Data/projector/warpmesh_1140x912.data
  use_warping: false
  callbacks:
    savedlp_h5:
  runners:
    LED_blinker:
      object: Rect
      led_frame: 360
      led_duration: 180
```

Validate projector dependencies on the rig with `etho version --debug` before
using a DLP protocol.
