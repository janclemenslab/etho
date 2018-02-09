import time
from etho.head.ZeroClient import ZeroClient
from ethoservice.OptZeroService import OPT
from etho import config

ip_address = 'rpi8'
ssh_address = '{0}@rpi8'.format(config['GENERAL']['user'])
opt_server_name = 'python -m {0}'.format(OPT.__module__)
folder_name = config['GENERAL']['folder']
opt_service_port = OPT.SERVICE_PORT

opt = ZeroClient(ssh_address)
opt.start_server(opt_server_name, folder_name, warmup=1)
opt.connect("tcp://{0}:{1}".format(ip_address, opt_service_port))
print([OPT.SERVICE_PORT, OPT.SERVICE_NAME])

pin = 3
duration = 300
blinkinterval = 4
blinkduration = 2
opt.setup(pin, duration, blinkinterval, blinkduration)
opt.init_local_logger('test/test_opt.log')
print(opt.progress())
opt.start()
# while opt.is_busy():
#     print(opt.progress())
#     time.sleep(1)

# opt.finish()

# print('stopping server:')
# try:
#     print('CAM: {0}'.format(cam.stop_server()))
# except Exception as e:
#     print(e)
