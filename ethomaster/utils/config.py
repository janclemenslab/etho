import pathlib
import os
from collections import defaultdict

# find_global_config_file():
HOME = str(pathlib.Path.home())
GLOBALCONFIGFILEPATH = os.path.join(HOME, 'ethoconfig.yml')
if not os.path.exists(GLOBALCONFIGFILEPATH):
    GLOBALCONFIGFILEPATH = os.path.join(HOME, 'ethoconfig.ini') # ~/ethoconfig.ini
if not os.path.exists(GLOBALCONFIGFILEPATH):
    raise FileNotFoundError('no config file found. should be ~/ethoconfig.yml or ~/ethoconfig.yml')


def getlist(string, delimiter=',', stripwhitespace=True):
    stringlist = string.split(delimiter)
    if stripwhitespace:
        stringlist = [item.strip() for item in stringlist]
    return stringlist


def readconfig(filename=GLOBALCONFIGFILEPATH):
    if filename.endswith(('.yml', '.yaml')):
        config = readconfig_yaml(filename)
    else:
        config = readconfig_ini(filename)
    return defaultdict(lambda:None, config.items())


def readconfig_yaml(filename):
    import yaml
    with open(filename, 'r') as f:
        config_dict = yaml.load(f.read())
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
            # is_list = item[1].strip().startswith('[') and item[1].strip().endswith(']')
            # item[1] = item[1].strip()[1:-2]

            is_tuple = '(' in item[1] and ')' in item[1]
            if is_list and not is_tuple:
                sectionDict[item[0]] = getlist(item[1])
            else:
                sectionDict[item[0]] = item[1]
        configDict[section] = sectionDict
    return configDict
