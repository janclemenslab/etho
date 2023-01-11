import time
import logging
import numpy as np
from typing import Tuple, Optional
from .base import BaseCam, gray2rgb

try:
    import PyCapture2

    pycapture_error = None
except ImportError as e:
    pycapture_error = e


class FlyCapture2(BaseCam):
    NAME = "CAP"

    def __init__(self, serialnumber):
        if pycapture_error is not None:
            raise pycapture_error
        self.serialnumber = int(serialnumber)
        self.timestamp_offset = 0
        self.im = PyCapture2.Image()

    def init(self):
        self.bus = PyCapture2.BusManager()
        self.c = PyCapture2.Camera()
        self.uid = self.bus.getCameraFromSerialNumber(self.serialnumber)
        self.c.connect(self.uid)
        self.timestamp_offset = self._estimate_timestamp_offset()
        self.c.setEmbeddedImageInfo(timestamp=True)

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
            raise ValueError("Image is None.")

        # convert timestamp
        ts = self.im.getTimeStamp()
        image_ts = ts.seconds + ts.microSeconds / 1_000_000

        # convert image
        image = self.im.getData()
        image = image.reshape((self.im.getRows(), self.im.getCols(), -1))
        image = image.astype(np.uint8)
        image = gray2rgb(image)
        return image, image_ts, system_ts

    def _estimate_timestamp_offset(self) -> float:
        return 0

    @property
    def roi(self) -> Tuple[int, int, int, int]:
        imageSettings, packetSize, percentage = self.c.getFormat7Configuration()
        return imageSettings.offsetX, imageSettings.offsetY, imageSettings.width, imageSettings.height

    @roi.setter
    def roi(self, x0_y0_x_y: Tuple[int, int, int, int]):
        try:
            x0, y0, x, y = x0_y0_x_y
        except ValueError:
            raise ValueError(f"Input {x0_y0_x_y} should be a 4-tuple.")
        try:
            fmt7_img_set = PyCapture2.Format7ImageSettings(0, x0, y0, x, y, PyCapture2.PIXEL_FORMAT.MONO8)
            fmt7_pkt_inf, isValid = self.c.validateFormat7Settings(fmt7_img_set)
            self.c.setFormat7ConfigurationPacket(fmt7_pkt_inf.maxBytesPerPacket, fmt7_img_set)
        except Exception as e:
            logging.exception(f"Failed setting ROI from input {x0_y0_x_y}", exc_info=e)
            self.c.setFormat7Configuration(100.0, offsetX=0, offsetY=0)
            x = self._min_max_inc("width", int(x), set_value=False)
            y = self._min_max_inc("height", int(y), set_value=False)
            x0 = self._min_max_inc("offsetX", int(x0), set_value=False)
            y0 = self._min_max_inc("offsetY", int(y0), set_value=False)
            logging.info(f"Trying again with these values {[x0, y0, x, y]}")
            try:
                fmt7_img_set = PyCapture2.Format7ImageSettings(0, x0, y0, x, y, PyCapture2.PIXEL_FORMAT.MONO8)
                fmt7_pkt_inf, isValid = self.c.validateFormat7Settings(fmt7_img_set)
                self.c.setFormat7ConfigurationPacket(fmt7_pkt_inf.maxBytesPerPacket, fmt7_img_set)
            except Exception as e:
                logging.exception(f"Failed setting ROI from input {x0_y0_x_y}", exc_info=e)
                raise
        pass

    def _min_max_inc(self, prop: str, value: int = None, set_value=True):
        info, isValid = self.c.getFormat7Info(PyCapture2.MODE.MODE_0)
        prop_map = {
            "width": {"max_val": info.maxWidth, "min_val": info.minWidth, "inc": info.imageHStepSize},
            "height": {"max_val": info.maxHeight, "min_val": info.minHeight, "inc": info.imageVStepSize},
            "offsetX": {"max_val": info.maxWidth, "min_val": 0, "inc": info.offsetHStepSize},
            "offsetY": {"max_val": info.maxHeight, "min_val": 0, "inc": info.offsetVStepSize},
        }

        if value is not None:
            value = np.clip(value, prop_map[prop]["min_val"], prop_map[prop]["max_val"])
            value = np.round(value / prop_map[prop]["inc"]) * prop_map[prop]["inc"]
            if set_value:
                self.c.setFormat7Configuration(100.0, **{prop: int(value)})
                imageSettings, packetSize, percentage = self.c.getFormat7Configuration()
                value = getattr(imageSettings, prop)
        return value

    @property
    def brightness(self):
        return self.c.getProperty(PyCapture2.PROPERTY_TYPE.BRIGHTNESS).absValue

    @brightness.setter
    def brightness(self, value: float):
        self.c.setProperty(
            type=PyCapture2.PROPERTY_TYPE.BRIGHTNESS, absValue=float(value), absControl=True, autoManualMode=True
        )

    @property
    def exposure(self):
        # convert to ns
        return self.c.getProperty(PyCapture2.PROPERTY_TYPE.SHUTTER).absValue * 1_000

    @exposure.setter
    def exposure(self, value: float):
        self.c.setProperty(type=PyCapture2.PROPERTY_TYPE.AUTO_EXPOSURE, absValue=float(0), autoManualMode=False, onOff=True)
        self.c.setProperty(type=PyCapture2.PROPERTY_TYPE.SHUTTER, absValue=int(value / 1_000), autoManualMode=False)

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
        self.c.setProperty(type=PyCapture2.PROPERTY_TYPE.GAMMA, absValue=float(value), onOff=True)

    @property
    def framerate(self):
        return self.c.getProperty(PyCapture2.PROPERTY_TYPE.FRAME_RATE).absValue

    @framerate.setter
    def framerate(self, value: float):
        self.c.setProperty(type=PyCapture2.PROPERTY_TYPE.AUTO_EXPOSURE, absValue=float(0), autoManualMode=False, onOff=True)
        self.c.setProperty(type=PyCapture2.PROPERTY_TYPE.FRAME_RATE, absValue=float(value), autoManualMode=False, onOff=True)

    def start(self):
        self.c.startCapture()

    def stop(self):
        try:
            self.c.stopCapture()
        except Exception as e:
            print(e)

    def close(self):
        self.stop()
        self.c.disconnect()

    def reset(self):
        """Reset the camera system to free all resources."""
        # self.bus.FireBusReset(self.guid)
        self.bus.rescanBus()  # does not reset but "invalidates all current camera connections"

    def info_hardware(self):
        cam_info = self.c.getCameraInfo()
        info = {
            "Serial number": cam_info.serialNumber,
            "Camera model": cam_info.modelName.decode("utf-8"),
            "Camera vendor": cam_info.vendorName.decode("utf-8"),
            "Sensor": cam_info.sensorInfo.decode("utf-8"),
            "Resolution": cam_info.sensorResolution.decode("utf-8"),
            "Firmware version": cam_info.firmwareVersion.decode("utf-8"),
            "Firmware build time": cam_info.firmwareBuildTime.decode("utf-8"),
        }
        return info
