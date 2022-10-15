# required imports
from .ZeroService import BaseZeroService
import time  # for timer
import threading
import sys
from .utils.log_exceptions import for_all_methods, log_exceptions
import logging
from .utils import camera as camera

import rich
from tqdm import tqdm
from ethoservice.utils.common import *

from .callbacks import callbacks

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import Progress
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.pretty import Pretty

logger = logging.getLogger('GCM')
logging.basicConfig(level=logging.INFO)

import skimage.transform


def to_string(img: np.ndarray, dest_width: int, unicode: bool = True) -> str:
    img_width, img_height = img.shape[:2]
    scale = img_width / dest_width
    dest_height = int(img_height / scale)
    dest_height = dest_height + 1 if dest_height % 2 != 0 else dest_height

    img = skimage.transform.resize(img, (dest_width, dest_height), preserve_range=True)
    img = img.astype(float)
    img -= np.min(img)
    img /= np.max(img)+0.000001
    img *= 255
    img = img.astype(np.uint8)
    output = ""

    for y in range(0, dest_height, 2):
        for x in range(dest_width):
            if unicode:
                r1, g1, b1 = img[x, y, :]
                r2, g2, b2 = img[x, y + 1, :]
                output = output + f"[rgb({r1},{g1},{b1}) on rgb({r2},{g2},{b2})]█[/]"
            else:
                r, g, b = img[x, y]
                output = output + f"[on rgb({r},{g},{b})] [/]"

        output = output + "\n"

    return output


def dict_to_def(d):
    s = ''
    for key, val in d.items():
        s += f"[bold]{key}[/]:\n   {str(val)}\n"
    return s


def dict_to_def_aults(d, d2):
    s = ''
    for key, val in d.items():
        s += f"[bold]{key}[/]:\n   {str(val)} (target: {str(d2[key])})\n"
    return s


def dict_to_table(d, title=None, key_name='Key', value_names=None):

    table = Table(title=title)

    table.add_column(key_name, justify="right", style="cyan", no_wrap=True)
    if value_names is None:
        first_key = list(d.keys())[0]
        value_names = [f'Value {cnt}' for cnt, _ in enumerate(d[first_key])]

    for value_name in value_names:
        table.add_column(value_name, justify='left', style="magenta")

    for key, val in d.items():
        table.add_row(key, *[str(v) for v in val])
    return table

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
        params['offsetX'], params['offsetY'], params['width'], params['height']=params['frame_offx'], params['frame_offy'], params['frame_width'], params['frame_height']

        self.layout = Layout()
        self.layout.split_column(
            Layout(Panel(''), name="progress", size=8),
            Layout(Panel(''), name="info"),
        )

        self.layout["info"].split_row(
            Layout(Panel(dict_to_def(self.c.info_hardware())), name="hardware", ratio=3),
            Layout(Panel(dict_to_def_aults(iii, params)), name="image", ratio=3),
            Layout(Panel(''), name="frame", ratio=8),
        )

        # logger.info(f"{self.cam_type} (sn {self.cam_serialnumber})")
        # rich.print(self.c.info_hardware())
        # rich.print(params)
        # rich.print(self.c.info_imaging())
        self.frame_width, self.frame_height, self.frame_channels = image.shape
        # logger.info(image.shape)
        self.framerate = self.c.framerate
        # logger.info(self.framerate)
        self.nFrames = int(self.framerate * (self.duration + 100))

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
        self.pbar = tqdm(total=self.nFrames, desc='GCM', unit=' frames')
        c=Console()
        nDigits = len(str(int(self.nFrames)))
        with Live(self.layout, auto_refresh=False, screen=True, ) as live:

            while RUN:

                try:
                    image, image_ts, system_ts = self.c.get()

                    for callback_name, callback in zip(self.callback_names, self.callbacks):
                        if 'timestamps' in callback_name:
                            package = (0, (system_ts, image_ts))
                        else:
                            package = (image, (system_ts, image_ts))
                        callback.send(package)

                    if frameNumber % self.framerate == 0:
                        out = to_string(image, c.size.width, unicode=False)
                        self.layout['info']['frame'].update(Panel(out, title=f'Frame {frameNumber}'))
                        prgrs_len = c.size.width // 2 - 40
                        prgrs_cut = frameNumber//(self.nFrames//prgrs_len)
                        prgrs = ['█' if pos < prgrs_cut else '░' for pos in range(prgrs_len)]

                        progressbar = f"[{''.join(prgrs)}] frame {int(frameNumber): {nDigits}d}/{self.nFrames}"
                        self.layout['progress'].update(Panel(f"Camera: {progressbar}", title='Camera'))
                        live.refresh()

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
