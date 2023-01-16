import pathlib
import os
from collections import defaultdict
import yaml
from typing import Dict, Union


# Find global config file
HOME = str(pathlib.Path.home())
GLOBALCONFIGFILEPATH = os.path.join(HOME, "ethoconfig.yml")
if not os.path.exists(GLOBALCONFIGFILEPATH):
    raise FileNotFoundError("No config file found. Should be at ~/ethoconfig.yml")


def defaultify(d: Dict, defaultfactory=lambda: None) -> defaultdict:
    """Convert nested dict to defaultdict."""
    if not isinstance(d, dict):
        return d
    return defaultdict(defaultfactory, {k: defaultify(v, defaultfactory) for k, v in d.items()})


def undefaultify(d: Union[Dict, defaultdict]) -> Dict:
    if not isinstance(d, dict):
        return d
    return {k: undefaultify(v) for k, v in d.items()}


def saveconfig(filename: str, prot: Union[Dict, defaultdict]):
    prot = undefaultify(prot)
    with open(filename, "w") as f:
        yaml.dump(prot, f)


def readconfig(filename: str = GLOBALCONFIGFILEPATH) -> defaultdict:
    with open(filename, "r") as f:
        config_dict = yaml.load(f.read(), Loader=yaml.FullLoader)
    return defaultify(config_dict)
