import av
import numpy as np

from etho.services.callbacks._image import ImageWriterPyAV


def test_pyav_callback_writes_h264_mp4(tmp_path):
    writer = ImageWriterPyAV(None, file_name=str(tmp_path / "video"), frame_rate=30)
    writer._loop((np.zeros((4, 6, 3), dtype=np.uint8), 1.0))
    writer._cleanup()

    with av.open(str(tmp_path / "video.mp4")) as video:
        stream = video.streams.video[0]
        assert stream.codec_context.name == "h264"
        assert (stream.width, stream.height) == (6, 4)
