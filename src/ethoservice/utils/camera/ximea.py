import time
import numpy as np
from typing import Tuple
from .base import BaseCam, gray2rgb

try:
    from ximea import xiapi
    ximea_error = None
except ImportError as e:
    ximea_error = e


class Ximea(BaseCam):

    NAME = 'XIM'

    def __init__(self, serialnumber):
        if ximea_error is not None:
            raise ximea_error
        self.serialnumber = serialnumber
        self.timestamp_offset = 0
        self.im = xiapi.Image()
        # create instance for first connected camera

    def init(self):
        self.c = xiapi.Camera()
        self.c.open_device_by_SN(self.serialnumber)
        # HARDCODED
        self.c.set_downsampling('XI_DWN_2x2')
        self.c.set_downsampling_type('XI_SKIPPING')

        self.c.set_imgdataformat('XI_MONO8')
        self.c.set_limit_bandwidth(self.c.get_limit_bandwidth_maximum())
        self.timestamp_offset = self._estimate_timestamp_offset()

    def get(self, timeout=None):
        self.c.get_image(self.im)  # get buffer - this blocks until an image is acquired
        system_timestamp = time.time()
        image_timestamp = self.im.tsSec * 1e9 + self.im.tsUSec * 1e3
        image_timestamp = image_timestamp / 1e9 + self.timestamp_offset

        image = self.im.get_image_data_numpy()
        image = gray2rgb(image)

        return image, image_timestamp, system_timestamp

    def _min_max_inc(self, prop, value=None, set_value=True):
        min_val, max_val, inc = self.c.get_param(prop + ':min'), self.c.get_param(prop + ':max'), self.c.get_param(prop +
                                                                                                                   ':inc')

        prop_type = type(self.c.get_param(prop))
        if value is not None:
            value = np.clip(value, min_val, max_val)
            value = np.round(value / inc) * inc
            if set_value:
                value = prop_type(value)
                self.c.set_param(prop, value)
                value = self.c.get_param(prop)
        return value

    def _estimate_timestamp_offset(self, timestamp_offset_iterations=30):
        """Gets offset between system time and timestamps."""
        # This method is required because the timestamp stored in the camera is relative to when it was powered on, so an
        # offset needs to be applied to get it into epoch time; from tests I’ve done, this appears to be accurate to ~1e-3
        # seconds.
        timestamp_offsets = []
        tmp = self.framerate
        self.framerate = 30
        self.start()
        for _ in range(timestamp_offset_iterations):
            # timestamp = self.c.get_timestamp()  # does not work for some reason
            # system_time = time.time()
            self.c.get_image(self.im)  # get buffer - this blocks until an image is acquired
            system_ts = time.time()
            image_ts = self.im.tsSec * 1e9 + self.im.tsUSec * 1e3
            image_ts = image_ts / 1e9
            timestamp_offset = system_ts - image_ts
            timestamp_offsets.append(timestamp_offset)
        self.stop()
        self.framerate = tmp
        # Return the median value
        return np.median(timestamp_offsets)

    @property
    def roi(self):
        return self.c.get_offsetX(), self.c.get_offsetY(), self.c.get_width(), self.c.get_height()

    @roi.setter
    def roi(self, x0_y0_x_y: Tuple[int, int, int, int]):
        try:
            x0, y0, x, y = x0_y0_x_y
            self.c.set_width(16)
            self.c.set_height(16)
            self.c.set_offsetX(x0)
            self.c.set_offsetY(y0)
            self.c.set_width(x)
            self.c.set_height(y)
        except ValueError:
            raise ValueError('Need 4-tuple with x0_y0_x_y')
        else:
            self._min_max_inc('offsetX', x0)
            self._min_max_inc('offsetY', y0)
            self._min_max_inc('width', x)
            self._min_max_inc('height', y)

    @property
    def exposure(self):
        return self.c.get_exposure()

    @exposure.setter
    def exposure(self, value: float):
        """Set exposure/shutter time in WHICH UNITS? ns or ms?."""
        self.c.disable_aeag()
        self.c.set_exposure(float(value))

    @property
    def framerate(self):
        return self.c.get_framerate()

    @framerate.setter
    def framerate(self, value: float):
        self.c.set_acq_timing_mode('XI_ACQ_TIMING_MODE_FRAME_RATE')
        self.c.set_framerate(float(value))

    @property
    def gamma(self):
        return self.c.get_gammaY()

    @gamma.setter
    def gamma(self, value: float):
        self.c.set_gammaY(float(value))

    @property
    def gain(self):
        return self.c.get_gain()

    @gain.setter
    def gain(self, value: float):
        self.c.disable_aeag()
        self.c.set_gain(float(value))

    @property
    def brightness(self):
        return None

    @brightness.setter
    def brightness(self, value: float):
        pass

    def start(self):
        self.c.start_acquisition()

    def stop(self):
        try:
            self.c.stop_acquisition()
        except:
            pass

    def close(self):
        self.stop()
        self.c.close_device()

    def reset(self, sleep=None):
        pass
