#!/usr/bin/env python
import pygame
import numpy as np
import threading
import pandas as pd
from .ZeroService import BaseZeroService
from .ZeroService.CamZeroService import CAM
import zerorpc
import time
import sys

class SCM(SoundZeroService):

    LOGGING_PORT = 1447
    SERVICE_PORT = 4247
    SERVICE_NAME = "SCM"

    def setup(self, sndsetup, camsetup):
        super().setup(*sndsetup)# call super setup()
        # instantiate and setup CAM
        print([CAM.SERVICE_PORT, CAM.SERVICE_NAME])
        self.cam = ZeroClient("{0}@{1}".format(user_name, ip_address), 'picam_client')
        print(cam.start_server(cam_server_name, folder_name, warmup=1))
        self.cam.connect("tcp://{0}:{1}".format(ip_address, cam_service_port))
        print('done')
        # max sure duration is long enough - longer than sndsetup duration
        self.cam.setup(*camsetup)

    def start(self):
        self.cam.start()
        time.sleep(5)
        super().start()

    def is_busy(self):
        return super().is_busy() and self.cam.is_busy()

    def finish(self):
        super().finish()
        time.sleep(5)
        self.cam.finish()

    def cleanup(self):
        super().cleanup()
        self.cam.cleanup()

    def info(self):
        (super().info, self.cam.info())


if __name__ == '__main__':
    if len(sys.argv) > 1:
        ser = sys.argv[1]
    else:
        ser = 'default'
    s = SCM(serializer=ser)
    s.bind("tcp://0.0.0.0:{0}".format(SCM.SERVICE_PORT))
    s.run()
