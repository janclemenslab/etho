# required imports
from .ZeroService import BaseZeroService  # import super class
import zerorpc  # for starting service in `main()`
import time     # for timer
import threading
import sys
from .utils.log_exceptions import for_all_methods, log_exceptions
import logging
from .utils import camera as camera
# try:
#     import PySpin
# except Exception as e:
#     print("IGNORE IF RUN ON HEAD")
#     print(e)

import numpy as np
import h5py
from ethoservice.utils.common import *

import cv2
from datetime import datetime
from .utils.ConcurrentTask import ConcurrentTask
from .callbacks import callbacks




@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class GCM(BaseZeroService):

    LOGGING_PORT = 1448   # set this to range 1420-1460
    SERVICE_PORT = 4248   # last to digits match logging port - but start with "42" instead of "14"
    SERVICE_NAME = "GCM"  # short, uppercase, 3-letter ID of the service (equals class name)

    def setup(self, savefilename, duration, params):
        self._time_started = None
        self.duration = duration
        self.savefilename = savefilename

        # set up CAMERA
        camera_type = 'spinnaker' # 'flycapture', 'xiapi'  # WHICH API
        self.cam_serialnumber = str(params['cam_serialnumber'])
        self.c = camera.make[camera_type](self.cam_serialnumber)

        # self.cam_system = PySpin.System_GetInstance()
        # self.cam_list = self.cam_system.GetCameras()
        # try:
        #     self.c = self.cam_list.GetBySerial(self.cam_serialnumber)
        #     self.c.Init()
        #     self.c.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)
        # except:
        #     print('sth went wrong - resetting cam')
        #     device_reset = PySpin.CCommandPtr(self.c.GetNodeMap().GetNode("DeviceReset"))
        #     device_reset.Execute()

        #     self.c.DeInit()
        #     del self.c
        #     self.cam_list.Clear()
        #     del self.cam_list
        #     self.cam_system.ReleaseInstance()
        #     del self.cam_system
        #     time.sleep(10)

        #     self.cam_system = PySpin.System_GetInstance()
        #     self.cam_list = self.cam_system.GetCameras()
        #     self.cam_list = self.cam_system.GetCameras()
        #     self.c = self.cam_list.GetBySerial(self.cam_serialnumber)
        #     self.c.Init()

        # # trigger overlap -> ReadOut
        # self.c.TriggerOverlap.SetValue(PySpin.TriggerOverlap_ReadOut)

        # # enable embedding of frame TIME STAMP
        # self.c.ChunkModeActive.SetValue(True)
        # self.c.ChunkSelector.SetValue(PySpin.ChunkSelector_Timestamp)
        # self.c.ChunkEnable.SetValue(True)

        # self.timestamp_offset = _compute_timestamp_offset(self.c)
        # self.c.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)

        self.c.roi = [params['frame_offx'], params['frame_offy'], params['frame_width'], params['frame_height']]

        # # set frame dims first so offsets can be non-zero
        # self.log.info(f"Frame width: {min_max_inc(self.c.Width, int(params['frame_width']))}")
        # self.log.info(f"Frame height: {min_max_inc(self.c.Height, int(params['frame_height']))}")
        # self.log.info(f"OffsetX: {min_max_inc(self.c.OffsetX, int(params['frame_offx']))}")
        # self.log.info(f"OffsetY: {min_max_inc(self.c.OffsetY, int(params['frame_offy']))}")

        # self.c.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
        # self.c.ExposureMode.SetValue(PySpin.ExposureMode_Timed)
        # self.c.ExposureTime.SetValue(float(params['shutter_speed']))
        self.c.exposure = params['shutter_speed']

        # self.c.BlackLevelSelector.SetValue(PySpin.BlackLevelSelector_All)
        # self.c.BlackLevel.SetValue(float(params['brightness']))
        self.c.brightness = params['brightness']

        # self.c.GammaEnable.SetValue(False)
        # self.c.Gamma.SetValue(float(params['gamma']))
        self.c.gamma = params['gamma']

        # self.c.GainAuto.SetValue(PySpin.GainAuto_Off)
        # self.c.Gain.SetValue(float(params['gain']))
        self.c.gain = params['gain']


        # self.c.AcquisitionFrameRateEnable.SetValue(True)
        # self.c.AcquisitionFrameRate.SetValue(float(params['frame_rate']))
        # self.frame_rate = self.c.AcquisitionResultingFrameRate.GetValue()
        # self.log.info(f'Frame rate = {self.frame_rate} fps.')
        self.c.frame_rate = params['frame_rate']
        # self.c.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)

        # get one frame to extract actual frame rate and frame size etc.
        # self.c.BeginAcquisition()
        # im = self.c.GetNextImage()
        # timestamp = im.GetTimeStamp()
        # im_converted = im.Convert(PySpin.PixelFormat_BGR8, PySpin.HQ_LINEAR)
        # image = im_converted.GetNDArray()
        # self.c.EndAcquisition()
        self.c.start()
        image, image_ts, system_ts = self.c.get()
        self.frame_width, self.frame_height = image.shape[:2]

        self.frame_interval = StatValue()
        self.frame_interval.value = 0
        self.last_frame_time = clock()

        self.nFrames = int(self.frame_rate * (self.duration + 100))

        self.callbacks = []
        common_task_kwargs = {'file_name': self.savefilename + 'avi', 'frame_rate': self.frame_rate,
                              'frame_height': self.frame_height, 'frame_width': self.frame_width}
        for cb_name, cb_params in params['callbacks'].items():
            if cb_params is not None:
                task_kwargs = {**common_task_kwargs, **cb_params}
            else:
                task_kwargs = common_task_kwargs

            self.callbacks.append(callbacks[cb_name].make_concurrent(task_kwargs=task_kwargs))

        # background jobs should be run and controlled via a thread
        # threads can be stopped by setting an event: `_thread_stopper.set()`
        self._thread_stopper = threading.Event()
        # and/or via a timer

        if self.duration > 0:
            self._thread_timer = threading.Timer(self.duration, self.finish, kwargs={'stop_service': True})

        # set up the worker thread
        self._worker_thread = threading.Thread(
            target=self._worker, args=(self._thread_stopper,))

    def start(self):
        for callback in self.callbacks:
            callback.start()
        self._time_started = time.time()

        # background jobs should be run and controlled via a thread
        self._worker_thread.start()
        self.log.info('started')
        if hasattr(self, '_thread_timer'):
             self.log.info('duration {0} seconds'.format(self.duration))
             self._thread_timer.start()
             self.log.info('finish timer started')

    def _worker(self, stop_event):
        RUN = True
        frameNumber = 0
        self.log.info('started worker')
        self.c.start()
        while RUN:

            try:
                image, image_ts, system_ts = self.c.get()

                for callback in self.callbacks:
                    callback.send((image, (system_ts, image_ts)))

                # update FPS counter
                self.frame_interval.update(system_ts - self.last_frame_time)
                self.last_frame_time = system_ts

                if frameNumber % 100 == 0:
                    sys.stdout.write('\rframe interval for frame {} is {} ms.'.format(
                                        frameNumber, np.round(self.frame_interval.value * 1000)))  # frame interval in ms

                frameNumber = frameNumber + 1
                if frameNumber == self.nFrames:
                    self.log.info('Max number of frames reached - stopping.')
                    RUN = False

            except ValueError as e:
                RUN = False
                self.c.stop()
                self.log.exception(e, exc_info=True)
            except Exception as e:
                self.log.exception(e, exc_info=True)

    def finish(self, stop_service=False):
        self.log.warning('stopping')

        # stop thread if necessary
        if hasattr(self, '_thread_stopper'):
            self._thread_stopper.set()
        if hasattr(self, '_thread_timer'):
            self._thread_timer.cancel()

        # clean up code here
        self.c.close()  # not sure this works if BeginAcquistion has not been called

        for callback in self.callbacks:
            callback.finish()

        # callbacks clean up after themselves now so probably no need for this:
        for callback in self.callbacks:
            try:
                callback.close()
            except:
                pass

        self.log.warning('   stopped ')
        if stop_service:
            time.sleep(0.5)
            self.service_stop()

    def disp(self):
        pass

    def is_busy(self):
        return True # should return True/False

    def test(self):
        return True

    def cleanup(self):
        self.finish()
        # your code here
        return True

    def info(self):
        if self.is_busy():
            pass  # your code here
        else:
            return None


if __name__ == '__main__':
    if len(sys.argv) > 1:
        ser = sys.argv[1]
    else:
        ser = 'default'
    if len(sys.argv) > 2:
        port = sys.argv[2]
    else:
        port = GCM.SERVICE_PORT

    s = GCM(serializer=ser)
    s.bind("tcp://0.0.0.0:{0}".format(port))  # broadcast on all IPs
    s.run()
