import time
from etho.head.ZeroClient import ZeroClient
from ethoservice.CamZeroService import CAM

ssh_address = 'ncb@rpi8'
ip_address = 'rpi8'
cam_server_name = 'python -m {0}'.format(CAM.__module__)
folder_name = '~/'
cam_service_port = CAM.SERVICE_PORT

cam = ZeroClient(ssh_address)
cam.start_server(cam_server_name, folder_name, warmup=1)
cam.connect("tcp://{0}:{1}".format(ip_address, cam_service_port))
print([CAM.SERVICE_PORT, CAM.SERVICE_NAME])

cam.setup('test.h264', 10)
cam.init_local_logger('test.log')
print(cam.progress())
cam.start()
while cam.is_busy():
    print(cam.progress())
    time.sleep(1)

# cam.finish()

# print('stopping server:')
# try:
#     print('CAM: {0}'.format(cam.stop_server()))
# except Exception as e:
#     print(e)
