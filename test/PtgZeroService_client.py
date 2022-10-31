import time
from utils.zeroclient import ZeroClient
from ethoservice.PTGZeroService import PTG
import subprocess

ssh_address = 'ncb@localhost'
ip_address = 'localhost'
cam_server_name = 'python -m {0}'.format(PTG.__module__)
folder_name = '~/'
cam_service_port = PTG.SERVICE_PORT

cam = ZeroClient(ssh_address)
# cam.start_server(cam_server_name, folder_name, warmup=1)
subprocess.Popen('python -m ethoservice.PTGZeroService')
cam.connect("tcp://{0}:{1}".format(ip_address, cam_service_port))
print([PTG.SERVICE_PORT, PTG.SERVICE_NAME])

cam.setup('20170129_1644', 30)
cam.init_local_logger('20170129_1644.log')
print(cam.progress())
cam.start()
# while cam.is_busy():
#     print(cam.progress())
#     time.sleep(1)

# cam.finish()

# print('stopping server:')
# try:
#     print('CAM: {0}'.format(cam.stop_server()))
# except Exception as e:
#     print(e)
