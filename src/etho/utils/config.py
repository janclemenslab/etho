import pathlib
import os
from collections import defaultdict

# Find global config file
HOME = str(pathlib.Path.home())
GLOBALCONFIGFILEPATH = os.path.join(HOME, "ethoconfig.yml")
if not os.path.exists(GLOBALCONFIGFILEPATH):
    raise FileNotFoundError("no config file found. should be ~/ethoconfig.yml or ~/ethoconfig.yml")


def defaultify(d, defaultfactory=lambda: None):
    """Convert nested dict to defaultdict."""
    if not isinstance(d, dict):
        return d
    return defaultdict(defaultfactory, {k: defaultify(v, defaultfactory) for k, v in d.items()})


def undefaultify(d):
    if not isinstance(d, dict):
        return d
    return {k: undefaultify(v) for k, v in d.items()}


def saveconfig(filename, prot):
    import yaml

    prot = undefaultify(prot)
    with open(filename, "w") as f:
        yaml.dump(prot, f)


def readconfig(filename=GLOBALCONFIGFILEPATH):
    import yaml

    with open(filename, "r") as f:
        config_dict = yaml.load(f.read(), Loader=yaml.FullLoader)
    return defaultify(config_dict)
