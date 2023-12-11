import time
import logging
import numpy as np
from typing import Tuple, Optional
from .base import BaseCam, gray2rgb

try:
    import pypylon.pylon as py
    pylon_error = None
except ImportError as pylon_error:
    pass


class Basler(BaseCam):
    NAME = "BAS"

    def __init__(self, serialnumber):
        if pylon_error is not None:
            raise pylon_error
        self.serialnumber = str(serialnumber)
        self.timestamp_offset = 0
        # self.im = PyCapture2.Image()

    def init(self):
        # self.bus =
        devices = py.TlFactory.GetInstance().EnumerateDevices()
        dev_dict = {d.GetSerialNumber(): d for d in devices}

        self.c = py.InstantCamera(py.TlFactory.GetInstance().CreateDevice(dev_dict[self.serialnumber]))
        self.c.Open()
        self.timestamp_offset = self._estimate_timestamp_offset()
        self.c.Chunk.Enable.Value = True
        self.c.PixelFormat.Value = "Mono8"

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
        res = self.c.RetrieveResult(1000)  # 1s timeout
        if res.GrabSucceeded():
            self.im = res
            system_ts = time.time()
        else:
            raise ValueError("Image is None.")

        # convert timestamp
        image_ts = self.im.TimeStamp

        # convert image
        image = self.im.Array
        image = gray2rgb(image)
        return image, image_ts, system_ts

    def _estimate_timestamp_offset(self) -> float:
        return 0

    @property
    def roi(self) -> Tuple[int, int, int, int]:
        return self.c.OffsetX.Value, self.c.OffsetY.Value, self.c.Width.Value, self.c.Height.Value

    @roi.setter
    def roi(self, x0_y0_x_y: Tuple[int, int, int, int]):
        try:
            x0, y0, x, y = x0_y0_x_y
        except ValueError:
            raise ValueError(f"Input {x0_y0_x_y} should be a 4-tuple.")
        try:
            self.c.OffsetX.Value = x0
            self.c.OffsetY.Value = y0
            self.c.Width.Value = x
            self.c.Height.Value = y
        except Exception as e:
            logging.exception(f"Failed setting ROI from input {x0_y0_x_y}", exc_info=e)
            x = self._min_max_inc("width", int(x), set_value=False)
            y = self._min_max_inc("height", int(y), set_value=False)
            x0 = self._min_max_inc("offsetX", int(x0), set_value=False)
            y0 = self._min_max_inc("offsetY", int(y0), set_value=False)
            logging.info(f"Trying again with these values {[x0, y0, x, y]}")
            try:
                self.c.OffsetX.Value = x0
                self.c.OffsetY.Value = y0
                self.c.Width.Value = x
                self.c.Height.Value = y
            except Exception as e:
                logging.exception(f"Failed setting ROI from input {x0_y0_x_y}", exc_info=e)
                raise
        pass

    def _min_max_inc(self, prop: str, value: int = None, set_value=True):
        prop_map = {
            "width": {"max_val": self.c.Width.Max, "min_val": self.c.Width.Max, "inc": self.c.Width.Max},
            "height": {"max_val": self.c.Height.Max, "min_val": self.c.Height.Max, "inc": self.c.Height.Max},
            "offsetX": {"max_val": self.c.OffsetX.Max, "min_val": self.c.OffsetX.Max, "inc": self.c.OffsetX.Max},
            "offsetY": {"max_val": self.c.OffsetY.Max, "min_val": self.c.OffsetY.Max, "inc": self.c.Offsety.Max},
        }

        if value is not None:
            value = np.clip(value, prop_map[prop]["min_val"], prop_map[prop]["max_val"])
            value = np.round(value / prop_map[prop]["inc"]) * prop_map[prop]["inc"]
        return value

    @property
    def brightness(self):
        return self.c.BslBrightness.Value

    @brightness.setter
    def brightness(self, value: float):
        self.c.BslBrightness.Value = value

    @property
    def exposure(self):
        return self.c.ExposureTime.Value / 1_00  # convert usec to ms

    @exposure.setter
    def exposure(self, value: float):
        self.c.ExposureAuto.Value = "Off"
        self.c.ExposureTime.Value = value * 1_000  # convert ms to usec

    @property
    def gain(self):
        return self.c.Gain.Value

    @gain.setter
    def gain(self, value: float):
        self.c.Gain.Value = value

    @property
    def gamma(self):
        return self.c.Gamma.Value

    @gamma.setter
    def gamma(self, value: float):
        self.c.Gamma.Value = value

    @property
    def framerate(self):
        return self.c.AcquisitionFrameRate.Value


    @framerate.setter
    def framerate(self, value: float):
        self.c.AcquisitionFrameRateEnable.Value = True
        self.c.AcquisitionFrameRate.Value = value

    def start(self):
        self.c.StartGrabbing()

    def stop(self):
        try:
            self.c.StopGrabbing()
        except Exception as e:
            print(e)

    def close(self):
        self.stop()
        self.c.Close()

    def reset(self):
        """Reset the camera system to free all resources."""
        # self.bus.FireBusReset(self.guid)
        pass  # self.bus.rescanBus()  # does not reset but "invalidates all current camera connections"

    def info_hardware(self):
        cam_info = self.c.DeviceInfo()

        info = {
            "Serial number": cam_info.GetSerialNumber(),
            "Camera model": cam_info.di.GetModelName().decode("utf-8"),
            "Camera vendor": cam_info.GetVendorName().decode("utf-8"),
            # "Sensor": cam_info.sensorInfo.decode("utf-8"),
            # "Resolution": cam_info.sensorResolution.decode("utf-8"),
            # "Firmware version": cam_info.firmwareVersion.decode("utf-8"),
            # "Firmware build time": cam_info.firmwareBuildTime.decode("utf-8"),
        }
        return info
