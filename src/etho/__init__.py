__version__ = "0.9.1"
# load global config on import
from .utils.config import readconfig

config = readconfig()
