from ethomaster import config
from ethomaster.utils.config import readconfig

print(config)

print(readconfig('test/test_config.ini'))
print(readconfig('test/test_config.yaml'))
print(type(readconfig('test/test_config.yaml')))
