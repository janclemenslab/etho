import time
import numpy as np
from typing import Tuple, Union
from .base import BaseCam

try:
    import PySpin
    pyspin_error = None
except ImportError as pyspin_error:
    pass

class Spinnaker(BaseCam):

    NAME = 'SPN'


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
        self._generate_attrs()

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
            BGR = np.repeat(im.GetNDArray()[..., np.newaxis], repeats=3, axis=-1)

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
    def exposure(self, value: Union[float, str]):
        if value == 'AUTO':
            self.c.ExposureAuto.SetValue(PySpin.ExposureAuto_Continuous)
        else:
            self.c.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
            self.c.ExposureMode.SetValue(PySpin.ExposureMode_Timed)
            self.c.ExposureTime.SetValue(float(value))

    @property
    def gain(self):
        self.c.Gain.GetValue()

    @gain.setter
    def gain(self, value: Union[float, str]):
        if value == 'AUTO':
            self.c.GainAuto.SetValue(PySpin.GainAuto_Continuous)
        else:
            self.c.GainAuto.SetValue(PySpin.GainAuto_Off)
            self.c.Gain.SetValue(float(value))

    def optimize_auto_exposure(self):
        self.setattr('AutoExposureControlLoopDamping', 0.1)
        self.setattr('AutoExposureLightingMode_Val', 2)  # Frontlight
        self.setattr('AutoExposureExposureTimeLowerLimit', 6)
        self.setattr('AutoExposureExposureTimeUpperLimit', 30000)
        self.setattr('AutoExposureEVCompensation', 3)

    @property
    def external_trigger(self):
        return self.c.TriggerMode.GetValue()

    @external_trigger.setter
    def external_trigger(self, value: bool = False):
        self.c.TriggerMode.SetValue(PySpin.TriggerMode_Off)

        if value:
            self.c.TriggerSource.SetValue(PySpin.TriggerSource_Line3)
            self.c.TriggerOverlap.SetValue(PySpin.TriggerOverlap_ReadOut)
            self.c.TriggerMode.SetValue(PySpin.TriggerMode_On)

    def _generate_attrs(self):

        self._rw_modes = {
            PySpin.RO: "read only",
            PySpin.RW: "read/write",
            PySpin.WO: "write only",
            PySpin.NA: "not available"
        }

        self._attr_types = {
            PySpin.intfIFloat: PySpin.CFloatPtr,
            PySpin.intfIBoolean: PySpin.CBooleanPtr,
            PySpin.intfIInteger: PySpin.CIntegerPtr,
            PySpin.intfIEnumeration: PySpin.CEnumerationPtr,
            PySpin.intfIString: PySpin.CStringPtr,
        }

        self._attr_type_names = {
            PySpin.intfIFloat: 'float',
            PySpin.intfIBoolean: 'bool',
            PySpin.intfIInteger: 'int',
            PySpin.intfIEnumeration: 'enum',
            PySpin.intfIString: 'string',
            PySpin.intfICommand: 'command',
        }

        self.camera_attributes = {}
        self.camera_methods = {}
        self.camera_node_types = {}

        for node in self.c.GetNodeMap().GetNodes():
            pit = node.GetPrincipalInterfaceType()
            name = node.GetName()
            self.camera_node_types[name] = self._attr_type_names.get(pit, pit)
            if pit == PySpin.intfICommand:
                self.camera_methods[name] = PySpin.CCommandPtr(node)
            if pit in self._attr_types:
                self.camera_attributes[name] = self._attr_types[pit](node)
        self.initialized = True

    def getattr(self, attr):
        if attr in self.camera_attributes:

            prop = self.camera_attributes[attr]
            if not PySpin.IsReadable(prop):
                raise AttributeError("Camera property '%s' is not readable" % attr)

            if hasattr(prop, "GetValue"):
                return prop.GetValue()
            elif hasattr(prop, "ToString"):
                return prop.ToString()
            else:
                raise AttributeError("Camera property '%s' is not readable" % attr)
        elif attr in self.camera_methods:
            return self.camera_methods[attr].Execute
        else:
            raise AttributeError(attr)

    def setattr(self, attr, val):
        if attr in self.camera_attributes:

            prop = self.camera_attributes[attr]
            if not PySpin.IsWritable(prop):
                raise AttributeError("Property '%s' is not currently writable!" % attr)

            if hasattr(prop, 'SetValue'):
                prop.SetValue(val)
            else:
                prop.FromString(val)

        elif attr in self.camera_methods:
            raise AttributeError("Camera method '%s' is a function -- you can't assign it a value!" % attr)
        else:
            if attr not in self.__dict__ and self.lock and self.initialized:
                raise AttributeError("Unknown property '%s'." % attr)
            else:
                raise AttributeError(attr)

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

    def enable_gpio_strobe(self):
        self._set_gpio_strobe(enable=True)

    def disable_gpio_strobe(self):
        self._set_gpio_strobe(enable=False)

    def set_node_and_entry(self, node_name: str, entry_name: str):
        nodemap = self.c.GetNodeMap()

        node = PySpin.CEnumerationPtr(nodemap.GetNode(node_name))
        if not PySpin.IsAvailable(node) or not PySpin.IsWritable(node):
            raise ValueError(f"Cannot retrieve node {node_name}.")

        entry = node.GetEntryByName(entry_name)
        if not PySpin.IsAvailable(entry) or not PySpin.IsReadable(entry):
            raise ValueError(f"Cannot retrieve entry {entry_name} from node {node_name}.")

        node.SetIntValue(entry.GetValue())

    def _set_gpio_strobe(self, line: str = "Line2", enable: bool = True):
        # from PySpin/Examples/Python3/CounterAndTimer.py
        # from https://github.com/CapAI/misc/blob/a22cd50e90018c03cde3c1339aa622185502bb05/spinnaker/pyspin/Examples/Python3/CounterAndTimer.py#L193
        if enable:
            line_mode = "Output"
        else:
            line_mode = "Input"

        # Select line to control
        self.set_node_and_entry("LineSelector", line)
        self.set_node_and_entry("LineMode", line_mode)
        self.set_node_and_entry("LineSource", "ExposureActive")

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
