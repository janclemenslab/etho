import time
from typing import Tuple
from .base import BaseCam

try:
    from pylablib.devices import DCAM
    hamamatsu_error = None
except ImportError as e:
    hamamatsu_error = e


class Hamamatsu(BaseCam):

    NAME = "HAM"

    def __init__(self, serialnumber):
        if hamamatsu_error is not None:
            raise hamamatsu_error
        self.serialnumber = int(serialnumber)
        self.timestamp_offset = 0
        self.im = None

    def init(self):
        self.c = DCAM.DCAMCamera(idx=self.serialnumber)
        self.c.set_trigger_mode('int')
        self.c.set_readout_speed('fast')
        self.c.set_defect_correct_mode(enabled=True)
        self.timestamp_offset = 0

    def get(self, timeout=None):
        self.c.wait_for_frame()  # wait for the next available frame
        image = self.c.read_oldest_image()  # get the oldest image which hasn't been read yet

        system_timestamp = time.time()
        image_timestamp = self.c.get_frame_readout_time()
        exposure, image_timestamp = self.c.get_frame_timings()

        return image, image_timestamp, system_timestamp


    @property
    def roi(self):
        roi = self.c.get_roi()
        # return self.c.get_offsetX(), self.c.get_offsetY(), self.c.get_width(), self.c.get_height()
        return roi.hstart, roi.vstart, roi.hend - roi.hstart, roi.vend - roi.vstart

    @roi.setter
    def roi(self, x0_y0_x_y: Tuple[int, int, int, int]):
        try:
            x0, y0, x, y = x0_y0_x_y
            self.set_roi(hstart=x0, vstart=y0, hend=x0+x, vend=y0+y)
        except ValueError:
            raise ValueError("Need 4-tuple with x0_y0_x_y")

    @property
    def exposure(self):
        return self.c.get_exposure()

    @exposure.setter
    def exposure(self, value: float):
        """Set exposure/shutter time in WHICH UNITS? ns or ms?."""
        self.c.set_exposure(float(value))

    @property
    def framerate(self):
        return 1/self.get_exposure()

    @framerate.setter
    def framerate(self, value: float):
        self.c.set_exposure(1/float(value))

    @property
    def gamma(self):
        return 1

    @gamma.setter
    def gamma(self, value: float):
        pass

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
        self.c.close()

    def reset(self, sleep=None):
        pass


    def info_hardware(self):
        cam_info = self.c.get_device_info()
        info = {
            "Serial number": cam_info.serial_number,
            "Camera model": cam_info.model,
            "Camera vendor": cam_info.vendor,
            "Sensor": str(self.c.get_dectector_size()),
            "Resolution": str(self.c._get_data_dimnensions_rc()),
            "Firmware version": cam_info.camer_version,
            "Firmware build time": '',
        }
        return info