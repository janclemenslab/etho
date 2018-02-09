import configparser

def getlist(string, delimiter=',', stripwhitespace=True):
    stringlist = string.split(delimiter)
    if stripwhitespace:
        stringlist = [item.strip() for item in stringlist]
    return stringlist


def readconfig(filename='config.ini'):
    config = configparser.ConfigParser()
    config.read(filename)
    sections = config.sections()

    configDict = {}
    for section in sections:
        sectionList = list(config[section].items())
        sectionDict = {}
        for item in sectionList:
            sectionDict[item[0]] = getlist(item[1])
        configDict[section] = sectionDict
    return configDict


if __name__ == '__main__':
    print(readconfig('config.ini'))
