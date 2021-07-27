"""
Define your own class here (see examples below for how to do that),
decorate with `@register_runner`.
Then select runners and set init params in prot file: 
`
DLP:
  runners:
    LED_blinker:  # this needs to be the name of the class
      object: 'Rect'  # should be the classname: psychopy.visuals.NAME
      led_frame: 360
      led_duration: 180
    LED_blinker_file:
      object: 'Rect'  # should be the classname: psychopy.visuals.NAME
      filename: `absolute_path_to_file/filename.npz`  # needs to have fields as expected by the class
`
"""
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from typing import Callable, Optional, Dict


# Populated by decorating classes with `register_runner`. 
# Enables selecting runners by string in `DLPZeroService`.
runners = dict()

def register_runner(cls: Callable):
    """Adds func to model_dict Dict[str: Class]. For selecting runners by string."""
    runners[cls.__name__] = cls
    return cls


class DLP_runner():
    """Base class for all runners."""

    def __init__(self, win, **kwargs):
        """All variants need to accept `win` as the first param

        Args:
            win (psychopy.visual.Window): PsychoPy win instance
        """
        pass

    def update(self, frame_number: int, **kwargs) -> Dict:
        """Will be called by DLPZeroService on every frame."""
        raise NotImplementedError()

    def status(self) -> Dict:  # Dict[key:str, value:int/float]
        """Generate status message."""
        return {}

    def destroy(self):
        """Free any resources (close files etc)."""
        pass


@register_runner
class LED_blinker(DLP_runner):
    """Blinking square read in by a photodiode for syncing DLP frames with DAQ samples."""

    def __init__(self, win, object, led_size = 0.3, led_pos = [-1,-0.3], led_frame = 180*60, led_duration = 180, **kwignore):
        """Set up LED blinker

        Args:
            win (psychopy.visual.Window): PsychoPy win instance
            object (e.g. psychopy.visual.Rect/Circle): Geometric object to manipulate on screen. Specify in protocol file as string.
            led_size (float, optional): [description]. Defaults to 0.3.
            led_pos (list, optional): [description]. Defaults to [-1,-0.3].
            led_frame ([type], optional): [description]. Defaults to 180*60.
            led_duration (int, optional): [description]. Defaults to 180.
            kwignore (Dict): Extra args to ignore for robustness when passing unspecified parameters.
        """
        self.led_size = led_size
        self.led_pos = led_pos
        self.led_frame = led_frame
        self.led_duration = led_duration
        self.win = win

        self.rectangle = object(win=self.win, units='norm', size=self.led_size, pos=self.led_pos,
                                autoDraw = True, fillColor=[-1, -1, -1], lineWidth=0, opacity=1)

    def update(self, frame_number: int, ball_info: Dict, **kwargs: Optional[Dict]):
        """Update LED blinker.

        Args:
            frame_number (int): [description]
            ball_info (Dict): from fictrac (not used)
            **kwargs (Optional[Any]): could be externally set positions, e.g. during closed loop (not used)

        Returns:
            Dict[str: float/int]: values should be numbers - not lists or np.arrays!
        """
        if frame_number % self.led_frame == 0:
            self.rectangle.opacity = 0

        if (frame_number - self.led_duration) % self.led_frame == 0:
            self.rectangle.opacity = 1

        return self.status()

    def status(self):
        """Generate status message."""
        log_msg = {'opacity': self.rectangle.opacity}
        return log_msg

    def destroy(self, **kwargs):
        """Free any resources (close files etc)."""
        pass




# Example with stim control via param file
@register_runner
class LED_blinker_file(DLP_runner):
    """Blinking square - opacity controlled by `opacity` field in npz file."""

    def __init__(self, win, object, filename: str, led_size = 0.3, led_pos = [-1,-0.3], **kwignore):
        """Set up LED blinker.

        Args:
            win (psychopy.visual.Window): PsychoPy win instance
            object, e.g. psychopy.visual.Rect
            filename (str): file with stim params
            led_size (float, optional): [description]. Defaults to 0.3.
            led_pos (list, optional): [description]. Defaults to [-1,-0.3].
            kwignore (Dict): Extra args to ignore for robustness when passing unspecified parameters.

        Returns:
            Dict[str: float/int]: values should be numbers - not lists or np.arrays!

        """
        self.led_size = led_size
        self.led_pos = led_pos

        self.rectangle = object(win=win, units = 'norm', size=self.led_size, pos=self.led_pos,
                              autoDraw = True, fillColor=[-1, -1, -1], lineWidth=0, opacity=1)

        # do not use plain arrays - either pd.DataFrames.read_csv, or np.recarrays
        # so we parameters in the data are more obvious
        # if filename is list -> load all extend the list
        self.params = np.load(filename)

    def update(self, frame_number: int, ball_info: Dict, kwargs: Optional[Dict]):
        """Update LED blinker.

        Args:
            frame_number (int): [description]
            ball_info (Dict): from fictrac
            **kwargs (Optional[Any]): could be externally set positions, e.g. during closed loop
        Returns:
            Dict[str: float/int]: values should be numbers - not lists or np.arrays!
        """
        self.rectangle.opacity = self.params['opacity'][frame_number]
        return self.status()

    def status(self):
        """Generate status message."""
        log_msg = {'opacity': self.rectangle.opacity}
        return log_msg
