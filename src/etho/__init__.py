"""etho"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("etho-python")
except PackageNotFoundError:
    __version__ = "0+unknown"

# load global config on import
try:
    from .utils.config import readconfig

    config = readconfig()
except FileNotFoundError as e:
    print("No configuration file found. Run `etho init`")
