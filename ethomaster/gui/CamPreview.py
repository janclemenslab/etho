'''
Receives a live video stream from the pi using ZeroMQ
'''
import io
from PIL import Image
import zmq

from ethomaster.head.ZeroClient import ZeroClient
from ethoservice.CamZeroService import CAM


def camPreview(host, user='ncb'):

    cam_server_name = 'python -m {0}'.format(CAM.__module__)
    folder_name = '~/'
    cam_service_port = CAM.SERVICE_PORT

    cam = ZeroClient('{0}@{1}'.format(user, host))
    cam.start_server(cam_server_name, folder_name, warmup=1, remote=True)
    cam.connect("tcp://{0}:{1}".format(host, cam_service_port))
    print([CAM.SERVICE_PORT, CAM.SERVICE_NAME])

    # Setup SUBSCRIBE socket

    context = zmq.Context()
    zmq_socket = context.socket(zmq.SUB)
    zmq_socket.setsockopt(zmq.SUBSCRIBE, b'')
    zmq_socket.setsockopt(zmq.CONFLATE, 1)
    zmq_socket.connect("tcp://{}:5557".format(host))

    cam_was_running = cam.is_busy()
    if not cam_was_running:
        cam.setup(None, 0)
        cam.start()

    try:
        while True:
            print(cam.info())
            cam.disp()  # request new frame

            image_stream = io.BytesIO()
            payload = zmq_socket.recv()
            image_stream.write(payload)

            # Rewind the stream, open it as an image with PIL and do some processing on it
            image_stream.seek(0)
            yield Image.open(image_stream)

    finally:
        if not cam_was_running:
            print('stopping server:')
            cam.finish()
            try:
                print('CAM: {0}'.format(cam.stop_server()))
            except Exception as e:
                print(e)


if __name__ == '__main__':
    import cv2
    import numpy as np
    import time

    host = 'rpi3'
    cv2.startWindowThread()
    cv2.namedWindow(host, cv2.WINDOW_NORMAL)

    preview = camPreview(host)

    for _ in range(10):
        cv2.imshow(host, np.array(next(preview)))
        cv2.waitKey(1)
        time.sleep(2)

    preview.close()
