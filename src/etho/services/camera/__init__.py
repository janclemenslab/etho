from .spinnaker import Spinnaker
from .ximea import Ximea
from .flycapture2 import FlyCapture2
from .hamamatsu import Hamamatsu
from .videocapture import VideoCapture
from .dummy import Dummy

make = {
    "Spinnaker": Spinnaker,
    "Ximea": Ximea,
    "PyCapture": FlyCapture2,
    "FlyCapture2": FlyCapture2,
    "Hamamatsu": Hamamatsu,
    "VideoCapture": VideoCapture,
    "Dummy": Dummy,
}
