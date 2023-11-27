"""etho"""
__version__ = "0.12.1"
# load global config on import
from .utils.config import readconfig

config = readconfig()
