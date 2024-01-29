"""etho"""
__version__ = "0.16.1"
# load global config on import
try:
    from .utils.config import readconfig
    config = readconfig()
except FileNotFoundError as e:
    print('No configuration fiel found. Run `etho init`')

