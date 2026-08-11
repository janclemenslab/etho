from .spinnaker import Spinnaker
from .spinnaker_old import Spinnaker_OLD
from .ximea import Ximea
from .basler import Basler
from .hamamatsu import Hamamatsu
from .dummy import Dummy

make = {
    "Spinnaker_OLD": Spinnaker_OLD,
    "Spinnaker": Spinnaker,
    "Ximea": Ximea,
    "Basler": Basler,
    "Hamamatsu": Hamamatsu,
    "Dummy": Dummy,
}
