from .spinnaker import Spinnaker
from .ximea import Ximea
from .flycapture2 import FlyCapture2
from .spinnaker_old import Spinnaker_OLD
from .basler import Basler
from .hamamatsu import Hamamatsu
from .videocapture import VideoCapture
from .dummy import Dummy

make = {
    "Spinnaker": Spinnaker,
    "Spinnaker_OLD": Spinnaker_OLD,
    "Ximea": Ximea,
    "PyCapture": FlyCapture2,
    "FlyCapture2": FlyCapture2,
    "Basler": Basler,
    "Hamamatsu": Hamamatsu,
    # "VideoCapture": VideoCapture,
    "Dummy": Dummy,
}
