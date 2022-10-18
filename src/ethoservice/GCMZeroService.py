from .ZeroService import BaseZeroService
import time
import threading
import sys
from .utils.log_exceptions import for_all_methods, log_exceptions
import logging
from .utils import camera as camera
from .callbacks import callbacks

from .utils.tui import dict_to_def, dict_to_def_aults, CameraProgress
import rich
from rich.console import Console
from rich.panel import Panel


logger = logging.getLogger('GCM')
logging.basicConfig(level=logging.INFO)


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class GCM(BaseZeroService):

    LOGGING_PORT = 1448  # set this to range 1420-1460
    SERVICE_PORT = 4248  # last to digits match logging port - but start with "42" instead of "14"
    SERVICE_NAME = "GCM"  # short, uppercase, 3-letter ID of the service (equals class name)

    def setup(self, savefilename, duration, params):
        self._time_started = None
        self.duration = duration
        self.savefilename = savefilename

        # set up CAMERA
        self.cam_serialnumber = str(params['cam_serialnumber'])
        self.cam_type = params['cam_type']
        assert self.cam_type in camera.make.keys()
        self.c = camera.make[self.cam_type](self.cam_serialnumber)
        try:
            self.c.init()
        except Exception as e:
            logger.exception("Failed to init {self.cam_type} (sn {self.cam_serialnumber}). Reset and re-try.", exc_info=e)
            self.c.reset()
            self.c.init()

        self.c.roi = [params['frame_offx'], params['frame_offy'], params['frame_width'], params['frame_height']]
        self.c.exposure = params['shutter_speed']
        self.c.brightness = params['brightness']
        self.c.gamma = params['gamma']
        self.c.gain = params['gain']
        self.c.framerate = params['frame_rate']
        self.c.start()
        image, image_ts, system_ts = self.c.get()
        self.c.stop()

        iii = self.c.info_imaging()
        iii['exposure'] = f"{iii['exposure']:1.2f}ms"
        params['exposure'] = f"{params['shutter_speed']/1_000:1.2f}ms"
        params['framerate'] = params['frame_rate']
        params['offsetX'], params['offsetY'], params['width'], params['height'] = params['frame_offx'], params[
            'frame_offy'], params['frame_width'], params['frame_height']

        hii = self.c.info_hardware()
        hii.update({k: v if v is not None else 'defaults' for k, v, in params['callbacks'].items()})
        hii['savefilename'] = self.savefilename
        hii['duration'] = self.duration

        rich.print(Panel(dict_to_def(hii), title='Hardware'))
        rich.print(Panel(dict_to_def_aults(iii, params), title='Image settings'))

        self.frame_width, self.frame_height, self.frame_channels = image.shape
        self.framerate = self.c.framerate
        self.nFrames = int(self.framerate * (self.duration + 100))
        self.nFramesTarget = int(self.framerate * self.duration)
        self.pbar = CameraProgress(self.nFramesTarget)

        self.callbacks = []
        self.callback_names = []
        common_task_kwargs = {
            'file_name': self.savefilename,
            'frame_rate': self.framerate,
            'frame_height': self.frame_height,
            'frame_width': self.frame_width
        }
        for cb_name, cb_params in params['callbacks'].items():
            if cb_params is not None:
                task_kwargs = {**common_task_kwargs, **cb_params}
            else:
                task_kwargs = common_task_kwargs

            self.callbacks.append(callbacks[cb_name].make_concurrent(task_kwargs=task_kwargs))
            self.callback_names.append(cb_name)

        # background jobs should be run and controlled via a thread
        # threads can be stopped by setting an event: `_thread_stopper.set()`
        self._thread_stopper = threading.Event()
        # and/or via a timer

        if self.duration > 0:
            self._thread_timer = threading.Timer(self.duration, self.finish, kwargs={'stop_service': True})

        # set up the worker thread
        self._worker_thread = threading.Thread(target=self._worker, args=(self._thread_stopper,))

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

                out = self.c.get()
                if out is None:
                    raise ValueError('Image is None')
                else:
                    image, image_ts, system_ts = out

                for callback_name, callback in zip(self.callback_names, self.callbacks):
                    if 'timestamps' in callback_name:
                        package = (0, (system_ts, image_ts))
                    else:
                        package = (image, (system_ts, image_ts))
                    callback.send(package)

                if frameNumber % self.framerate == 0:
                    self.pbar.update(number_of_frames=frameNumber)

                frameNumber = frameNumber + 1
                if frameNumber == self.nFrames:
                    self.log.info('Max number of frames reached - stopping.')
                    RUN = False

            except ValueError as e:
                RUN = False
                self.c.stop()
                self.log.debug(e, exc_info=True)
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
        return True  # should return True/False

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
