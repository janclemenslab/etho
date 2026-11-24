# DLP Projector

DLP projector support is rig-specific and depends on optional projector control
software. Treat this page as an operator checklist and validate details on the
rig before running experiments.

## Protocol Shape

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

`warpfile` points to the projector calibration/warp mesh. `runners` define the
visual stimulus objects and timing parameters used by the rig.

## Operator Checklist

- Confirm projector firmware/control software is installed.
- Confirm optional Python dependencies import in the `etho` environment.
- Verify the warp file path from the rig computer.
- Run a short projector-only or camera-projector alignment protocol.
- Save DLP metadata with `savedlp_h5` when the experiment needs frame-level stimulus records.
