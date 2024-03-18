"""etho"""
__version__ = "0.17.0"
# load global config on import
try:
    from .utils.config import readconfig
    config = readconfig()
except FileNotFoundError as e:
    print('No configuration file found. Run `etho init`')

