from .spinnaker import Spinnaker
from .ximea import Ximea
from .basler import Basler
from .hamamatsu import Hamamatsu
from .dummy import Dummy

make = {
    "Spinnaker": Spinnaker,
    "Ximea": Ximea,
    "Basler": Basler,
    "Hamamatsu": Hamamatsu,
    "Dummy": Dummy,
}
