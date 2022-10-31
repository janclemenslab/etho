import time
import subprocess
from etho.utils.zeroclient import ZeroClient
from etho.services.ThuAZeroService import THUA
from etho import config


ip_address = 'localhost'
ssh_address = '{0}@localhost'.format(config['GENERAL']['user'])
thu_server_name = 'python -m {0}'.format(THUA.__module__)
folder_name = config['GENERAL']['folder']
thu_service_port = THUA.SERVICE_PORT

print(ssh_address)
print(thu_server_name)
thu = ZeroClient(ssh_address)
# thu.start_server(thu_server_name, folder_name, warmup=1)
subprocess.Popen(thu_server_name, creationflags=subprocess.CREATE_NEW_CONSOLE)
thu.connect("tcp://{0}:{1}".format(ip_address, thu_service_port))
print([THUA.SERVICE_PORT, THUA.SERVICE_NAME])


comport = 'COM3'
delay = 1
duration = 200
thu.setup(comport, delay, duration)
thu.init_local_logger(folder_name + 'test_thu.log')
print(thu.progress())
thu.start()
while thu.is_busy():
    print(thu.progress())
    print(thu.info())
    time.sleep(1)

thu.finish()

# print('stopping server:')
# try:
#     print('CAM: {0}'.format(cam.stop_server()))
# except Exception as e:
#     print(e)
