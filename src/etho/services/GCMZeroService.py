from .ZeroService import BaseZeroService
import time
import threading
import sys
from .utils.log_exceptions import for_all_methods, log_exceptions
import logging
from ..services import camera
from .callbacks import callbacks


logger = logging.getLogger(__name__)


@for_all_methods(log_exceptions(logger))
class GCM(BaseZeroService):
    LOGGING_PORT = 1446  # set this to range 1420-1460
    SERVICE_PORT = 4246  # last to digits match logging port - but start with "42" instead of "14"
    SERVICE_NAME = "GCM"  # short, uppercase, 3-letter ID of the service (equals class name)

    def setup(self, savefilename, duration, params):
        self._time_started = None
        self.duration = duration
        self.savefilename = savefilename
        self.c = None

        # set up CAMERA
        self.cam_serialnumber = str(params["cam_serialnumber"])
        self.cam_type = params["cam_type"]
        assert self.cam_type in camera.make.keys()
        self.c = camera.make[self.cam_type](self.cam_serialnumber)
        try:
            self.c.init()
        except Exception as e:
            self.log.exception(
                f"Failed to init {self.cam_type} (sn {self.cam_serialnumber}). Reset and re-try.",
                exc_info=e,
            )
            self.c.reset()
            self.c.init()

        defaults = {
            "binning": 1,
            "gamma": 1,
            "gain": 0,
            "brightness": 0,
            "optimize_auto_exposure": False,
            "external_trigger": False,
            "frame_offx": 0,
            "frame_offy": 0,
        }
        params = defaults | params  # merge directory - keep existing values in params, only add non-existing from defaults

        self.c.roi = [
            params["frame_offx"],
            params["frame_offy"],
            params["frame_width"],
            params["frame_height"],
        ]
        self.c.exposure = params["shutter_speed"]
        self.c.brightness = params["brightness"]
        self.c.gamma = params["gamma"]
        self.c.gain = params["gain"]
        self.c.framerate = params["frame_rate"]

        if "optimize_auto_exposure" in params and params["optimize_auto_exposure"]:
            self.c.optimize_auto_exposure()

        # acquire test image
        self.c.disable_gpio_strobe()  # to prevent the test image producing strobes
        self.c.external_trigger = False  # disable here so test image acq works w/o ext trigger
        self.c.start()
        self.test_image, image_ts, system_ts = self.c.get()
        self.c.stop()

        self.c.external_trigger = params["external_trigger"]

        self.frame_width, self.frame_height, self.frame_channels = self.test_image.shape
        self.framerate = self.c.framerate
        self.nFrames = int(self.framerate * self.duration + 100)
        self.frameNumber = 0
        self.prev_framenumber = 0

        self.callbacks = []
        self.callback_names = []
        common_task_kwargs = {
            "file_name": self.savefilename,
            "frame_rate": self.framerate,
            "frame_height": self.frame_height,
            "frame_width": self.frame_width,
        }

        if "callbacks" in params and params["callbacks"]:
            for cb_name, cb_params in params["callbacks"].items():
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
            self._thread_timer = threading.Timer(self.duration, self.finish, kwargs={"stop_service": True})

        # set up the worker thread
        self._worker_thread = threading.Thread(target=self._worker, args=(self._thread_stopper,))

        iii = self.c.info_imaging()
        iii["exposure"] = f"{iii['exposure']:1.2f}ms"
        params["exposure"] = f"{params['shutter_speed']/1_000:1.2f}ms"
        params["framerate"] = params["frame_rate"]
        params["offsetX"], params["offsetY"], params["width"], params["height"] = (
            params["frame_offx"],
            params["frame_offy"],
            params["frame_width"],
            params["frame_height"],
        )

        hii = self.c.info_hardware()
        self.log.info(params.__str__())
        try:
            hii.update({k: v if v is not None else "defaults" for k, v in params["callbacks"].items()})
        except AttributeError:
            pass
        hii["savefilename"] = self.savefilename
        hii["duration"] = self.duration
        self.info = {"hardware": hii, "image": (iii, params)}

        self.finished = False

    def start(self):
        for callback in self.callbacks:
            callback.start()
        self._time_started = time.time()

        # background jobs should be run and controlled via a thread
        self._worker_thread.start()
        self.log.debug("started")
        if hasattr(self, "_thread_timer"):
            self.log.debug("duration {0} seconds".format(self.duration))
            self._thread_timer.start()
            self.log.debug("finish timer started")

    def _worker(self, stop_event):
        RUN = True
        self.frameNumber = 0
        self.prev_framenumber = 0
        self.log.info("started worker")
        self.c.enable_gpio_strobe()
        self.c.start()

        while RUN:
            try:
                out = self.c.get()
                if out is None:
                    raise ValueError("Image is None")
                else:
                    image, image_ts, system_ts = out

                for callback_name, callback in zip(self.callback_names, self.callbacks):
                    if "timestamps" in callback_name:
                        package = (0, (system_ts, image_ts))
                    else:
                        package = (image, (system_ts, image_ts))
                    callback.send(package)

                self.frameNumber += 1
                if self.frameNumber == self.nFrames:
                    self.log.info("Max number of frames reached - stopping.")
                    RUN = False

            except ValueError as e:
                RUN = False
                self.c.stop()
                self.log.debug(e, exc_info=True)
            except Exception as e:
                self.log.exception("Error", exc_info=e)

    def finish(self, stop_service=False):
        self.log.warning("stopping")
        try:
            self.c.disable_gpio_strobe()
        except Exception as e:
            pass  # self.log.warning(e)

        # stop thread if necessary
        if hasattr(self, "_thread_stopper"):
            self._thread_stopper.set()
        if hasattr(self, "_thread_timer"):
            self._thread_timer.cancel()

        # clean up code here
        try:
            self.c.close()  # not sure this works if BeginAcquistion has not been called
        except:
            pass

        for callback in self.callbacks:
            callback.finish()

        # callbacks clean up after themselves now so probably no need for this:
        for callback in self.callbacks:
            try:
                callback.close()
            except Exception as e:
                pass

        self.finished = True
        self.log.warning("   stopped ")
        if stop_service:
            time.sleep(0.5)
            self.service_stop()
            # self.kill_children()
            # self.kill()

    def progress(self):
        try:
            p = super().progress()
            fn = self.frameNumber
            p.update(
                {
                    "framenumber": fn,
                    "framenumber_delta": fn - self.prev_framenumber,
                    "framenumber_units": "frames",
                }
            )
            self.prev_framenumber = fn
            return p
        except:
            pass

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


if __name__ == "__main__":
    if len(sys.argv) > 1:
        ser = sys.argv[1]
    else:
        ser = "default"
    if len(sys.argv) > 2:
        port = sys.argv[2]
    else:
        port = GCM.SERVICE_PORT
    logger.info(f'Starting service GCM at {port} with serializer "{ser}".')
    s = GCM(serializer=ser)
    s.bind("tcp://0.0.0.0:{0}".format(port))  # broadcast on all IPs
    s.run()
