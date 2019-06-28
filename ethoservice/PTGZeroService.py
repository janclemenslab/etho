#!/usr/bin/env python
# required imports
from .ZeroService import BaseZeroService  # import super class
import zerorpc  # for starting service in `main()`
import time     # for timer
import threading
import sys
try:
    import flycapture2 as fc2
except Exception as e:
    print("IGNORE IF RUN ON HEAD")
    print(e)

import numpy as np
import h5py
from ethoservice.utils.common import *

from multiprocessing import Process, Queue, Pipe
import cv2
# from common import clock, StatValue
from datetime import datetime
import sys
# import zmq
# from zmq.devices.basedevice import ProcessDevice
# import argparse



def disp(displayQueue, frame_width, frame_height, poll_timeout=0.01):
    cv2.namedWindow('display')
    cv2.resizeWindow('display', frame_width, frame_height)
    RUN = True
    while RUN:
        if displayQueue.poll(poll_timeout):
            image = displayQueue.recv()  # TODO: should be none blocking (block=False) just in case, need to catch empyt queue exception
            if image is None:
                print('stopping display thread')
                RUN = False
                break
            cv2.imshow('display', image)
            cv2.waitKey(1)
    print("closing display")
    cv2.destroyWindow('display')


def disp_fast(displayQueue, frame_width, frame_height, poll_timeout=0.01):
    from pyqtgraph.Qt import QtGui
    import pyqtgraph as pg
    from pyqtgraph.widgets.RawImageWidget import RawImageWidget
    pg.setConfigOption('background', 'w')
    pg.setConfigOption('leftButtonPan', False)

    # set up window and subplots
    app = QtGui.QApplication([])
    win = RawImageWidget(scaled=True)
    win.resize(frame_width, frame_height)
    win.show()
    app.processEvents()
    RUN = True
    while RUN:
        if displayQueue.poll(poll_timeout):
            image = displayQueue.recv()  # TODO: should be none blocking (block=False) just in case, need to catch empyt queue exception
            if image is None:
                print('stopping display thread')
                RUN = False
                break
            win.setImage(image)
            app.processEvents()
    print("closing display")


def save(writeQueue, file_name, frame_rate, frame_width, frame_height):
    print("setting up video writer")
    ovw = cv2.VideoWriter()
    print("   saving to " + file_name + '.h264')
    ovw.open(file_name + '.avi', cv2.VideoWriter_fourcc(*'x264'),
             frame_rate, (frame_width, frame_height), True)
    # ovw.open(file_name + '.h264', cv2.CAP_INTEL_MFX, cv2.VideoWriter_fourcc(*'H264'),
             # frame_rate, (frame_width, frame_height), True)
    RUN = True
    while RUN:
        # if writeQueue.poll(0.01):
        image = writeQueue.get()  # get new frame
        if image is None:
            print('stopping WRITE thread')
            RUN = False
            break
        ovw.write(image)
    print("closing video writer")
    ovw.release()
    ovw = None


class PTG(BaseZeroService):

    LOGGING_PORT = 1448   # set this to range 1420-1460
    SERVICE_PORT = 4248   # last to digits match logging port - but start with "42" instead of "14"
    SERVICE_NAME = "PTG"  # short, uppercase, 3-letter ID of the service (equals class name)

    def setup(self, savefilename, duration, params):
        self._time_started = None
        self.duration = duration
        self.savefilename = savefilename

        # set up CAMERA - these should be defined in a PARAMS dict
        self.cam_id = int(params['cam_id'])

        # pre-allocate image data structures
        self.im = fc2.Image()  # this will hold the original acquired image
        self.imRGB = fc2.Image()  # this will hold the image after conversion to RGB

        print("setting up camera " + str(self.cam_id))
        self.c = fc2.Context()
        self.c.connect(*self.c.get_camera_from_index(self.cam_id))

        self.c.set_format7_configuration(fc2.MODE_0, int(params['frame_offx']), int(params['frame_offy']), int(params['frame_width']), int(params['frame_height']), fc2.PIXEL_FORMAT_BGR)
        print(self.c.get_format7_configuration())

        self.c.set_property_abs_value(fc2.FRAME_RATE, float(params['frame_rate']))
        print(self.c.get_property(fc2.FRAME_RATE))

        self.c.set_trigger_mode(0, True, 0, 0, 14)  # free-running mode
        self.c.set_register(0x12f8, 1)  # set time-stamp register so that time stamps are embedded in frames (SOURCE?)

        self.c.set_property_abs_value(fc2.SHUTTER, float(params['shutter_speed']))
        self.c.set_property_abs_value(fc2.BRIGHTNESS, float(params['brightness']))
        self.c.set_property_abs_value(fc2.AUTO_EXPOSURE, float(params['exposure']))
        # self.c.set_property_abs_value(fc2.SHARPNESS, sharpness)
        self.c.set_property_abs_value(fc2.GAMMA, float(params['gamma']))
        self.c.set_property_abs_value(fc2.GAIN, float(params['gain']))

        # get one frame to extract actual frame rate and frame size etc.
        self.c.start_capture()
        self.c.retrieve_buffer(self.im)  # get buffer - this blocks until an image is acquired
        self.c.stop_capture()

        self.frame_rate = self.c.get_property(fc2.FRAME_RATE)['abs_value']
        print(self.frame_rate)
        (self.frame_width, self.frame_height) = np.array(self.im).shape[0:2]
        print((self.frame_width, self.frame_height))

        self.frame_interval = StatValue()
        self.frame_interval.value = 0
        self.last_frame_time = clock()

        self.nFrames = int(self.frame_rate * (self.duration + 100))
        if self.savefilename is None:  # display only - set up DISPLAY
            self.displayQueue, displayOut = Pipe()
            self.pDisplay = Process(target=disp_fast, args=(displayOut, self.frame_height, self.frame_width))
        else:  # save only - set up SAVE
            os.makedirs(os.path.dirname(self.savefilename), exist_ok=True)
            self.nFrames = int(self.frame_rate * (self.duration + 100))
            self.timestamps = np.zeros((self.nFrames, 6))
            # save camera info
            print("saving camera info in the timestamps file")
            camera_info = self.c.get_camera_info()
            h5f = h5py.File(self.savefilename + '_timeStamps.h5', "w")
            dset = h5f.create_dataset("camera_info", (1,), compression="gzip")
            for k, v in camera_info.items():
                dset.attrs[k] = v
            h5f.close()
            self.writeQueue = Queue()  # TODO: this should be a Pipe since we always only want to display the last frame
            self.pWrite = Process(target=save,
                                  args=(self.writeQueue, self.savefilename, self.frame_rate, self.frame_height, self.frame_width))

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
        if self.savefilename is None:
            self.pDisplay.start()
        else:
            self.pWrite.start()
            # self.pDisplay.start()

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
        print('started worker')
        self.c.start_capture()
        while RUN: #and not stop_event.wait(0.0001):
            try:
                self.c.retrieve_buffer(self.im)  # get buffer - this blocks until an image is acquired
            except Exception as e:
                RUN = False
            t = time.time()
            self.frame_interval.update(t - self.last_frame_time)
            self.last_frame_time = t

            # necessary for BW images?
            # im.convertImage(fc2.PIXEL_FORMAT_RGB, imRGB)  # convert image to RGB from YUV422
            # im.convert(fc2.PIXEL_FORMAT_RGB, im)  # convert image to RGB from YUV422
            # RGB = np.reshape(np.array(im), (frame_height, frame_width, 3))  # why the reshape?
            # RGB = RGB[roi[1]:roi[3], roi[0]:roi[2], :]            # crop
            # BGR = cv2.cvtColor(RGB, cv2.COLOR_RGB2BGR)  # opencv wants BGR images for display and saving
            BGR = cv2.cvtColor(np.array(self.im), cv2.COLOR_GRAY2RGB)

            # display every 50th frame
            if frameNumber % 50 == 0:
                # self.displayQueue.send(BGR)
                sys.stdout.write('\rframe interval for frame {} is {} ms.'.format(
                    frameNumber, np.round(self.frame_interval.value * 1000)))  # frame interval in ms

            if self.savefilename is not None:
                ts = self.im.timestamp()  # retrieve time stamp embedded in the frame
                self.timestamps[frameNumber, :] = (t, ts['seconds'], ts['microSeconds'], ts[
                                        'cycleCount'], ts['cycleOffset'], ts['cycleSeconds'])
                self.writeQueue.put(BGR)
            else:
                self.displayQueue.send(BGR)
            frameNumber = frameNumber + 1
            if frameNumber == self.nFrames:
                print('max number of frames reached - stopping')
                RUN = False
            continue

    def finish(self, stop_service=False):
        self.log.warning('stopping')

        # stop thread if necessary
        if hasattr(self, '_thread_stopper'):
            self._thread_stopper.set()
        if hasattr(self, '_thread_timer'):
            self._thread_timer.cancel()

        # clean up code here
        self.c.stop_capture()

        if self.savefilename is None:
            print("closing display queue")
            self.pDisplay.terminate()
            self.displayQueue.send(None)
        else:
            print("closing video writer")
            self.writeQueue.put(None)
            # FIXME: truncate self.timestamps to the actual number of recorded frames -
            # save this during recording so we don't loose all timestamps in case something goes wrong
            print('saving time stamps ' + self.savefilename + '_timeStamps.h5')
            h5f = h5py.File(self.savefilename + '_timeStamps.h5')
            dset = h5f.create_dataset("timeStamps", data=self.timestamps, compression="gzip")
            h5f.close()

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
    s = PTG(serializer=ser)
    s.bind("tcp://0.0.0.0:{0}".format(PTG.SERVICE_PORT))  # broadcast on all IPs
    s.run()
