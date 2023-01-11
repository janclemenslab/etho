from .spinnaker import Spinnaker
from .ximea import Ximea
from .flycapture2 import FlyCapture2
from .dummy import Dummy

make = {"Spinnaker": Spinnaker, "Ximea": Ximea, "PyCapture": FlyCapture2, "FlyCapture2": FlyCapture2, "Dummy": Dummy}
