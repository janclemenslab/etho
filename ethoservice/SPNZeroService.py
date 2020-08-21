# required imports
from .ZeroService import BaseZeroService  # import super class
import zerorpc  # for starting service in `main()`
import time     # for timer
import threading
import sys
from .utils.log_exceptions import for_all_methods, log_exceptions
import logging
try:
    import PySpin
except Exception as e:
    print("IGNORE IF RUN ON HEAD")
    print(e)

import numpy as np
import h5py
from ethoservice.utils.common import *

import cv2
from datetime import datetime
from .utils.ConcurrentTask import ConcurrentTask
from .callbacks_oop import callbacks


# @log_exceptions(logging.getLogger(__name__))
def min_max_inc(prop, value=None, set_value=True):
    min_val, max_val, inc = prop.GetMin(), prop.GetMax(), prop.GetInc()

    prop_type = type(prop.GetValue())
    if value is not None:
        value = np.clip(value, min_val, max_val)
        value = np.round(value / inc) * inc
        if set_value:
            value = prop_type(value)
            prop.SetValue(value)
            value = prop.GetValue()
    return value


def _compute_timestamp_offset(cam, timestamp_offset_iterations=10):
    """Gets offset between system time and timestamps."""
    # This method is required because the timestamp stored in the camera is relative to when it was powered on, so an
    # offset needs to be applied to get it into epoch time; from tests I’ve done, this appears to be accurate to ~1e-3
    # seconds.

    timestamp_offsets = []
    for i in range(timestamp_offset_iterations):
        # Latch timestamp. This basically “freezes” the current camera timer into a variable that can be read with
        # TimestampLatchValue()
        cam.TimestampLatch.Execute()
        system_time = time.time()
        # Compute timestamp offset in seconds; note that timestamp latch value is in nanoseconds
        timestamp_offset = system_time - cam.TimestampLatchValue.GetValue() / 1e9
        # print(system_time, cam.TimestampLatchValue.GetValue() / 1e9)

        # Append
        timestamp_offsets.append(timestamp_offset)
    # Return the median value
    return np.median(timestamp_offsets)


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class SPN(BaseZeroService):

    LOGGING_PORT = 1448   # set this to range 1420-1460
    SERVICE_PORT = 4248   # last to digits match logging port - but start with "42" instead of "14"
    SERVICE_NAME = "SPN"  # short, uppercase, 3-letter ID of the service (equals class name)

    def setup(self, savefilename, duration, params):
        self._time_started = None
        self.duration = duration
        self.savefilename = savefilename

        # set up CAMERA - these should be defined in a PARAMS dict
        self.cam_serialnumber = str(params['cam_serialnumber'])
        # set up CAMERA
        self.cam_system = PySpin.System_GetInstance()
        self.cam_list = self.cam_system.GetCameras()
        try:
            self.c = self.cam_list.GetBySerial(self.cam_serialnumber)
            self.c.Init()
            self.c.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)
        except:
            print('sth went wrong - resetting cam')
            device_reset = PySpin.CCommandPtr(self.c.GetNodeMap().GetNode("DeviceReset"))
            device_reset.Execute()

            self.c.DeInit()
            del self.c
            self.cam_list.Clear()
            del self.cam_list
            self.cam_system.ReleaseInstance()
            del self.cam_system
            time.sleep(10)

            self.cam_system = PySpin.System_GetInstance()
            self.cam_list = self.cam_system.GetCameras()
            self.cam_list = self.cam_system.GetCameras()
            self.c = self.cam_list.GetBySerial(self.cam_serialnumber)
            self.c.Init()
        
        # trigger overlap -> ReadOut
        self.c.TriggerOverlap.SetValue(PySpin.TriggerOverlap_ReadOut)

        # enable embedding of frame TIME STAMP
        self.c.ChunkModeActive.SetValue(True)
        self.c.ChunkSelector.SetValue(PySpin.ChunkSelector_Timestamp)
        self.c.ChunkEnable.SetValue(True)

        self.timestamp_offset = _compute_timestamp_offset(self.c)
        self.c.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)

        # set frame dims first so offsets can be non-zero
        self.log.info(f"Frame width: {min_max_inc(self.c.Width, int(params['frame_width']))}")
        self.log.info(f"Frame height: {min_max_inc(self.c.Height, int(params['frame_height']))}")
        self.log.info(f"OffsetX: {min_max_inc(self.c.OffsetX, int(params['frame_offx']))}")
        self.log.info(f"OffsetY: {min_max_inc(self.c.OffsetY, int(params['frame_offy']))}")

        self.c.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
        self.c.ExposureMode.SetValue(PySpin.ExposureMode_Timed)
        self.c.ExposureTime.SetValue(float(params['shutter_speed']))

        self.c.BlackLevelSelector.SetValue(PySpin.BlackLevelSelector_All)
        self.c.BlackLevel.SetValue(float(params['brightness']))

        self.c.GammaEnable.SetValue(False)
        # self.c.Gamma.SetValue(float(params['gamma']))

        self.c.GainAuto.SetValue(PySpin.GainAuto_Off)
        self.c.Gain.SetValue(float(params['gain']))


        self.c.AcquisitionFrameRateEnable.SetValue(True)
        self.c.AcquisitionFrameRate.SetValue(float(params['frame_rate']))
        self.frame_rate = self.c.AcquisitionResultingFrameRate.GetValue()
        self.log.info(f'Frame rate = {self.frame_rate} fps.')

        self.c.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)

        # get one frame to extract actual frame rate and frame size etc.
        self.c.BeginAcquisition()
        im = self.c.GetNextImage()
        timestamp = im.GetTimeStamp()
        im_converted = im.Convert(PySpin.PixelFormat_BGR8, PySpin.HQ_LINEAR)
        image = im_converted.GetNDArray()
        self.c.EndAcquisition()
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

        self.c.BeginAcquisition()
        while RUN:
            try:
                im = self.c.GetNextImage(PySpin.EVENT_TIMEOUT_INFINITE)
                t = time.time()
            except Exception:
                RUN = False
                continue

            if im.IsIncomplete():
                self.log.warning(f"Image incomplete with image status {im.GetImageStatus()}")
            else:
                try:
                    im_converted = im.Convert(PySpin.PixelFormat_BGR8, PySpin.HQ_LINEAR)
                    BGR = im_converted.GetNDArray()

                    self.frame_interval.update(t - self.last_frame_time)
                    self.last_frame_time = t

                    timestamp = im.GetTimeStamp()
                    timestamp = timestamp / 1e9 + self.timestamp_offset

                    for callback in self.callbacks:
                        callback.send((BGR, (t, timestamp)))

                    # im.Release()  # not sure we need this to free the buffer
                    frameNumber = frameNumber + 1
                    if frameNumber == self.nFrames:
                        self.log.info('Max number of frames reached - stopping.')
                        RUN = False

                    # display every 50th frame
                    if frameNumber % 100 == 0:
                        sys.stdout.write('\rframe interval for frame {} is {} ms.'.format(
                                         frameNumber, np.round(self.frame_interval.value * 1000)))  # frame interval in ms

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
        self.c.EndAcquisition()  # not sure this works if BeginAcquistion has not been called


        for callback in self.callbacks:
            callback.finish()

        for callback in self.callbacks:
            callback.close()

        # if self.savefilename is not None:
        #     # FIXME: truncate self.timestamps to the actual number of recorded frames -
        #     # save this during recording so we don't loose all timestamps in case something goes wrong
        #     print('saving time stamps ' + self.savefilename + '_timeStamps.h5')
        #     with h5py.File(self.savefilename + '_timeStamps.h5', 'w') as h5f:
        #         h5f.create_dataset("timeStamps", data=self.timestamps, compression="gzip")

        self.c.DeInit()
        del self.c
        self.cam_list.Clear()
        # self.cam_system.ReleaseInstance()

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
        port = SPN.SERVICE_PORT

    s = SPN(serializer=ser)
    s.bind("tcp://0.0.0.0:{0}".format(port))  # broadcast on all IPs
    s.run()
