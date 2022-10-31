import numpy as np
from typing import Tuple, Optional
import time
from .base import BaseCam
import cv2


class Dummy(BaseCam):

    def __init__(self, serialnumber: int):
        """Dummy cam returning noise frames

        Args:
            serialnumber ([type]): [description]
        """
        self.serialnumber: int = serialnumber

    def init(self, *args, **kwargs):
        self._t0 = time.time()

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
        time.sleep(1 / (1.11 * self._framerate))
        system_timestamp = time.time()
        image_timestamp = system_timestamp - self._t0

        image = np.random.randint(0, 64, size=(self._roi[2], self._roi[3], 3), dtype=np.uint8)
        image = cv2.putText(image,
                            f"{image_timestamp: 1.3f} s",
                            org=(20, 100),
                            fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                            fontScale=1,
                            color=(128, 64, 96),
                            thickness=2,
                            lineType=2)

        return image, image_timestamp, system_timestamp

    def _estimate_timestamp_offset(self) -> float:
        """[summary]

        Returns:
            float: Timestamp offset rel to system time.
                   Return 0 if timestamps are already in system time.
        """
        return 0

    @property
    def roi(self) -> Tuple[int, int, int, int]:
        x0, y0, x, y = self._roi
        return x0, y0, x, y

    @roi.setter
    def roi(self, x0_y0_x_y: Tuple[int, int, int, int]):
        self._roi = x0_y0_x_y

    @property
    def framerate(self) -> float:
        return self._framerate

    @framerate.setter
    def framerate(self, value: float):
        self._framerate = value

    @property
    def brightness(self) -> float:
        return self._brightness

    @brightness.setter
    def brightness(self, value: float):
        self._brightness = value

    @property
    def exposure(self) -> float:
        return self._exposure

    @exposure.setter
    def exposure(self, value: float):
        self._exposure = float(value)

    @property
    def gain(self) -> float:
        return self._gain

    @gain.setter
    def gain(self, value: float):
        self._gain = float(value)

    @property
    def gamma(self):
        return self._gamma

    @gamma.setter
    def gamma(self, value: float):
        self._gamma = value

    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        pass

    def reset(self):
        """Reset the camera system to free all resources."""
        pass

    def info_imaging(self):
        x0, y0, x, y = self.roi
        info = {
            'width': x,
            'height': y,
            'offsetX': x0,
            'offsetY': y0,
            'exposure': self.exposure / 1_000,
            'brightness': self.brightness,
            'gamma': self.gamma,
            'gain': self.gain,
            'framerate': self.framerate,
        }
        return info
