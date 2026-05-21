import logging
import threading
import time

import numpy as np

from . import camera
from .callbacks import callbacks


logger = logging.getLogger(__name__)


class ResumableZeroService:
    def __init__(self):
        self.state = "new"
        self.log = logger

    def setup_hardware(self):
        raise NotImplementedError

    def prepare_run(self, *args, **kwargs):
        raise NotImplementedError

    def start(self):
        raise NotImplementedError

    def stop_run(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def information(self):
        return getattr(self, "info", {})


def array_generator(data):
    yield data


def close_callback(callback, sleep_time=0.05):
    try:
        callback.close(sleep_time=sleep_time)
    except TypeError:
        callback.close()


class ResumableDAQ(ResumableZeroService):
    def __init__(self, params):
        super().__init__()
        self.params = params
        self.callbacks = []
        self.info = {}

    def setup_hardware(self):
        import etho.services.DAQZeroService as daq_service

        self.log.info("Setting up DAQ hardware.")
        daqmx_import_error = getattr(daq_service, "daqmx_import_error", None)
        if daqmx_import_error is not None:
            raise ImportError(daqmx_import_error)
        if not hasattr(daq_service, "IOTask"):
            raise ImportError("DAQ IOTask is unavailable. Check PyDAQmx installation.")

        self.fs = self.params["samplingrate"]
        self.dev_name = self.params.get("device") or "Dev1"
        self.clock_source = self.params["clock_source"]
        self.nb_inputsamples_per_cycle = self.params["nb_inputsamples_per_cycle"]
        self.analog_chans_in = self.params["analog_chans_in"]
        self.analog_chans_out = self.params["analog_chans_out"]
        self.digital_chans_out = self.params["digital_chans_out"]
        IOTask = daq_service.IOTask

        if self.analog_chans_in:
            self.taskAI = IOTask(
                dev_name=self.dev_name,
                cha_name=self.analog_chans_in,
                rate=self.fs,
                nb_inputsamples_per_cycle=self.nb_inputsamples_per_cycle,
                clock_source=self.clock_source,
                logger=self.log,
            )
            self.taskAI.data_rec = []
        if self.analog_chans_out:
            self.taskAO = IOTask(
                dev_name=self.dev_name,
                cha_name=self.analog_chans_out,
                rate=self.fs,
                clock_source=self.clock_source,
                logger=self.log,
            )
        if self.digital_chans_out:
            self.taskDO = IOTask(
                dev_name=self.dev_name,
                cha_name=self.digital_chans_out,
                rate=self.fs,
                clock_source=self.clock_source,
                logger=self.log,
            )
        self.info = {
            "job": {
                "sample rate": f"{self.fs}Hz",
                "analog output": self.analog_chans_out,
                "digital output": self.digital_chans_out,
                "analog input": self.analog_chans_in,
            }
        }
        self.state = "ready"
        self.log.info("DAQ hardware ready.")
        return self

    def prepare_run(self, savefilename, analog_data_out=None, digital_data_out=None, duration=None, metadata=None):
        self.stop_run()
        self.savefilename = savefilename
        self.metadata = metadata or {}
        self._time_started = None
        self.prev_elapsed = 0
        self.log.info(f"Preparing DAQ run: {savefilename}.")

        if analog_data_out is not None:
            analog_data_out = np.asarray(analog_data_out, dtype=np.float64)
            if analog_data_out.ndim == 1:
                analog_data_out = analog_data_out.reshape(-1, 1)
        if digital_data_out is not None:
            digital_data_out = np.asarray(digital_data_out, dtype=np.uint8)
            if digital_data_out.ndim == 1:
                digital_data_out = digital_data_out.reshape(-1, 1)

        if duration is None:
            n_samples = 0
            if analog_data_out is not None:
                n_samples = analog_data_out.shape[0]
            if digital_data_out is not None:
                n_samples = max(n_samples, digital_data_out.shape[0])
            duration = n_samples / self.fs if n_samples else self.params.get("duration", -1)
        self.duration = duration

        if self.analog_chans_out:
            if analog_data_out is None:
                analog_data_out = np.zeros((int(duration * self.fs), len(self.analog_chans_out)), dtype=np.float64)
            if analog_data_out.shape[1] != len(self.analog_chans_out):
                raise ValueError("analog_data_out channel count does not match analog_chans_out")
            self.taskAO.data_gen = array_generator(analog_data_out)
        if self.digital_chans_out:
            if digital_data_out is None:
                digital_data_out = np.zeros((int(duration * self.fs), len(self.digital_chans_out)), dtype=np.uint8)
            if digital_data_out.shape[1] != len(self.digital_chans_out):
                raise ValueError("digital_data_out channel count does not match digital_chans_out")
            self.taskDO.data_gen = array_generator(digital_data_out)
        for task_name in ("taskAI", "taskDO", "taskAO"):
            task = getattr(self, task_name, None)
            if task is not None:
                if hasattr(task, "samples_read"):
                    try:
                        task.samples_read.value = 0
                    except Exception:
                        pass
                if hasattr(task, "_newdata_event"):
                    task._newdata_event.clear()

        if self.analog_chans_in:
            attrs = {
                "rate": self.fs,
                "analog_chans_in": self.analog_chans_in,
                "analog_chans_out": self.analog_chans_out,
                "digital_chans_out": self.digital_chans_out,
                **self.metadata,
            }
            common = {
                "file_name": self.savefilename,
                "nb_inputsamples_per_cycle": self.nb_inputsamples_per_cycle,
                "nb_analog_chans_in": len(self.analog_chans_in),
                "attrs": attrs,
            }
            self.callbacks = []
            self.taskAI.data_rec = []
            for cb_name, cb_params in (self.params.get("callbacks") or {}).items():
                task_kwargs = common if cb_params is None else {**common, **cb_params}
                callback = callbacks[cb_name].make_concurrent(task_kwargs=task_kwargs)
                self.callbacks.append(callback)
                self.taskAI.data_rec.append(callback)
                self.log.info(f"   callback {cb_name}.")

        if duration and duration > 0:
            self._thread_timer = threading.Timer(duration, self.stop_run)
        self.info = {
            "job": {
                "sample rate": f"{self.fs}Hz",
                "analog output": self.analog_chans_out,
                "digital output": self.digital_chans_out,
                "analog input": self.analog_chans_in,
                "duration": f"{self.duration}s",
                "savefilename": self.savefilename,
                "metadata": self.metadata,
            }
        }
        self.state = "prepared"
        self.log.info(f"DAQ run prepared for {self.duration}s.")
        return self

    def start(self):
        self.log.info("Starting DAQ run.")
        for callback in self.callbacks:
            callback.start()
        if self.analog_chans_out:
            self.taskAO.StartTask()
        if self.digital_chans_out:
            self.taskDO.StartTask()
        if self.analog_chans_in:
            self.taskAI.StartTask()
        self._time_started = time.time()
        self.prev_elapsed = 0
        if hasattr(self, "_thread_timer"):
            self._thread_timer.start()
        self.state = "running"
        self.log.info("DAQ run started.")

    def stop_run(self):
        was_active = self.state in {"prepared", "running"}
        if self.state == "running":
            self.log.info("Stopping DAQ run.")
        if hasattr(self, "_thread_timer"):
            self._thread_timer.cancel()
            del self._thread_timer
        for task_name in ("taskAI", "taskDO", "taskAO"):
            task = getattr(self, task_name, None)
            if task is not None:
                try:
                    task.StopTask()
                except Exception as e:
                    self.log.debug(e)
        for callback in self.callbacks:
            try:
                callback.finish()
                close_callback(callback)
            except Exception as e:
                self.log.debug(e)
        self.callbacks = []
        if hasattr(self, "taskAI"):
            self.taskAI.data_rec = []
        if hasattr(self, "taskAO"):
            self.taskAO.data_gen = None
        if hasattr(self, "taskDO"):
            self.taskDO.data_gen = None
        if self.state != "new":
            self.state = "stopped"
        if was_active:
            self.log.info("DAQ run stopped.")

    def close(self):
        self.stop_run()
        self.log.info("Closing DAQ hardware.")
        for task_name in ("taskAI", "taskDO", "taskAO"):
            task = getattr(self, task_name, None)
            if task is not None:
                try:
                    task.ClearTask()
                except Exception as e:
                    self.log.debug(e)
        self.state = "closed"
        self.log.info("DAQ hardware closed.")

    def progress(self):
        elapsed = time.time() - self._time_started if getattr(self, "_time_started", None) else 0
        elapsed_delta = elapsed - getattr(self, "prev_elapsed", 0)
        self.prev_elapsed = elapsed
        return {
            "total": self.duration if getattr(self, "duration", None) else 0,
            "elapsed": elapsed,
            "elapsed_delta": elapsed_delta,
            "elapsed_units": "seconds",
        }


class ResumableGCM(ResumableZeroService):
    def __init__(self, params):
        super().__init__()
        self.params = params
        self.callbacks = []
        self.callback_names = []
        self.frameNumber = 0
        self.prev_framenumber = 0
        self.prev_elapsed = 0
        self.info = {}

    def setup_hardware(self):
        self.log.info("Setting up camera hardware.")
        params = {
            "binning": 1,
            "gamma": 1,
            "gain": 0,
            "brightness": 0,
            "optimize_auto_exposure": False,
            "external_trigger": False,
            "frame_offx": 0,
            "frame_offy": 0,
            **self.params,
        }
        self.params = params
        self.c = camera.make[params["cam_type"]](str(params["cam_serialnumber"]))
        try:
            self.c.init()
        except Exception:
            self.c.reset()
            self.c.init()

        self.c.roi = [params["frame_offx"], params["frame_offy"], params["frame_width"], params["frame_height"]]
        self.c.exposure = params["shutter_speed"]
        self.c.brightness = params["brightness"]
        self.c.gamma = params["gamma"]
        self.c.gain = params["gain"]
        self.c.framerate = params["frame_rate"]
        self.c.binning = params["binning"]
        if params["optimize_auto_exposure"]:
            self.c.optimize_auto_exposure()

        self.c.disable_gpio_strobe()
        self.c.external_trigger = False
        self.c.start()
        self.test_image, _, _ = self.c.get()
        self.c.stop()
        self.c.external_trigger = params["external_trigger"]

        self.frame_width, self.frame_height, self.frame_channels = self.test_image.shape
        self.framerate = self.c.framerate
        self.info = self._information(savefilename=None, duration=None, callbacks={})
        self.state = "ready"
        self.log.info("Camera hardware ready.")
        return self

    def _information(self, savefilename, duration, callbacks):
        iii = self.c.info_imaging() if hasattr(self.c, "info_imaging") else {}
        if "exposure" in iii:
            iii["exposure"] = f"{iii['exposure']:1.2f}ms"
        params = dict(self.params)
        params["exposure"] = f"{params['shutter_speed'] / 1_000:1.2f}ms"
        params["framerate"] = params["frame_rate"]
        params["offsetX"], params["offsetY"], params["width"], params["height"] = (
            params["frame_offx"],
            params["frame_offy"],
            params["frame_width"],
            params["frame_height"],
        )
        hii = self.c.info_hardware() if hasattr(self.c, "info_hardware") else {}
        try:
            hii.update({k: v if v is not None else "defaults" for k, v in callbacks.items()})
        except AttributeError:
            pass
        if savefilename is not None:
            hii["savefilename"] = savefilename
        if duration is not None:
            hii["duration"] = duration
        return {"hardware": hii, "image": (iii, params)}

    def prepare_run(self, savefilename, duration, preview=False):
        self.stop_run()
        self.savefilename = savefilename
        self.duration = duration
        self.nFrames = int(self.framerate * duration + 100)
        self.frameNumber = 0
        self.prev_framenumber = 0
        self.prev_elapsed = 0
        if hasattr(self.c, "_t0"):
            self.c._t0 = time.time()
        self.callbacks = []
        self.callback_names = []
        self.log.info(f"Preparing camera run: {savefilename}.")
        common = {
            "file_name": self.savefilename,
            "frame_rate": self.framerate,
            "frame_height": self.frame_height,
            "frame_width": self.frame_width,
        }
        run_callbacks = {"disp_fast": None} if preview else (self.params.get("callbacks") or {})
        for cb_name, cb_params in run_callbacks.items():
            task_kwargs = common if cb_params is None else {**common, **cb_params}
            self.callbacks.append(callbacks[cb_name].make_concurrent(task_kwargs=task_kwargs))
            self.callback_names.append(cb_name)
            self.log.info(f"   callback {cb_name}.")
        self._thread_stopper = threading.Event()
        self._worker_thread = threading.Thread(target=self._worker, args=(self._thread_stopper,))
        if duration and duration > 0:
            self._thread_timer = threading.Timer(duration, self.stop_run)
        self.info = self._information(self.savefilename, self.duration, run_callbacks)
        self.state = "prepared"
        self.log.info(f"Camera run prepared for {self.duration}s.")
        return self

    def start(self):
        self.log.info("Starting camera run.")
        for callback in self.callbacks:
            callback.start()
        self._time_started = time.time()
        self.prev_elapsed = 0
        self._prev_elapsed = 0
        self._worker_thread.start()
        if hasattr(self, "_thread_timer"):
            self._thread_timer.start()
        self.state = "running"
        self.log.info("Camera run started.")

    def _worker(self, stop_event):
        self.log.info("Camera worker started.")
        self.c.enable_gpio_strobe()
        self.c.start()
        while not stop_event.is_set() and self.frameNumber < self.nFrames:
            try:
                image, image_ts, system_ts = self.c.get()
            except Exception as e:
                self.log.exception("Camera get failed", exc_info=e)
                break
            for callback_name, callback in zip(self.callback_names, self.callbacks):
                package = (0, (system_ts, image_ts)) if "timestamps" in callback_name else (image, (system_ts, image_ts))
                callback.send(package)
            self.frameNumber += 1
        try:
            self.c.stop()
        except Exception:
            pass
        self.log.info("Camera worker stopped.")

    def stop_run(self):
        was_active = self.state in {"prepared", "running"}
        if self.state == "running":
            self.log.info("Stopping camera run.")
        if hasattr(self, "_thread_timer"):
            self._thread_timer.cancel()
            del self._thread_timer
        if hasattr(self, "_thread_stopper"):
            self._thread_stopper.set()
        try:
            self.c.disable_gpio_strobe()
            self.c.stop()
        except Exception:
            pass
        if hasattr(self, "_worker_thread") and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=0.5)
        for callback in self.callbacks:
            try:
                callback.finish()
                close_callback(callback)
            except Exception as e:
                self.log.debug(e)
        self.callbacks = []
        self.callback_names = []
        if self.state != "new":
            self.state = "stopped"
        if was_active:
            self.log.info("Camera run stopped.")

    def close(self):
        self.stop_run()
        self.log.info("Closing camera hardware.")
        try:
            self.c.close()
        except Exception:
            pass
        self.state = "closed"
        self.log.info("Camera hardware closed.")

    def progress(self):
        elapsed = time.time() - self._time_started if getattr(self, "_time_started", None) else 0
        elapsed_delta = elapsed - getattr(self, "prev_elapsed", 0)
        frame_delta = self.frameNumber - self.prev_framenumber
        self.prev_framenumber = self.frameNumber
        self.prev_elapsed = elapsed
        return {
            "total": self.duration if getattr(self, "duration", None) else 0,
            "elapsed": elapsed,
            "elapsed_delta": elapsed_delta,
            "elapsed_units": "seconds",
            "framenumber": self.frameNumber,
            "framenumber_delta": frame_delta,
            "framenumber_units": "frames",
        }
