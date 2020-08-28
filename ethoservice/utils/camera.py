#!/usr/bin/env python
# required imports
import time     # for timer
import sys
from .log_exceptions import for_all_methods, log_exceptions
import logging
import numpy as np
import h5py
import cv2
from typing import Tuple, Optional

try:
    from ximea import xiapi
except ImportError as e:
    print("IGNORE IF RUN ON HEAD")
    print(e)

try:
    import PySpin
except ImportError as e:
    print("IGNORE IF RUN ON HEAD")
    print(e)


class BaseCam():

    def __init__(self, serialnumber):
        """[summary]

        Should set:
        - continuous acq
        - anything that optimizes throughput
        - pixel format
        - time stamping
        - init pointer to image

        Args:
            serialnumber ([type]): [description]
        """
        self.im = None  # pointer to image
        self.timestamp_offset = self._get_timestamp_offset()

    def get(self, timeout: Optional[float] = None) -> Tuple[np.ndarray, float, float]:
        """

        pull image from cam, convert to np.ndarray, get time stamp

        Args:
            timeout (Optional[float], optional): [description]. Defaults to None.

        Returns:
            Tuple[np.ndarray, float, float]:
                image as np.array (x,y,c)
                image_timestamp (in seconds UTC)
                system_timestamp (in seconds UTC)

        Raises:
            ValueError is sth goes wrong
        """

        image, image_timestamp, system_timestamp = None, None, None
        return image, image_timestamp, system_timestamp

    def _estimate_timestamp_offset(self) -> float:
        """[summary]

        Returns:
            float: Timestamp offset rel to system time.
                   Return 0 if timestamps are already in system time.
        """
        pass

    @property
    def roi(self):
        pass

    @property.setter
    def roi(self, x0, y0, width, height):
        pass

    @property
    def brightness(self):
        pass

    @property
    def exposure(self):
        pass

    @property
    def gain(self):
        pass

    @property
    def gamma(self):
        pass

    @property
    def framerate(self):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        pass

    def reset(self):
        """Reset the camera system to free all resources."""
        pass


class Spinnaker(BaseCam):

    def __init__(self, serialnumber):
        self.serialnumber = serialnumber

        self.cam_system = PySpin.System_GetInstance()
        self.cam_list = self.cam_system.GetCameras()
        self.c = self.cam_list.GetBySerial(self.cam_serialnumber)
        self.c.Init()

        # enable embedding of frame TIME STAMP
        self.c.ChunkModeActive.SetValue(True)
        self.c.ChunkSelector.SetValue(PySpin.ChunkSelector_Timestamp)
        self.c.ChunkEnable.SetValue(True)
        self.timestamp_offset = self._estimate_timestamp_offset()

        # set pixel format
        self.c.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)

        # set continuous acquisition
        self.c.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)

        # trigger overlap -> ReadOut - for faster frame rates
        self.c.TriggerOverlap.SetValue(PySpin.TriggerOverlap_ReadOut)


    def get(self, timeout=None):

        timeout = PySpin.EVENT_TIMEOUT_INFINITE
        # get image
        im = self.c.GetNextImage(timeout)
        system_stimestamp = time.time()

        if im.IsIncomplete():
            raise ValueError(f"Image incomplete with image status {im.GetImageStatus()}")
        else:
            # convert
            im_converted = im.Convert(PySpin.PixelFormat_BGR8, PySpin.HQ_LINEAR)
            BGR = im_converted.GetNDArray()

            # get time stamps
            image_timestamp = im.GetTimeStamp()
            image_timestamp = image_timestamp / 1e9 + self.timestamp_offset
            return BGR, image_timestamp, system_stimestamp

    @property
    def roi(self) -> Tuple[int, int, int]:
        return self.c.OffsetX.GetValue(), self.c.OffsetY.GetValue(), self.c.Width.GetValue(), self.c.Height.GetValue()

    @property.setter
    def roi(self, x0: int, y0: int, x: int, y: int):
        self._min_max_inc(self.c.Width, int(x))
        self._min_max_inc(self.c.Height, int(y))
        self._min_max_inc(self.c.OffsetX, int(x0))
        self._min_max_inc(self.c.OffsetY, int(y0))

    @property
    def framerate(self):
        return self.c.AcquisitionResultingFrameRate.GetValue()

    @property.setter
    def framerate(self, value: float):
        self.c.AcquisitionFrameRateEnable.SetValue(True)
        self.c.AcquisitionFrameRate.SetValue(float(value))

    @property
    def gamma(self):
        return self.c.GammaEnable.GetValue()

    @property.setter
    def gamma(self, value: bool):
        self.c.GammaEnable.SetValue(bool(value))

    @property
    def brightness(self):
        return self.c.BlackLevel.GetValue()

    @property.setter
    def brightness(self, value: float):
        self.c.BlackLevelSelector.SetValue(PySpin.BlackLevelSelector_All)
        self.c.BlackLevel.SetValue(float(value))

    @property
    def shutter(self):
        return self.c.ExposureTime.GetValue()

    @property.setter
    def shutter(self, value: float):
        self.c.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
        self.c.ExposureMode.SetValue(PySpin.ExposureMode_Timed)
        self.c.ExposureTime.SetValue(float(value))

    @property
    def gain(self):
        self.c.Gain.GetValue()

    @property.setter
    def gain(self, value: float):
        self.c.GainAuto.SetValue(PySpin.GainAuto_Off)
        self.c.Gain.SetValue(float(value))

    def _min_max_inc(self, prop, value=None, set_value=True):
        min_val, max_val, inc = prop.GetMin(), prop.GetMax(), prop.GetInc()

        prop_type = type(prop.GetValue())
        if value is not None:
            value = np.clip(value, min_val, max_val)
            value = np.round(value / inc) * inc
            if set_value:
                value = prop_type(value)
                prop.SetValue(value)
                value = prop.GetValue()
        return value

    def _estimate_timestamp_offset(self, timestamp_offset_iterations=10):
        """Gets offset between system time and timestamps."""
        # This method is required because the timestamp stored in the camera is relative to when it was powered on, so an
        # offset needs to be applied to get it into epoch time; from tests I’ve done, this appears to be accurate to ~1e-3
        # seconds.
        timestamp_offsets = []
        for i in range(timestamp_offset_iterations):
            # Latch timestamp. This basically “freezes” the current camera timer into a variable that can be read with
            self.c.TimestampLatch.Execute()
            system_time = time.time()
            # Compute timestamp offset in seconds; note that timestamp latch value is in nanoseconds
            timestamp_offset = system_time - self.c.TimestampLatchValue.GetValue() / 1e9
            timestamp_offsets.append(timestamp_offset)
        # Return the median value
        return np.median(timestamp_offsets)

    def reset(self, sleep: float = 10.0):
        device_reset = PySpin.CCommandPtr(self.c.GetNodeMap().GetNode("DeviceReset"))
        device_reset.Execute()
        self.close()
        time.sleep(sleep)

    def start(self):
        self.c.BeginAcquisition()

    def stop(self):
        self.c.EndAcquisition()  # not sure this works if BeginAcquistion has not been called

    def close(self):
        self.stop()
        self.c.DeInit()
        del self.c
        self.cam_list.Clear()
        del self.cam_list
        self.cam_system.ReleaseInstance()
        del self.cam_system


class Ximea(BaseCam):

    def __init__(self, serialnumber):
        self.serialnumber = serialnumber

        self.im = xiapi.Image()
        # create instance for first connected camera
        self.c = xiapi.Camera()
        self.c.open_device_by_SN(self.serialnumber)

        self.c.set_imgdataformat('XI_MONO8')


    def get(self, timeout=None):
        self.c.get_image(self.im)  # get buffer - this blocks until an image is acquired
        system_timestamp = time.time()
        image_timestamp = self.img.tsSec * 1e9 + self.img.tsUSec

        image = self.im.get_image_data_numpy()
        return image, image_timestamp, system_timestamp

    @property
    def roi(self):
        return self.c.get_offsetX(), self.c.get_offsetY(), self.c.get_width(), self.c.get_height()

    @property.setter
    def roi(self, x0: int, y0: int, x: int, y: int):
        # see how to access these for the width and heigh params:
        # XI_PRM_INFO_INCREMENT
        # XI_PRM_INFO_MAX
        # XI_PRM_INFO_MIN
        # xiGetParamInt(handle, XI_PRM_EXPOSURE XI_PRM_INFO_MAX, &exp_max);
        self.c.set_offsetX(int(x0))
        self.c.set_offsetY(int(y0))
        self.c.set_width(int(x))
        self.c.set_height(int(y))

    @property
    def exposure(self):
        self.c.get_exposure()

    @property.setter
    def exposure(self, value: float):
        self.c.set_aeag('XI_OFF')
        self.c.set_exposure(float(value))

    @property
    def framerate(self):
        self.c.get_framerate()

    @property.setter
    def framerate(self, value: float):
        self.c.set_acq_timing_mode('XI_ACQ_TIMING_MODE_FRAME_RATE')
        self.c.set_framerate(float(value))

    @property
    def gamma(self):
        self.c.get_gammay()

    @property.setter
    def gamma(self, value: float):
        self.c.set_gammay(float(value))

    @property
    def gain(self):
        self.c.get_gain()

    @property.setter
    def gain(self, value: float):
        self.c.set_aeag('XI_OFF')
        self.c.set_gain(float(value))


    def start(self):
        self.c.start_acquisition()

    def stop(self):
        self.c.stop_acquisition()

    def close(self):
        self.stop()
        self.c.close_device()

    def reset(self, sleep=None):
        pass


class FlyCapture(BaseCam):
    pass

make = {'spinnaker': Spinnaker, 'xiapi': Ximea, 'flycapture': FlyCapture}
