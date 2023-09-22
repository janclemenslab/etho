"""etho"""
__version__ = "0.12.0"
# load global config on import
from .utils.config import readconfig

config = readconfig()
