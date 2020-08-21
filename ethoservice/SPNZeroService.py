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
from .callbacks import callbacks


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

        self.log.info(f"Frame width: {min_max_inc(self.c.Width, int(params['frame_width']))}")
        self.log.info(f"Frame height: {min_max_inc(self.c.Height, int(params['frame_height']))}")
        self.log.info(f"OffsetX: {min_max_inc(self.c.OffsetX, int(params['frame_offx']))}")
        self.log.info(f"OffsetY: {min_max_inc(self.c.OffsetY, int(params['frame_offy']))}")

        # first set frame dims so offsets can be non-zero
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
       
        if self.savefilename is None or ('display' in params and params['display']):
            # make comms a shared array?
            self.callbacks.append(ConcurrentTask(task=callbacks['disp_fast'], comms='pipe',
                                                 taskinitargs=(self.frame_height, self.frame_width)))

        if self.savefilename is not None:
            os.makedirs(os.path.dirname(self.savefilename), exist_ok=True)
            self.nFrames = int(self.frame_rate * (self.duration + 100))
            self.timestamps = np.zeros((self.nFrames, 2))
            # save camera info
            print("saving camera info in the timestamps file")
            # camera_info = self.c.get_camera_info()
            with h5py.File(self.savefilename + '_timeStamps.h5', "w") as h5f:
                dset = h5f.create_dataset("camera_info", (1,), compression="gzip")
                # for k, v in camera_info.items():
                #     dset.attrs[k] = v
            
            if 'save_fast' in params and params['save_fast']:
                self.log.info(f"Using GPU-based video encoder.")
                save_callback = callbacks['save_fast']
                taskinitargs = (self.savefilename, self.frame_rate, self.frame_height, self.frame_width, params['save_fast_bin_path'])
            else:
                save_callback = callbacks['save']
                taskinitargs  =(self.savefilename, self.frame_rate, self.frame_height, self.frame_width)
            self.callbacks.append(ConcurrentTask(task=save_callback, comms='queue', taskinitargs=taskinitargs))

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
        while RUN: #and not stop_event.wait(0.0001):
            try:
                im = self.c.GetNextImage(PySpin.EVENT_TIMEOUT_INFINITE)
                t = time.time()
            except Exception:
                RUN = False

            if im.IsIncomplete():
                self.log.warning(f"Image incomplete with image status {im.GetImageStatus()}")
            else:
                try:
                    im_converted = im.Convert(PySpin.PixelFormat_BGR8, PySpin.HQ_LINEAR)
                    BGR = im_converted.GetNDArray()

                    self.frame_interval.update(t - self.last_frame_time)
                    self.last_frame_time = t

                    # display every 50th frame
                    if frameNumber % 50 == 0:
                        sys.stdout.write('\rframe interval for frame {} is {} ms.'.format(
                            frameNumber, np.round(self.frame_interval.value * 1000)))  # frame interval in ms   
                        sys.stdout.flush()

                    if self.savefilename is not None:
                        timestamp = im.GetTimeStamp()
                        timestamp = timestamp / 1e9 + self.timestamp_offset
                        self.timestamps[frameNumber, :] = (t, timestamp)

                    for callback in self.callbacks:
                        callback.send(BGR)

                    # im.Release()  # not sure we need this to free the buffer
                    frameNumber = frameNumber + 1
                    if frameNumber == self.nFrames:
                        self.log.info('Max number of frames reached - stopping.')
                        RUN = False
                    continue
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
        try: 
            self.c.EndAcquisition()  # not sure this works if BeginAcquistion has not been called
        except:
            pass

        for callback in self.callbacks:
            callback.finish()

        for callback in self.callbacks:
            callback.close()

        if self.savefilename is not None:
            # FIXME: truncate self.timestamps to the actual number of recorded frames -
            # save this during recording so we don't loose all timestamps in case something goes wrong
            print('saving time stamps ' + self.savefilename + '_timeStamps.h5')
            with h5py.File(self.savefilename + '_timeStamps.h5', 'w') as h5f:
                h5f.create_dataset("timeStamps", data=self.timestamps, compression="gzip")

        self.c.DeInit()
        del self.c
        self.cam_list.Clear()
        self.cam_system.ReleaseInstance()

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