"""[summary]

TODO: register all methods for logging: `@for_all_methods(log_exceptions(logging.getLogger(__name__)))`
"""
import logging
import numpy as np
import cv2
from . import register_callback
from ._base import BaseCallback
from ..utils.concurrent_task import ConcurrentTask


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
    TIMESTAMPS_ONLY = False

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
    TIMESTAMPS_ONLY = False

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
    FRIENDLY_NAME = 'save_avi'
    TIMESTAMPS_ONLY = False

    def __init__(self, data_source, *, poll_timeout=0.01,
                 **kwargs):
        super().__init__(data_source=data_source, poll_timeout=poll_timeout, **kwargs)

        self.vw = cv2.VideoWriter()
        self.vw.open(self.file_name + self.SUFFIX, cv2.VideoWriter_fourcc(*'x264'),
                     self.frame_rate, (self.frame_height, self.frame_width), True)

    def _loop(self, data):
        if hasattr(self.data_source, 'WHOAMI') and self.data_source.WHOAMI == 'array':
            image = data
        else:
            image, timestamp = data

        self.vw.write(image)

    def _cleanup(self):
        self.vw.release()
        del self.vw
        super()._cleanup()


@register_callback
class ImageWriterCVR(ImageCallback):

    SUFFIX: str = '.avi'
    FRIENDLY_NAME = 'save_avi_round'
    TIMESTAMPS_ONLY = False

    def __init__(self, data_source, *, poll_timeout=0.01, max_frames_per_video=100_000,
                 **kwargs):
        super().__init__(data_source=data_source, poll_timeout=poll_timeout, **kwargs)

        self.video_count = 0
        self.frame_count = 0
        self.max_frames_per_video = max_frames_per_video

        self.vw = cv2.VideoWriter()
        self.vw.open(self.file_name + self.SUFFIX + f"{self.video_count:06d}", cv2.VideoWriter_fourcc(*'x264'),
                     self.frame_rate, (self.frame_height, self.frame_width), True)

    def _loop(self, data):
        if hasattr(self.data_source, 'WHOAMI') and self.data_source.WHOAMI == 'array':
            image = data
        else:
            image, timestamp = data

        self.vw.write(image)
        self.frame_count += 1
        if self.frame_count > self.max_frames_per_video:
            self.vw.release()
            del self.vw
            self.vw = cv2.VideoWriter()
            self.vw.open(self.file_name + self.SUFFIX + f"{self.video_count:06d}", cv2.VideoWriter_fourcc(*'x264'),
                         self.frame_rate, (self.frame_height, self.frame_width), True)
            self.frame_count = 0
            self.video_count += 1

    def _cleanup(self):
        self.vw.release()
        del self.vw
        super()._cleanup()


@register_callback
class ImageWriterVPF(ImageCallback):

    SUFFIX: str = '.avi'
    FRIENDLY_NAME = 'save_avi_fast'
    TIMESTAMPS_ONLY = False

    def __init__(self, data_source, *, poll_timeout=0.01,
                 VPF_bin_path=None,
                 **kwargs):
        super().__init__(data_source=data_source, poll_timeout=poll_timeout, **kwargs)

        import sys
        sys.path.append(VPF_bin_path)
        import PyNvCodec as nvc

        gpuID = 0
        self.encFile = open(self.file_name + self.SUFFIX,  "wb")
        # self.nvEnc = nvc.PyNvEncoder({'rc':'vbr_hq','profile': 'high', 'cq': '10', 'codec': 'h264', 'bf':'3',
        #                               'fps': str(self.frame_rate), 'temporalaq': '', 'lookahead':'20',
        #                               's': f'{self.frame_width}x{self.frame_height}'}, gpuID)
        self.nvEnc = nvc.PyNvEncoder({'rc':'vbr_hq','profile': 'high', 'cq': '10', 'codec': 'h264', 'bf':'3',
                                      'fps': str(self.frame_rate), 'temporalaq': '', 'lookahead':'20',
                                      's': f'{self.frame_height}x{self.frame_width}'}, gpuID)
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
    TIMESTAMPS_ONLY = True

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
        super()._cleanup()


@register_callback
class ImageDisplayCenterBackCV2(ImageCallback):

    FRIENDLY_NAME = 'disp_back'
    TIMESTAMPS_ONLY = False

    def __init__(self, data_source, poll_timeout=0.01, center_x=0, center_y=0, **kwargs):
        super().__init__(data_source=data_source, poll_timeout=poll_timeout, **kwargs)

        logging.info("setting up disp")
        cv2.namedWindow('display')
        cv2.resizeWindow('display', self.frame_width, self.frame_height)

        if center_x != 0:
            self.center_x = center_x
        else:
            self.center_x = self.frame_height//2
        if center_y != 0:
            self.center_y = center_y
        else:
            self.center_y = self.frame_width//2
        self.color = [0,0,250]
        self.thickness = 1

    @classmethod
    def make_concurrent(cls, comms='pipe', **kwargs):
        return ConcurrentTask(task=cls.make_run, comms=comms, **kwargs)

    def _loop(self, data):
        if self.data_source.WHOAMI == 'array':
            image = data
        else:
            image, timestamp = data

        image = cv2.rectangle(image, (self.frame_height-95,self.frame_width), (95,self.frame_width-45), color=self.color, thickness=self.thickness) # ball region
        image = cv2.line(image, (60,self.center_y), (self.frame_height-60, self.center_y), self.color, self.thickness) # y-axis cross
        image = cv2.line(image, (self.center_x,60), (self.center_x,self.frame_width-60), self.color, self.thickness) # x-axis cross
        # image = cv2.rectangle(image, (self.center_x-40,self.center_y-35), (self.center_x+20,self.center_y+35), color=self.color, thickness=self.thickness) # fly
        cv2.imshow('display', image)
        cv2.waitKey(1)

    def _cleanup(self):
        logging.info("closing display")
        cv2.destroyWindow('display')

@register_callback
class ImageDisplayCenterTopCV2(ImageCallback):

    FRIENDLY_NAME = 'disp_top'
    TIMESTAMPS_ONLY = False

    def __init__(self, data_source, poll_timeout=0.01, circ_center_x=0, circ_center_y=0, circ_r=0, **kwargs):
        super().__init__(data_source=data_source, poll_timeout=poll_timeout, **kwargs)

        logging.info("setting up disp")
        cv2.namedWindow('display')
        cv2.resizeWindow('display', self.frame_width, self.frame_height)

        # properties of drawn circle
        if circ_center_x != 0:
            self.circ_center_x = circ_center_x
        else:
            self.circ_center_x = self.frame_height//2
        if circ_center_y != 0:
            self.circ_center_y = circ_center_y
        else:
            self.circ_center_y = self.frame_width//2
        if circ_r != 0:
            self.circ_r = circ_r
        else:
            self.circ_r = 10
        self.circ_color = [0,0,250]
        self.needle_color = [250,0,0]
        self.circ_thickness = 2

        self.flyhead_topleft, self.flyhead_bottomright = (self.circ_center_x-45,self.circ_center_y-50), (self.circ_center_x+5,self.circ_center_y+50)
        self.flybody_topleft, self.flybody_bottomright = (self.circ_center_x,self.circ_center_y-45), (self.circ_center_x+200,self.circ_center_y+45)
        self.needle_topleft, self.needle_bottomright = (self.circ_center_x+195,self.circ_center_y-40), (self.frame_width,self.circ_center_y+40)

    @classmethod
    def make_concurrent(cls, comms='pipe', **kwargs):
        return ConcurrentTask(task=cls.make_run, comms=comms, **kwargs)

    def _loop(self, data):
        if self.data_source.WHOAMI == 'array':
            image = data
        else:
            image, timestamp = data

        image = cv2.circle(image, (self.circ_center_x, self.circ_center_y), self.circ_r, self.circ_color, self.circ_thickness)
        image = cv2.line(image, (self.circ_center_x,0), (self.circ_center_x,self.frame_width), self.circ_color, self.circ_thickness)
        image = cv2.line(image, (0,self.circ_center_y), (self.frame_height,self.circ_center_y), self.circ_color, self.circ_thickness)
        image = cv2.rectangle(image, self.flyhead_topleft, self.flyhead_bottomright, color=self.circ_color, thickness=self.circ_thickness)
        image = cv2.rectangle(image, self.flybody_topleft, self.flybody_bottomright, color=self.circ_color, thickness=self.circ_thickness)
        image = cv2.rectangle(image, self.needle_topleft, self.needle_bottomright, color=self.needle_color, thickness=self.circ_thickness)
        cv2.imshow('display', image)
        cv2.waitKey(1)

    def _cleanup(self):
        logging.info("closing display")
        cv2.destroyWindow('display')

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
