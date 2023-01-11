import time
import numpy as np
from typing import Tuple
from .base import BaseCam

try:
    import PySpin

    pyspin_error = None
except ImportError as e:
    pyspin_error = e


class Spinnaker(BaseCam):

    NAME = "SPN"

    def __init__(self, serialnumber):
        if pyspin_error is not None:
            raise pyspin_error
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

    def _set_gpio(self, line="Line2"):
        # from PySpin/Examples/Python3/CounterAndTimer.py
        # from https://github.com/CapAI/misc/blob/a22cd50e90018c03cde3c1339aa622185502bb05/spinnaker/pyspin/Examples/Python3/CounterAndTimer.py#L193
        nodemap = self.c.GetNodeMap()
        node_line_selector = PySpin.CEnumerationPtr(nodemap.GetNode("LineSelector"))
        if not PySpin.IsAvailable(node_line_selector) or not PySpin.IsWritable(node_line_selector):
            print("\nUnable to set Line Selector (enumeration retrieval). Aborting...\n")
            return False

        entry_line_selector_line = node_line_selector.GetEntryByName(line)
        if not PySpin.IsAvailable(entry_line_selector_line) or not PySpin.IsReadable(entry_line_selector_line):
            print("\nUnable to set Line Selector (entry retrieval). Aborting...\n")
            return False

        line_selector_line = entry_line_selector_line.GetValue()
        node_line_selector.SetIntValue(line_selector_line)

        # Set Line Source for Selected Line to Counter 0 Active
        node_line_source = PySpin.CEnumerationPtr(nodemap.GetNode("LineSource"))
        if not PySpin.IsAvailable(node_line_source) or not PySpin.IsWritable(node_line_source):
            print("\nUnable to set Line Source (enumeration retrieval). Aborting...\n")
            return False

        entry_line_source_counter_0_active = node_line_source.GetEntryByName("ExposureActive")
        if not PySpin.IsAvailable(entry_line_source_counter_0_active) or not PySpin.IsReadable(
            entry_line_source_counter_0_active
        ):
            print("\nUnable to set Line Source (entry retrieval). Aborting...\n")
            return False

        line_source_counter_0_active = entry_line_source_counter_0_active.GetValue()

        node_line_source.SetIntValue(line_source_counter_0_active)
        return True

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
            raise ValueError("Need 4-tuple with x0_y0_x_y")
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
    def brightness(self) -> float:
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
        try:
            self.c.EndAcquisition()  # not sure this works if BeginAcquistion has not been called
        except:
            pass

    def close(self):
        self.stop()  # should check if cam started
        self.c.DeInit()
        del self.c
        self.cam_list.Clear()
        del self.cam_list
        # self.cam_system.ReleaseInstance()
        # del self.cam_system
