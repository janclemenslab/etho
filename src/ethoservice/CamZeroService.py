#!/usr/bin/env python
try:
    import picamera
    picamera_error = None
except Exception as e:
    picamera_error = e

from threading import Timer
import io
from .ZeroService import BaseZeroService
import time
import zmq
import os
import sys
from .utils.log_exceptions import for_all_methods, log_exceptions
import logging


@log_exceptions(logging.getLogger(__name__))
def frame_server():
    # Setup ZeroMQ PUBLISH socket for frames
    context = zmq.Context()
    zmq_socket = context.socket(zmq.PUB)
    zmq_socket.bind("tcp://0.0.0.0:5557")
    RUN = True
    try:
        while RUN:
            camera = (yield)
            if camera is None:
                RUN = False
            else:
                stream = io.BytesIO()
                camera.capture(stream, use_video_port=True, format='jpeg')
                stream.seek(0)
                zmq_socket.send(stream.read())
    except:  # GeneratorExit:
        pass  # clean up zmq_socket and context?
    print("   closing frame_server.")


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class CAM(BaseZeroService):
    """PIcamera service.

    possible modes:
    http://picamera.readthedocs.io/en/release-1.13/fov.html#sensor-modes
    shortly: if you want to record the full FOV, than 1640x1232 is the limit on width.
    Height is usually not a problem. up to 40fps possible with those settings.
    Camera can do 1280x720@90fps!
    """

    LOGGING_PORT = 1442
    SERVICE_PORT = 4242
    SERVICE_NAME = 'CAM'

    def setup(self,
              savefilename,
              duration,
              bitrate=10000000,
              resolution=(1640, 922),
              framerate=40,
              shutterspeed=10 * 1000,
              annotate_frame_num=False):
        """Initialize recording.

        Args:
            savefilename - None (preview only)
            duration in seconds
            name-value pairs not settable via zerorpc - maybe send via settings dictionary
        """
        if picamera_error is not None:
            raise picamera_error

        self.camera = picamera.PiCamera()
        self.fs = frame_server()
        self.fs.send(None)
        self.camera.resolution = resolution
        self.camera.framerate = framerate  # fps
        self.camera.shutter_speed = shutterspeed  # us
        self.camera.zoom = [0, 0.1, 1.0, 1]
        self.camera.awb_mode = 'off'
        self.camera.awb_gains = (113 / 128, 99 / 128)

        # as framenumber in frame <-display timestamp!!
        self.camera.annotate_frame_num = annotate_frame_num
        self.duration = duration
        self.bitrate = bitrate
        if savefilename is None:
            self.savefilename = '/dev/null'
            self.format = 'h264'
        else:
            self.savefilename = savefilename
            os.makedirs(os.path.dirname(savefilename), exist_ok=True)
            self.format = None
            self.log.info('   will save to {}'.format(self.savefilename))
        self._time_started = None

    def start(self):
        self.log.info('starting recording')
        if self.camera.recording:
            self.log.warning('    stop running recording')
            self.finish()
        self.camera.start_recording(self.savefilename, format=self.format, bitrate=self.bitrate)
        self.log.info('started recording')
        if self.duration > 0:
            self.log.info('duration {0} seconds'.format(self.duration))
            # will execute FINISH after N seconds
            t = Timer(self.duration, self.finish, kwargs={'stop_service': True})
            t.start()
            self.log.info('finish timer started')
        self._time_started = time.time()
        self.log.debug('started')

    def finish(self, stop_service=False):
        self.log.warning("stopping recording")
        if hasattr(self, 'camera') and self.camera.recording:
            self.camera.stop_recording()
            self.log.warning("   stopped recording")
        else:
            self.log.warning("   was not recording")
        self._flush_loggers()
        if stop_service:
            time.sleep(2)
            self.service_stop()

    def disp(self):
        if self.camera.recording:
            self.fs.send(self.camera)

    def is_busy(self):
        if hasattr(self, 'camera'):
            return self.camera.recording
        else:
            return None

    def info(self):
        if self.is_busy():
            return self.camera.frame
        else:
            return None

    def test(self):
        return True

    def cleanup(self):
        if hasattr(self, 'camera'):
            self.camera.close()
        return True


if __name__ == '__main__':
    # expose as ZeroService
    if len(sys.argv) > 1:
        ser = sys.argv[1]
    else:
        ser = 'default'
    s = CAM(serializer=ser)
    s.bind("tcp://0.0.0.0:{0}".format(CAM.SERVICE_PORT))
    s.run()
