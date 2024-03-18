from .ZeroService import BaseZeroService
import time
import threading
import sys
import copy
from typing import Iterable, Sequence, Optional, Dict, Any
from .utils.log_exceptions import for_all_methods, log_exceptions
from .callbacks import callbacks
import logging
import numpy as np

daqmx_import_error = None
try:
    from .daq.IOTask import *

    daqmx_import_error = None
except (ImportError, NameError, NotImplementedError) as daqmx_import_error:
    pass


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class DAQ(BaseZeroService):
    """Bundles and synchronizes analog/digital input and output tasks."""

    LOGGING_PORT = 1449  # set this to range 1420-1460
    SERVICE_PORT = (
        4249  # last to digits match logging port - but start with "42" instead of "14"
    )
    SERVICE_NAME = (
        "DAQ"  # short, uppercase, 3-letter ID of the service (equals class name)
    )

    def setup(
        self,
        savefilename: str = None,
        play_order: Iterable = None,
        playlist_info=None,
        duration: float = -1,
        fs: int = 10000,
        display=False,
        realtime=False,
        dev_name="Dev1",
        nb_inputsamples_per_cycle=None,
        clock_source=None,
        analog_chans_out: Optional[Sequence[str]] = None,
        analog_chans_in: Sequence[str] = ["ai0"],
        digital_chans_out: Optional[Sequence[str]] = None,
        analog_data_out: Optional[Sequence[np.ndarray]] = None,
        digital_data_out: Optional[Sequence] = None,
        metadata: Optional[Dict] = None,
        params=None,
    ):
        """[summary]

        Args:
            savefilename (str, optional): [description]. Defaults to None.
            play_order (Iterable, optional): [description]. Defaults to None.
            playlist_info ([type], optional): [description]. Defaults to None.
            duration (float, optional): [description]. Defaults to -1.
            fs (int, optional): [description]. Defaults to 10000.
            display (bool, optional): [description]. Defaults to False.
            realtime (bool, optional): [description]. Defaults to False.
            nb_inputsamples_per_cycle ([type], optional): [description]. Defaults to None.
            clock_source (str, optional): None for AI-synced clock.
                                          Use 'OnboardClock' for boards that don't support this (USB-DAQ).
                                          Defaults to None.
            analog_chans_out (Sequence, optional): [description]. Defaults to None.
            analog_chans_in (Sequence, optional): [description]. Defaults to ['ai0'].
            digital_chans_out (Sequence, optional): [description]. Defaults to None.
            analog_data_out (Sequence, optional): [description]. Defaults to None.
            digital_data_out (Sequence, optional): [description]. Defaults to None.
            metadata (dict, optional): [description]. Defaults to {}.
            params: part of prot dict (prot['DAQ'])

        Raises:
            ValueError: [description]
        """
        self.status = "initializing"

        if daqmx_import_error is not None:
            raise ImportError(daqmx_import_error)

        self._time_started = None
        self.duration = duration
        self.fs = fs
        self.savefilename = savefilename
        self.metadata = metadata
        self.playlist_info = playlist_info

        self.analog_chans_out = analog_chans_out
        self.analog_chans_in = analog_chans_in
        self.digital_chans_out = digital_chans_out

        # ANALOG OUTPUT
        if self.analog_chans_out:
            self.taskAO = IOTask(
                dev_name=dev_name,
                cha_name=self.analog_chans_out,
                rate=fs,
                clock_source=clock_source,
                logger=self.log,
            )
            if analog_data_out[0].shape[-1] is not len(self.analog_chans_out):
                raise ValueError(
                    f"Number of analog output channels ({len(self.analog_chans_out)}) does not match the number of channels in the sound files ({analog_data_out[0].shape[-1]})."
                )
            play_order_new = copy.deepcopy(play_order)
            self.taskAO.data_gen = data_playlist(
                analog_data_out, play_order_new, playlist_info, self.log, name="AO"
            )
            if clock_source is None:
                self.taskAO.CfgDigEdgeStartTrig("ai/StartTrigger", DAQmx_Val_Rising)
            else:
                self.taskAO.DisableStartTrig()
        # DIGITAL OUTPUT
        if self.digital_chans_out:
            self.taskDO = IOTask(
                dev_name=dev_name,
                cha_name=self.digital_chans_out,
                rate=fs,
                clock_source=clock_source,
                logger=self.log,
            )
            play_order_new = copy.deepcopy(play_order)
            self.taskDO.data_gen = data_playlist(
                digital_data_out, play_order_new, name="DO"
            )
            if clock_source is None:
                self.taskDO.CfgDigEdgeStartTrig("ai/StartTrigger", DAQmx_Val_Rising)
            else:
                self.taskDO.DisableStartTrig()
        # ANALOG INPUT
        if self.analog_chans_in:
            self.taskAI = IOTask(
                dev_name=dev_name,
                cha_name=self.analog_chans_in,
                rate=fs,
                nb_inputsamples_per_cycle=nb_inputsamples_per_cycle,
                clock_source=clock_source,
                duration=self.duration,
                logger=self.log,
            )
            self.taskAI.data_rec = []

            self.callbacks = []
            if metadata is None:
                metadata = {}
            attrs = {
                "rate": fs,
                "analog_chans_in": analog_chans_in,
                "analog_chans_out": analog_chans_out,
                "digital_chans_out": digital_chans_out,
                **metadata,
            }
            common_task_kwargs = {
                "file_name": self.savefilename,
                "nb_inputsamples_per_cycle": nb_inputsamples_per_cycle,
                "nb_analog_chans_in": len(analog_chans_in),
                "attrs": attrs,
            }

            self.callbacks = []
            if "callbacks" in params and params["callbacks"]:
                for cb_name, cb_params in params["callbacks"].items():
                    if cb_params is not None:
                        task_kwargs = {**common_task_kwargs, **cb_params}
                    else:
                        task_kwargs = common_task_kwargs
                    callback = callbacks[cb_name].make_concurrent(
                        task_kwargs=task_kwargs
                    )
                    self.callbacks.append(callback)
                    self.taskAI.data_rec.append(callback)

        if self.duration > 0:  # if zero, will stop when nothing is to be outputted
            self._thread_timer = threading.Timer(
                self.duration, self.finish, kwargs={"stop_service": True}
            )
        self.status = "initialized"

        self.info: Dict[str, Dict[str, Any]] = dict()
        self.info["job"]: Dict[str, Any] = {
            "sample rate": f"{self.fs}Hz",
            "analog output": self.analog_chans_out,
            "digital output": self.digital_chans_out,
            "analog input": self.analog_chans_in,
            "duration": f"{self.duration}s",
            "savefilename": self.savefilename,
            "metadata": self.metadata,
        }
        self.info["playlist"] = self.playlist_info

    def start(self):
        self.status = "running"

        self._time_started = time.time()

        for task in self.taskAI.data_rec:
            task.start()

        # Arm the output tasks - won't start until the AI start is triggered
        if self.analog_chans_out:
            self.taskAO.StartTask()

        if self.digital_chans_out:
            self.taskDO.StartTask()

        # Start the AI task - generates AI start trigger and triggers the output tasks
        self.taskAI.StartTask()

        self.log.debug("started")
        if hasattr(self, "_thread_timer"):
            self.log.debug("duration {0} seconds".format(self.duration))
            self._thread_timer.start()
            self.log.debug("finish timer started")

    def finish(self, stop_service=False):
        self.status = "finishing"
        self.log.warning("stopping")
        if hasattr(self, "_thread_stopper"):
            self._thread_stopper.set()
        if hasattr(self, "_thread_timer"):
            self._thread_timer.cancel()

        
        for callback in self.callbacks:
            try:
                callback.finish()
            except Exception as e:
                self.log.warning(e)

        try: 
            self.taskAI.StopTask()
            self.log.warning("   stoppedAI")
        except InvalidTaskError as e:
            self.log.warning(e)

        # close any files in the callbacks
        for callback in self.callbacks:
            try:
                callback.close()
            except Exception as e:
                self.log.warning(e)

        self.taskAI.ClearTask()

        # stop tasks and properly close callbacks (e.g. flush data to disk and close file)
        if hasattr(self, "digital_chans_out") and self.digital_chans_out:
            # try:

            #     self.taskDO.StopTask()
            # except GenStoppedToPreventRegenOfOldSamplesError as e:
            #     pass
            # print("\n   stoppedDO")
            self.taskDO.stop()

        if hasattr(self, "analog_chans_out") and self.analog_chans_out:
            # try:
            #     self.taskAO.StopTask()
            # except GenStoppedToPreventRegenOfOldSamplesError as e:
            #     pass
            # print("\n   stoppedAO")
            self.taskAO.stop()

        if self.analog_chans_out:
            self.taskAO.ClearTask()

        if self.digital_chans_out:
            self.taskDO.ClearTask()

        self.log.warning("   stopped ")
        if stop_service:
            time.sleep(0.5)
            self.service_stop()

    def disp(self):
        pass

    def is_busy(self, ai=True, ao=True):
        taskCheckFailed = False

        taskIsDoneAI = daq.c_ulong()
        if self.analog_chans_out:
            taskIsDoneAO = daq.c_ulong()
        if ai:
            try:
                self.taskAI.IsTaskDone(taskIsDoneAI)
            except (
                daq.InvalidTaskError,
                GenStoppedToPreventRegenOfOldSamplesError,
            ) as e:
                taskCheckFailed = True
        else:
            taskIsDoneAI = 0
        if ao and self.analog_chans_out:
            try:
                self.taskAO.IsTaskDone(taskIsDoneAO)
            except (
                daq.InvalidTaskError,
                GenStoppedToPreventRegenOfOldSamplesError,
            ) as e:
                taskCheckFailed = True
        else:
            taskIsDoneAO = 0

        return not bool(taskIsDoneAI) and not bool(taskIsDoneAO) and not taskCheckFailed

    def test(self):
        return True

    def cleanup(self):
        self.finish()
        return True

    def info(self):
        if self.is_busy():
            pass  # your code here
        else:
            return None


if __name__ == "__main__":
    daqmx_import_error = None
    if len(sys.argv) > 1:
        ser = sys.argv[1]
    else:
        ser = "default"

    if len(sys.argv) > 2:
        port = sys.argv[2]
    else:
        port = DAQ.SERVICE_PORT

    logging.info("Starting DAQ service")
    s = DAQ(serializer=ser)  # expose class via zerorpc
    s.bind("tcp://0.0.0.0:{0}".format(port))  # broadcast on all IPs
    s.run()
