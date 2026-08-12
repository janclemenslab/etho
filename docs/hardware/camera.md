# Cameras

Camera acquisition is handled by the `GCM` service. A protocol can use one
camera block or multiple suffixed blocks such as `GCM1` and `GCM2`.

## Supported Backends

`cam_type` selects the backend:

| `cam_type` | Dependency |
|------------|------------|
| `Dummy` | Built in; useful for smoke tests. |
| `Spinnaker` | FLIR Spinnaker SDK and Python bindings. |
| `Basler` | Basler pylon and `pypylon`. |
| `Ximea` | Ximea driver and Python package. |
| `Hamamatsu` | DCAM driver and `pylablib`. |

Run `etho version --debug` on the rig to confirm the expected backend imports.

## Protocol Fields

```yaml
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
```

The service acquires one test image during setup, then applies
`external_trigger` before the experiment starts. If triggering is enabled,
confirm that the camera is armed before the DAQ or counter trigger starts.

## Operator Checklist

- Confirm the camera appears in the vendor tool before starting Etho.
- Match `cam_serialnumber` to the physical camera.
- Validate ROI offsets, width, height, and binning in a short preview run.
- Check exposure and frame rate in the service log after setup.
- For externally triggered cameras, verify trigger polarity and cabling on the rig.
- Run a short saved acquisition and inspect both video and timestamp files.
