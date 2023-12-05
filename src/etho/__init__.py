"""etho"""
__version__ = "0.14.0"
# load global config on import
from .utils.config import readconfig

config = readconfig()
