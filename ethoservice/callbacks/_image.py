"""[summary]

TODO: register all methods for logging: `@for_all_methods(log_exceptions(logging.getLogger(__name__)))`
"""
import logging
import numpy as np
import cv2
from . import register_callback
from ._base import BaseCallback
from ..utils.ConcurrentTask import ConcurrentTask


class ImageCallback(BaseCallback):
    def __init__(self, data_source, poll_timeout: float = None, rate: float = 0,
                 file_name: str = None, frame_rate: float = None,
                 frame_width: float = None, frame_height: float = None,
                 **kwargs):
        super().__init__(data_source=data_source, poll_timeout=poll_timeout, rate=rate, **kwargs)

        self.frame_rate = frame_rate
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.file_name = file_name


@register_callback
class ImageDisplayCV2(ImageCallback):

    FRIENDLY_NAME = 'disp'

    def __init__(self, data_source, poll_timeout=0.01,
                 **kwargs):
        super().__init__(data_source=data_source, poll_timeout=poll_timeout, **kwargs)

        logging.info("setting up disp")
        cv2.namedWindow('display')
        cv2.resizeWindow('display', self.frame_width, self.frame_height)

    @classmethod
    def make_concurrent(cls, comms='pipe', **kwargs):
        return ConcurrentTask(task=cls.make_run, comms=comms, **kwargs)

    def _loop(self, data):
        if self.data_source.WHOAMI == 'array':
            image = data
        else:
            image, timestamp = data

        cv2.imshow('display', image)
        cv2.waitKey(1)

    def _cleanup(self):
        logging.info("closing display")
        cv2.destroyWindow('display')


@register_callback
class ImageDisplayPQG(ImageCallback):

    FRIENDLY_NAME = 'disp_fast'

    def __init__(self, data_source, *, poll_timeout=0.01,
                 **kwargs):
        super().__init__(data_source=data_source, poll_timeout=poll_timeout, **kwargs)

        from pyqtgraph.Qt import QtGui
        import pyqtgraph as pg
        from pyqtgraph.widgets.RawImageWidget import RawImageWidget

        logging.info("setting up ImageDisplayPQG")

        pg.setConfigOption('background', 'w')
        pg.setConfigOption('leftButtonPan', False)

        # set up window and subplots
        self.app = QtGui.QApplication([])
        self.win = RawImageWidget(scaled=True)
        self.win.resize(self.frame_width, self.frame_height)
        self.win.show()
        self.app.processEvents()

    @classmethod
    def make_concurrent(cls, comms='pipe', **kwargs):
        return ConcurrentTask(task=cls.make_run, comms=comms, **kwargs)

    def _loop(self, data):
        if self.data_source.WHOAMI == 'array':
            image = data
        else:
            image, timestamp = data

        self.win.setImage(image)
        self.app.processEvents()

    def _cleanup(self):
        logging.info("closing display")
        # close app and windows here?


@register_callback
class ImageWriterCV2(ImageCallback):

    SUFFIX: str = '.avi'
    FRIENDLY_NAME = 'save'

    def __init__(self, data_source, *, poll_timeout=0.01,
                 **kwargs):
        super().__init__(data_source=data_source, poll_timeout=poll_timeout, **kwargs)

        self.vw = cv2.VideoWriter()
        self.vw.open(self.file_name + self.SUFFIX, cv2.VideoWriter_fourcc(*'x264'),
                     self.frame_rate, (self.frame_width, self.frame_height), True)

    def _loop(self, data):
        if self.data_source.WHOAMI == 'array':
            image = data
        else:
            image, timestamp = data

        self.vw.write(image)

    def _cleanup(self):
        self.vw.release()
        del self.vw


@register_callback
class ImageWriterVPF(ImageCallback):

    SUFFIX: str = '.avi'
    FRIENDLY_NAME = 'save_fast'

    def __init__(self, data_source, *, poll_timeout=0.01,
                 VPF_bin_path=None,
                 **kwargs):
        super().__init__(data_source=data_source, poll_timeout=poll_timeout, **kwargs)

        import sys
        sys.path.append(VPF_bin_path)
        import PyNvCodec as nvc

        gpuID = 0
        self.encFile = open(self.file_name + self.SUFFIX,  "wb")
        self.nvEnc = nvc.PyNvEncoder({'rc':'vbr_hq','profile': 'high', 'cq': '10', 'codec': 'h264', 'bf':'3',
                                      'fps': str(self.frame_rate), 'temporalaq': '', 'lookahead':'20',
                                      's': f'{self.frame_width}x{self.frame_height}'}, gpuID)
        self.nvUpl = nvc.PyFrameUploader(self.nvEnc.Width(), self.nvEnc.Height(), nvc.PixelFormat.YUV420, gpuID)
        self.nvCvt = nvc.PySurfaceConverter(self.nvEnc.Width(), self.nvEnc.Height(), nvc.PixelFormat.YUV420, nvc.PixelFormat.NV12, gpuID)

    def _loop(self, data):
        image, timestamp = data
        rawFrameYUV420 = cv2.cvtColor(image, cv2.COLOR_RGB2YUV_I420)  # convert to YUV420 - nvenc can't handle RGB inputs
        rawSurfaceYUV420 = self.nvUpl.UploadSingleFrame(rawFrameYUV420)  # upload YUV420 frame to GPU
        if (rawSurfaceYUV420.Empty()):
            return  # break
        rawSurfaceNV12 = self.nvCvt.Execute(rawSurfaceYUV420)  # convert YUV420 to NV12
        if (rawSurfaceNV12.Empty()):
            return  # break
        encFrame = self.nvEnc.EncodeSingleSurface(rawSurfaceNV12)  # compres NV12 and download
        self._write_frame(encFrame)

    def _write_frame(self, encFrame):
        # save compressd byte stream to file
        if(encFrame.size):
            encByteArray = bytearray(encFrame)  # save compressd byte stream to file
            self.encFile.write(encByteArray)

    def _cleanup(self):
        # Encoder is asyncronous, so we need to flush it
        encFrames = self.nvEnc.Flush()
        for encFrame in encFrames:
            self._write_frame(encFrame)
        self.encFile.close()


@register_callback
class TimestampWriterHDF(ImageCallback):
    """[summary]

    required params to set in prot:
        increment: int = 1000, data_dim=2,

    Args:
        BaseCallback ([type]): [description]
    """

    SUFFIX: str = '_timestamps.h5'
    FRIENDLY_NAME: str = 'save_timestamps'

    def __init__(self, data_source, *, poll_timeout=0.01,
                 increment: int = 1000, data_dim=2,
                 **kwargs):
        super().__init__(data_source=data_source, poll_timeout=poll_timeout, **kwargs)

        import h5py
        self.increment = increment
        self.f = h5py.File(self.file_name + self.SUFFIX, 'w')
        self.ts = self.f.create_dataset(name="timeStamps",
                              shape=[self.increment, data_dim],
                              maxshape=[None, data_dim],
                              dtype=np.float64, compression="gzip")
        self.frame_count = 0

    def _loop(self, data):
        image, timestamp = data

        if self.frame_count % self.increment == self.increment - 1:
            self.f.flush()
            self.ts.resize(self.ts.shape[0] + self.increment, axis=0)

        self.ts[self.frame_count] = timestamp
        self.frame_count +=1

    def _cleanup(self):
        self.ts.resize(self.frame_count, axis=0)  # self.ts[:self.frame_count]
        self.f.flush()
        self.f.close()


if __name__ == "__main__":
    import time
    import ctypes
    ct = ImageDisplayPQG.make_concurrent(task_kwargs={'frame_width': 100, 'frame_height': 100, 'rate': 2}, comms='array', comms_kwargs={'shape':(100, 100), 'ctype':ctypes.c_uint8})
    ct.start()
    for _ in range(100000000):
        if ct._sender.WHOAMI=='array':
            ct.send((np.zeros((100, 100)) + np.random.randint(0, 255)).astype(np.uint8))
        else:
            ct.send(((np.zeros((100, 100)) + np.random.randint(0, 255)).astype(np.uint8),1))
        time.sleep(.001)
    ct.finish()
    ct.close()
