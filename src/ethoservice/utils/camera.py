# required imports
import time  # for timer
from ..utils.log_exceptions import for_all_methods, log_exceptions
import logging
import numpy as np
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


try:
    import PyCapture2
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
        pass

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
        pass

    def _estimate_timestamp_offset(self) -> float:
        """[summary]

        Returns:
            float: Timestamp offset rel to system time.
                   Return 0 if timestamps are already in system time.
        """
        pass

    @property
    def roi(self) -> Tuple[int, int, int, int]:
        pass

    @roi.setter
    def roi(self, x0_y0_x_y: Tuple[int, int, int, int]):
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

    NAME = 'SPN'

    def __init__(self, serialnumber):
        self.serialnumber = serialnumber

    def init(self):
        self.cam_system = PySpin.System_GetInstance()
        self.cam_list = self.cam_system.GetCameras()
        self.c = self.cam_list.GetBySerial(self.serialnumber)
        self.c.Init()
        self.c.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)

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
    def roi(self) -> Tuple[int, int, int, int]:
        return self.c.OffsetX.GetValue(), self.c.OffsetY.GetValue(), self.c.Width.GetValue(), self.c.Height.GetValue()

    @roi.setter
    def roi(self, x0_y0_x_y: Tuple[int, int, int, int]):
        try:
            x0, y0, x, y = x0_y0_x_y
        except ValueError:
            raise ValueError('Need 4-tuple with x0_y0_x_y')
        else:
            self._min_max_inc(self.c.Width, int(x))
            self._min_max_inc(self.c.Height, int(y))
            self._min_max_inc(self.c.OffsetX, int(x0))
            self._min_max_inc(self.c.OffsetY, int(y0))

    @property
    def framerate(self):
        return self.c.AcquisitionResultingFrameRate.GetValue()

    @framerate.setter
    def framerate(self, value: float):
        self.c.AcquisitionFrameRateEnable.SetValue(True)
        self.c.AcquisitionFrameRate.SetValue(float(value))

    @property
    def gamma(self):
        return self.c.GammaEnable.GetValue()

    @gamma.setter
    def gamma(self, value: bool):
        self.c.GammaEnable.SetValue(bool(value))

    @property
    def brightness(self):
        return self.c.BlackLevel.GetValue()

    @brightness.setter
    def brightness(self, value: float):
        self.c.BlackLevelSelector.SetValue(PySpin.BlackLevelSelector_All)
        self.c.BlackLevel.SetValue(float(value))

    @property
    def exposure(self):
        return self.c.ExposureTime.GetValue()

    @exposure.setter
    def exposure(self, value: float):
        self.c.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
        self.c.ExposureMode.SetValue(PySpin.ExposureMode_Timed)
        self.c.ExposureTime.SetValue(float(value))

    @property
    def gain(self):
        self.c.Gain.GetValue()

    @gain.setter
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
        try:
            self.stop()  # should check if cam started
        except:
            pass
        self.c.DeInit()
        del self.c
        self.cam_list.Clear()
        del self.cam_list
        # self.cam_system.ReleaseInstance()
        # del self.cam_system


class Ximea(BaseCam):

    NAME = 'XIM'

    def __init__(self, serialnumber):
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
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

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
        self.c.stop_acquisition()

    def close(self):
        self.stop()
        self.c.close_device()

    def reset(self, sleep=None):
        pass


class PyCapture(BaseCam):
    NAME = 'CAP'

    def __init__(self, serialnumber):
        """[summary]

        Should set:
        - continuous acq
        - anything that optimizes throughput
        - pixel format
        - time stamping
        - init pointer to image

        Args:
            serialnumber (Union[str, int]): [description]
        """
        self.serialnumber = int(serialnumber)
        self.timestamp_offset = 0
        self.im = PyCapture2.Image()

    def init(self):
        self.bus = PyCapture2.BusManager()
        self.c = PyCapture2.Camera()
        self.uid = self.bus.getCameraFromSerialNumber(self.serialnumber)
        self.c.connect(self.uid)
        # self.c.setConfiguration(grabMode=PyCapture2.GRAB_MODE.DROP_FRAMES)
        # FAILS with "IIDC failure"
        # self.c.setFormat7Configuration(100.0, mode=PyCapture2.MODE.MODE_0, pixelFormat=PyCapture2.PIXEL_FORMAT.BGR)
        self.timestamp_offset = self._estimate_timestamp_offset()
        # embedded_info = self.c.getEmbeddedImageInfo()
        # if embedded_info.available.timestamp:
        self.c.setEmbeddedImageInfo(timestamp=True)
        #     print('\nTimeStamp is enabled.\n')
        # else:
        #     print('\nTimeStamp no available.\n')

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
        try:
            self.im = self.c.retrieveBuffer()
            system_ts = time.time()
        except PyCapture2.Fc2error as fc2Err:
            print('Error retrieving buffer : %s' % fc2Err)
            return

        ts = self.im.getTimeStamp()

        image_ts = ts.cycleSeconds * 8000 + ts.cycleCount
        # image_ts = cycleOffset + cycleSecs / 8000

        image = self.im.convert(PyCapture2.PIXEL_FORMAT.BGR).getData()
        image = image.reshape((self.im.getCols(), self.im.getRows(), -1))
        image = image.astype(np.uint8)
        return image, image_ts, system_ts

    def _estimate_timestamp_offset(self) -> float:
        """[summary]

        Returns:
            float: Timestamp offset rel to system time.
                   Return 0 if timestamps are already in system time.
        """
        return 0

    @property
    def roi(self) -> Tuple[int, int, int, int]:
        imageSettings, packetSize, percentage = self.c.getFormat7Configuration()
        return imageSettings.offsetX, imageSettings.offsetY, imageSettings.width, imageSettings.height

    @roi.setter
    def roi(self, x0_y0_x_y: Tuple[int, int, int, int]):
        # try:
        #     x0, y0, x, y = x0_y0_x_y
        #     info, isValid = self.c.getFormat7Info(PyCapture2.MODE.MODE_0)
        #     import ipdb;ipdb.set_trace()
        #     self.c.setFormat7Configuration(100.0, offsetX=0, offsetY=0, width=16, height=16)
        # except ValueError:
        #     raise ValueError('Need 4-tuple with x0_y0_x_y')
        # # else:
        # self.c.setFormat7Configuration(100.0, offsetX=0, offsetY=0)
        # self._min_max_inc('width', int(x))
        # self._min_max_inc('height', int(y))
        # self._min_max_inc('offsetX', int(x0))
        # self._min_max_inc('offsetY', int(y0))
        pass

    def _min_max_inc(self, prop: str, value: int = None, set_value=True):
        # info, isValid = self.c.getFormat7Info(PyCapture2.MODE.MODE_0)
        # prop_map = {'width': {'max_val': info.maxWidth, 'min_val': info.minWidth, 'inc': info.imageHStepSize},
        #             'height': {'max_val': info.maxHeight, 'min_val': info.minHeight, 'inc': info.imageVStepSize},
        #             'offsetX': {'max_val': info.maxWidth, 'min_val': 0, 'inc': info.offsetHStepSize},
        #             'offsetY': {'max_val': info.maxHeight, 'min_val': 0, 'inc': info.offsetVStepSize},
        #             }

        # if value is not None:
        #     value = np.clip(value, prop_map[prop]['min_val'], prop_map[prop]['max_val'])
        #     value = np.round(value / prop_map[prop]['inc']) * prop_map[prop]['inc']
        #     if set_value:
        #         self.c.setFormat7Configuration(100.0, **{prop: int(value)})
        #         imageSettings, packetSize, percentage = self.c.getFormat7Configuration()
        #         value = getattr(imageSettings, prop)
        return value

    @property
    def brightness(self):
        return self.c.getProperty(PyCapture2.PROPERTY_TYPE.BRIGHTNESS).absValue

    @brightness.setter
    def brightness(self, value: float):
        self.c.setProperty(type=PyCapture2.PROPERTY_TYPE.BRIGHTNESS, absValue=float(value), autoManualMode=False)

    @property
    def exposure(self):
        # UNITS?
        return self.c.getProperty(PyCapture2.PROPERTY_TYPE.SHUTTER).absValue

    @exposure.setter
    def exposure(self, value: float):
        self.c.setProperty(type=PyCapture2.PROPERTY_TYPE.SHUTTER, absValue=float(value), autoManualMode=False)

    @property
    def gain(self):
        return self.c.getProperty(PyCapture2.PROPERTY_TYPE.GAIN).absValue

    @gain.setter
    def gain(self, value: float):
        self.c.setProperty(type=PyCapture2.PROPERTY_TYPE.GAIN, absValue=float(value), autoManualMode=False)

    @property
    def gamma(self):
        return self.c.getProperty(PyCapture2.PROPERTY_TYPE.GAMMA).absValue

    @gamma.setter
    def gamma(self, value: float):
        self.c.setProperty(type=PyCapture2.PROPERTY_TYPE.GAMMA, absValue=float(value), autoManualMode=False)

    @property
    def framerate(self):
        return self.c.getProperty(PyCapture2.PROPERTY_TYPE.FRAME_RATE).absValue

    @framerate.setter
    def framerate(self, value: float):
        self.c.setProperty(type=PyCapture2.PROPERTY_TYPE.FRAME_RATE, absValue=float(value), autoManualMode=False)

    def start(self):
        self.c.startCapture()

    def stop(self):
        self.c.stopCapture()

    def close(self):
        self.c.disconnect()
        del self.c

    def reset(self):
        """Reset the camera system to free all resources."""
        # self.bus.FireBusReset(self.guid)
        self.bus.rescanBus()  # does not reset but "invalidates all current camera connections"


make = {'Spinnaker': Spinnaker, 'Ximea': Ximea, 'PyCapture': PyCapture}
