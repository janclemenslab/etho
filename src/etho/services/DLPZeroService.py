#!/usr/bin/env python
from .ZeroService import BaseZeroService  # import super class
import time  # for timer
import threading
from .utils.log_exceptions import for_all_methods, log_exceptions
from .dlp import dlp_runners
import logging
import defopt
from typing import Optional

try:
    import pycrafter4500
    from pybmt.callback.threshold_callback import ThresholdCallback
    from pybmt.callback.broadcast_callback import BroadcastCallback
    from pybmt.fictrac.service import FicTracDriver
    from pybmt.fictrac.state import FicTracState

    dlp_import_error = None
except ImportError as dlp_import_error:
    pass


# decorate all methods in the class so that exceptions are properly logged
@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class DLP(BaseZeroService):

    LOGGING_PORT = 1453  # set this to range 1420-1460
    SERVICE_PORT = 4253  # last two digits match logging port - but start with "42" instead of "14"
    SERVICE_NAME = "DLP"  # short, uppercase, 3-letter ID of the service (must equal class name)

    def setup(self, duration, logfilename, params=None):
        if dlp_import_error is not None:
            raise dlp_import_error

        self._time_started = None
        self.duration = float(duration)
        fps = 180
        nb_frames = int(self.duration * fps)
        self.tracDrv = FicTracDriver.as_client(remote_endpoint_url="localhost:5556")
        if self.tracDrv.fictrac_process is None:  # ensure fictrac is running
            self.tracDrv = None

        # 180 hz, 7 bit depth, white
        try:
            pycrafter4500.pattern_mode(
                num_pats=3,
                fps=180,
                bit_depth=7,
                led_color=0b111,  # BGR flags
            )
        except AttributeError:
            raise ValueError("Failed setting DLP pattern mode. Maybe DLP is off.")

        # background jobs should be run and controlled via a thread

        # signals that the works is initialized and ready to receive the start_run signal
        self._thread_is_ready = threading.Event()
        # start running the worker after init
        self._thread_start_run = threading.Event()
        # threads can be stopped by setting an event: `_thread_stopper.set()`
        self._thread_stopper = threading.Event()

        # via a timer
        if self.duration > 0:
            self._thread_timer = threading.Timer(self.duration, self.finish, kwargs={"stop_service": True})
        #
        self._worker_thread = threading.Thread(
            target=self._worker,
            args=(
                self._thread_stopper,
                self._thread_start_run,
                self._thread_is_ready,
                logfilename,
                nb_frames,
                self.log,
                self.tracDrv,
                params,
            ),
        )

        # start thread here so everything is initialized before
        # we start for more deterministic delays
        self.log.info("Initialzing PsychoPy stuff.")

        # start the thread - this will halt after initialization
        self._worker_thread.start()

        # block until thread is initialized
        self._thread_is_ready.wait()

    def start(self):
        self._time_started = time.time()
        # background jobs should be run and controlled via a thread
        self._thread_start_run.set()  # this will start playing the DLP stimulis
        self.log.info("started")
        if hasattr(self, "_thread_timer"):
            self.log.info("duration {0} seconds".format(self.duration))
            self._thread_timer.start()
            self.log.info("finish timer started")

    def _worker(self, stop_event, start_run_event, is_ready_event, savefilename, nb_frames, logger, tracDrv, params):
        # need to import psychopy here since psychopy only works in the thread where it's imported
        from psychopy.visual.windowframepack import ProjectorFramePacker
        import psychopy.visual, psychopy.event, psychopy.core, psychopy.visual.windowwarp
        from tqdm import tqdm
        from .callbacks import callbacks

        # # INIT WINDOW
        screen_id = 1

        # main window
        win = psychopy.visual.Window(
            monitor="projector", screen=screen_id, units="norm", fullscr=False, useFBO=True, size=(912, 1140), allowGUI=False
        )
        framePacker = ProjectorFramePacker(win)

        # INIT WARPER (skip for prototyping)
        if params["use_warping"]:
            logger.info(f"Loading warp data from {params['warpfile']}")
            # create a warper and change projection using warpfile
            warper = psychopy.visual.windowwarp.Warper(win, warp=None, warpfile=None)
            warper.changeProjection(
                warp="warpfile", warpfile=params["warpfile"], eyepoint=[0.5, 0.5], flipHorizontal=False, flipVertical=False
            )
            logger.info("Warp file loaded.")

        # INIT RUNNERS
        logger.info("Initializing runners:")
        runners = {}
        for runner_name, runner_args in params["runners"].items():
            if "object" in runner_args:  # get class handle from object name
                runner_args["object"] = psychopy.visual.__dict__[runner_args["object"]]
            logger.info(f"   {runner_name}: {runner_args}")
            runners[runner_name] = dlp_runners.runners[runner_name](win, **runner_args)

        # INIT CALLBACKS
        tasks = []
        attrs = {}
        common_task_kwargs = {"file_name": savefilename, "attrs": attrs}
        for cb_name, cb_params in params["callbacks"].items():
            if cb_params is not None:
                task_kwargs = {**common_task_kwargs, **cb_params}
            else:
                task_kwargs = common_task_kwargs
            tasks.append(callbacks[cb_name].make_concurrent(task_kwargs=task_kwargs))

        for task in tasks:
            task.start()

        logger.info("Finished initializing worker.")
        is_ready_event.set()
        logger.info("Waiting for `start_run` event.")
        self._thread_start_run.wait()

        # re-activate windows
        win.winHandle.activate()  # re-activate window
        win.flip()  # redraw the newly activated window

        # RUN THE RUNNERS
        logger.info("Running the runners")
        ball_info = None
        log_msg = dict()
        for frame_number in tqdm(range(nb_frames), total=nb_frames, mininterval=1):
            if stop_event.is_set():
                logger.info("received stop event")
                break

            if tracDrv is not None:  # get ball info
                ball_info = tracDrv._read_message()

            for runner_name, runner in runners.items():
                log_data = runner.update(frame_number, ball_info)
                log_msg[runner_name] = log_data
            win.flip()

            systemtime = time.time()
            for task in tasks:
                task.send((log_msg, systemtime))

        # CLEAN UP RUNNERS
        for runner in runners.values():
            runner.destroy()

        win.close()
        # win2.close()
        for task in tasks:
            try:
                task.close()
            except Exception as e:
                pass  # print(e)
        psychopy.core.quit()

    def finish(self, stop_service=False):
        self.log.warning("stopping")
        # stop thread if necessary
        if hasattr(self, "_thread_stopper"):
            self._thread_stopper.set()
        if hasattr(self, "_thread_timer"):
            self._thread_timer.cancel()
        # clean up code here

        self.log.warning("   stopped ")
        # mode log file and savefilename
        if stop_service:
            time.sleep(2)
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


def cli(serializer: str = "default", port: Optional[str] = None):
    if port == None:
        port = DLP.SERVICE_PORT
    s = DLP(serializer=serializer)
    s.bind("tcp://0.0.0.0:{0}".format(port))  # broadcast on all IPs
    print("running DLPZeroService")
    s.run()
    print("done")


if __name__ == "__main__":
    defopt.run(cli)
