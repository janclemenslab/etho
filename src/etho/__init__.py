__version__ = "0.10.0"
# load global config on import
from .utils.config import readconfig

config = readconfig()