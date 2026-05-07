# Callbacks

Callbacks process data produced by services. Camera callbacks receive frames and
timestamps. DAQ callbacks receive analog input chunks and metadata. Use
callbacks to save data, display live previews, or stream derived information.

## Protocol Syntax

Callbacks are configured under a service block:

```yaml
GCM:
  callbacks:
    save_avi:
    save_timestamps:
    disp_fast:
      framerate: 10

DAQ:
  callbacks:
    save_h5:
    plot_fast:
      channels_to_plot: [0, 1]
```

Use an empty value when a callback has no parameters. Use a nested mapping when
the callback accepts options.

## Camera Callbacks

| Name | Purpose |
|------|---------|
| `disp` | Display frames with OpenCV. |
| `disp_fast` | Display frames with pyqtgraph. |
| `disp_back` | Display a center/back camera helper view. |
| `disp_top` | Display a center/top camera helper view. |
| `save_avi` | Save frames with OpenCV `VideoWriter`. |
| `save_ffmpegcv` | Save frames with an ffmpegcv backend. |
| `save_vidgear` | Save frames through VidGear. |
| `save_vidgear_round` | Save rounded/cropped VidGear output. |
| `save_avi_fast` | Save video with NVIDIA Video Processing Framework. |
| `saveimg_h5` | Save image frames to HDF5. |
| `saveimg_zarr` | Save image frames to Zarr. |
| `save_timestamps` | Save system and camera timestamps. |

Some video writers require optional packages or GPU-specific binaries. Confirm
support on the rig with `etho version --debug` and a short test run.

## DAQ And DLP Callbacks

| Name | Purpose |
|------|---------|
| `save_h5` | Save analog input chunks and metadata to HDF5. |
| `save_zarr` | Save analog input chunks and metadata to Zarr. |
| `plot_fast` | Display traces with pyqtgraph. |
| `plot` | Display traces with matplotlib. |
| `savedlp_h5` | Save DLP frame or stimulus metadata. |

`plot_fast` and `plot` can limit displayed channels:

```yaml
callbacks:
  plot_fast:
    channels_to_plot: [0, 1, 2]
```

## Writing A Callback

Callbacks subclass `BaseCallback` and implement `_loop`. `_cleanup` should close
files, flush buffers, and call `super()._cleanup()` at the end.

```python
from etho.services.callbacks import register_callback
from etho.services.callbacks._base import BaseCallback


@register_callback
class CoolCallback(BaseCallback):
    FRIENDLY_NAME = "cool"

    def _loop(self, data):
        image_or_chunk, timestamps = data
        ...

    def _cleanup(self):
        ...
        super()._cleanup()
```

Once imported by the callback package, the callback can be selected in a
protocol by `FRIENDLY_NAME` or class name.
