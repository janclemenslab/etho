import time
from ethomaster.head.ZeroClient import ZeroClient
from ethoservice.ThuZeroService import THU
from ethomaster import config


ser = 'pickle'
ip_address = 'rpi5'
ssh_address = '{0}@rpi5'.format(config['GENERAL']['user'])
thu_server_name = 'python -m {0} {1}'.format(THU.__module__, ser)
folder_name = config['GENERAL']['folder']

thu = ZeroClient(ssh_address, serializer=ser)
thu.start_server(thu_server_name, folder_name, warmup=1)
thu.connect("tcp://{0}:{1}".format(ip_address, THU.SERVICE_PORT))
print([THU.SERVICE_PORT, THU.SERVICE_NAME])


pin = 4
delay = 20
duration = 200
thu.setup(pin, delay, duration)
thu.init_local_logger('testest/test_thu.log')
print(thu.progress())
thu.start()
while thu.is_busy():
    print(thu.progress())
    time.sleep(1)

thu.finish()

# print('stopping server:')
# try:
#     print('CAM: {0}'.format(cam.stop_server()))
# except Exception as e:
#     print(e)
