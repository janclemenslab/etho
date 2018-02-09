import configparser

def getlist(string, delimiter=',', stripwhitespace=True):
    stringlist = string.split(delimiter)
    if stripwhitespace:
        stringlist = [item.strip() for item in stringlist]
    return stringlist

def readconfig(filename='config.ini'):
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


if __name__ == '__main__':
    print(readconfig('config.ini'))
