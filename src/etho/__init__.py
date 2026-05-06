"""etho"""

# load global config on import
try:
    from .utils.config import readconfig

    config = readconfig()
except FileNotFoundError as e:
    print("No configuration file found. Run `etho init`")
