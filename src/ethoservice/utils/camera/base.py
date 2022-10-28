import numpy as np
from typing import Tuple, Optional


def gray2rgb(image: np.ndarray) -> np.ndarray:
    if image.shape[-1] != 3:
        image = np.tile(image, (1, 1, 3))
    return image


class BaseCam():

    def __init__(self, serialnumber: int):
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
        self.serialnumber: int = serialnumber

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

    def info_hardware(self):
        pass

    def info_imaging(self):
        x0, y0, x, y = self.roi
        info = {'width': x, 'height': y,
                'offsetX': x0, 'offsetY': y0,
                'exposure': self.exposure / 1_000,
                'brightness': self.brightness,
                'gamma': self.gamma,
                'gain': self.gain,
                'framerate': self.framerate,
                }
        return info