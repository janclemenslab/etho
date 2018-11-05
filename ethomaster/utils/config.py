import configparser
import pathlib
import os
HOME = str(pathlib.Path.home())
CTRLFILEPATH = os.path.join(HOME, '.ethoconfig.ini') # should be ~/.ethoconfig.ini

def getlist(string, delimiter=',', stripwhitespace=True):
    stringlist = string.split(delimiter)
    if stripwhitespace:
        stringlist = [item.strip() for item in stringlist]
    return stringlist

def readconfig(filename=CTRLFILEPATH):
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


if __name__ == '__main__':
    print(readconfig())
