import time
from etho.head.ZeroClient import ZeroClient
from ethoservice.NITriggerZeroService import NIT
import pandas as pd
from etho import config
from etho.utils.config import readconfig


ip_address = 'localhost'
protocolfile = 'protocols/default.txt'
playlistfile = 'playlists/IPItuneChaining.txt'

# load config/protocols
prot = readconfig(protocolfile)
maxDuration = int(3600)


user_name = config['GENERAL']['user']
folder_name = config['GENERAL']['folder']

port="/Dev1/port0/line0:7"
data=np.array([0, 1, 1, 0, 1, 0, 1, 0], dtype=np.uint8)

print([NIT.SERVICE_PORT, NIT.SERVICE_NAME])
nit = ZeroClient("{0}@{1}".format(user_name, ip_address), 'nidaq')
subprocess.Popen('python -m ethoservice.NITZeroService')
nit.connect("tcp://{0}:{1}".format(ip_address, NIT.SERVICE_PORT))
print('done')
print('sending sound data to {0} - may take a while.'.format(ip_address))
nit.setup(-1)
nit.init_local_logger('{0}/{1}_daq.log'.format(dirname, filename))
nit.send(port, data)

nit.finish()
