"""etho"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("etho-python")
except PackageNotFoundError:
    __version__ = "0+unknown"

# load global config on import
try:
    from .utils.config import defaultify, readconfig

    config = readconfig()
except FileNotFoundError:
    print("No configuration file found. Run `etho init`")
    config = defaultify({})
