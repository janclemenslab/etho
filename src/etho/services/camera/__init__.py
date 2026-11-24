from .spinnaker import Spinnaker
from .spinnaker_old import Spinnaker_OLD
from .ximea import Ximea
from .basler import Basler
from .hamamatsu import Hamamatsu
from .dummy import Dummy
from .webcam import Webcam, list_webcams

make = {
    "Spinnaker_OLD": Spinnaker_OLD,
    "Spinnaker": Spinnaker,
    "Ximea": Ximea,
    "Basler": Basler,
    "Hamamatsu": Hamamatsu,
    "Dummy": Dummy,
    "Webcam": Webcam,
}
