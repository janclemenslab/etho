import pathlib
import os
from collections import defaultdict

# Find global config file
HOME = str(pathlib.Path.home())
GLOBALCONFIGFILEPATH = os.path.join(HOME, 'ethoconfig.yml')
if not os.path.exists(GLOBALCONFIGFILEPATH):
    GLOBALCONFIGFILEPATH = os.path.join(HOME, 'ethoconfig.ini') # ~/ethoconfig.ini
if not os.path.exists(GLOBALCONFIGFILEPATH):
    raise FileNotFoundError('no config file found. should be ~/ethoconfig.yml or ~/ethoconfig.yml')


def getlist(string, delimiter=',', stripwhitespace=True):
    """Parse [...] or (...) wrapped strings in ini file to a list or tuple."""
    stringlist = string.split(delimiter)
    if stripwhitespace:
        stringlist = [item.strip() for item in stringlist]
    return stringlist


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
    with open(filename, 'w') as f:
        yaml.dump(prot, f)


def readconfig(filename=GLOBALCONFIGFILEPATH):
    """Read ini or yaml config file, defaults to reading the global config."""
    if filename.endswith(('.yml', '.yaml')):
        config = readconfig_yaml(filename)
    else:
        config = readconfig_ini(filename)
    return defaultify(config)


def readconfig_yaml(filename):
    import yaml
    with open(filename, 'r') as f:
        config_dict = yaml.load(f.read(), Loader=yaml.FullLoader)
    return config_dict


def readconfig_ini(filename):
    import configparser
    config = configparser.ConfigParser(inline_comment_prefixes=('#',))
    config.read(filename)
    sections = config.sections()

    configDict = {}
    for section in sections:
        sectionList = list(config[section].items())
        sectionDict = {}
        for item in sectionList:
            is_list = ',' in item[1]
            is_tuple = '(' in item[1] and ')' in item[1]
            if is_list and not is_tuple:
                sectionDict[item[0]] = getlist(item[1])
            else:
                sectionDict[item[0]] = item[1]
        configDict[section] = sectionDict
    return configDict
