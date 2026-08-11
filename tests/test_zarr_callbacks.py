import numpy as np
import zarr

from etho.services.callbacks._image import ImageWriterZarr
from etho.services.callbacks._trace import SaveZarr


def test_zarr_callbacks_write_v2_stores(tmp_path):
    trace = SaveZarr(None, file_name=str(tmp_path / "trace"))
    trace._loop((np.ones((2, 1)), 1.0))
    trace._cleanup()

    images = ImageWriterZarr(None, file_name=str(tmp_path / "images"))
    images._loop((np.ones((2, 3)), 1.0))
    images._cleanup()

    assert zarr.open_group(str(tmp_path / "trace_daq.zarr"), mode="r")["samples"].shape == (2, 1)
    assert zarr.open_group(str(tmp_path / "images_images.zarr"), mode="r")["images"].shape == (1, 2, 3)
