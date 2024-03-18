from typing import Optional, Dict, Any
import logging
import numpy as np
from .config import readconfig, undefaultify


logger = logging.getLogger(__name__)


def parse(filename):
    calibration_data = undefaultify(readconfig(filename))

    calibrations = {}
    for key, val in calibration_data.items():
        try:
            if "frequency" in val:
                calibrations[key] = CalibrationLinear(val["output"], val["gain"], val["frequency"], attr=val)
            else:
                calibrations[key] = CalibrationCurve(val["output"], val["gain"], attr=val)
        except Exception as e:
            logging.exception(f'Something went wrong parsing calibrations from block "{key}" in {filename}.', exc_info=e)
    return calibrations


class CalibrationCurve:
    # nonlinear gain, calibrated at a single frequency, multiple intensities

    def __init__(
        self,
        intensities: np.ndarray[float],
        gains: np.ndarray[float],
        frequencies: Optional[np.ndarray[float]] = None,
        interpolate: Optional[bool] = True,
        extrapolate: Optional[bool] = True,
        attr: Optional[Dict[str, Any]] = None,
    ):
        self.intensities = intensities
        self.gains = gains
        self.interpolate = interpolate
        self.extrapolate = extrapolate
        self.attr = attr if attr is not None else {}
        print(self.attr)

        self.data = {o: g for o, g in zip(self.intensities, self.gains)}

    def __str__(self):
        try:
            return f"Calbration curve for outputs in {self.attr['output_units']}."
        except:
            return super().__str__()

    def __call__(self, intensity, frequency=None):
        if self.interpolate:
            gain = np.interp(intensity, self.intensities, self.gains, left=0)
        else:
            print('e')
            gain = self.data[intensity]
        return gain


class CalibrationLinear:
    # linear gain, calibrated at a single intensity, multiple frequencies

    def __init__(
        self, intensities, gains, frequencies, interpolate=True, extrapolate=True, attr: Optional[Dict[str, Any]] = None
    ):
        self.intensities = np.asarray(intensities)
        self.gains = np.asarray(gains)
        self.frequencies = np.asarray(frequencies)
        self.attr = attr if attr is not None else {}

        if len(self.intensities) != len(self.gains) or len(self.intensities) != len(self.frequencies):
            raise ValueError(
                f"Intensities, gains and frequencies need to have the same length but have {len(self.intensities)}, {len(self.gains)} and {len(self.frequencies)} elements."
            )

        self.gains /= self.intensities  # normalize gains to correspond to intensities of 1.0.
        self.interpolate = interpolate
        self.extrapolate = extrapolate

        self.data = {o: g for o, g in zip(self.frequencies, self.gains)}

    def __call__(self, intensity, frequency=None):
        if self.interpolate:
            gain = intensity * np.interp(frequency, self.frequencies, self.gains)
        else:
            gain = intensity * self.data[frequency]
        return gain
