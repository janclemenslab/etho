import time
from etho.head.ZeroClient import ZeroClient
from ethoservice.ThuZeroService import THU
from etho import config


ip_address = 'rpi8'
ssh_address = '{0}@rpi8'.format(config['GENERAL']['user'])
thu_server_name = 'python -m {0}'.format(THU.__module__)
folder_name = config['GENERAL']['folder']
thu_service_port = THU.SERVICE_PORT

thu = ZeroClient(ssh_address)
thu.start_server(thu_server_name, folder_name, warmup=1)
thu.connect("tcp://{0}:{1}".format(ip_address, thu_service_port))
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
