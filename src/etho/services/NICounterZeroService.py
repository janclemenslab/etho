from .ZeroService import BaseZeroService
import time
import sys
import numpy as np
from . import register_service
from .utils.log_exceptions import for_all_methods, log_exceptions
from ..utils.config import undefaultify
import logging
import threading

try:
    import PyDAQmx as daq

    pydaqmx_import_error = None
except (ImportError, NotImplementedError) as pydaqmx_import_error:
    pass


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
@register_service
class NIC(BaseZeroService):
    """NI DAQmx Counter service for generating pulse trains via a digital output,
    for instance as an external frame trigger for cameras.
    """

    LOGGING_PORT = 1450  # set this to range 1420-1460
    SERVICE_PORT = 4250  # last to digits match logging output_channels - but start with "42" instead of "14"
    SERVICE_NAME = "NIC"  # short, uppercase, 3-letter ID of the service (equals class name)
    CLIENT_START_GROUP = "trigger"

    @classmethod
    def setup_client(cls, service_key, service_index, prot, defaults, playlistfile, save_prefix, preview, new_console):
        this = defaults.copy()
        this.update(prot[service_key])

        if prot[service_key].get("port") is None:
            prot[service_key]["port"] = cls.SERVICE_PORT + service_index

        service = cls.make(
            this["serializer"],
            this["host"],
            this["python_exe"],
            new_console=new_console,
            port=prot[service_key]["port"],
        )

        params = undefaultify(prot[service_key])
        service.setup(
            params["output_channel"],
            prot["maxduration"] + 10,
            params["frequency"],
            params["duty_cycle"],
            params,
        )
        save_suffix = f"_{service_index + 1}" if service_index > 0 else ""
        service.init_local_logger(f"{this['savefolder']}/{save_prefix}/{save_prefix}{save_suffix}_nic.log")
        return service

    def setup(self, output_channel, duration, frequency, duty_cycle, params):
        """Setup the counter service (intiates the digital output channels).

        Args:
            output_channels (str): Digital output channel, e.g. "/dev1/port0/line0:1"
            duration (float): Duration of the service.
            frequency (float): Frequency of the pulse train in Hz.
            duty_cycle (float): Duty cycle (pulse duration/period = duration * frequency) of the pulse train.
            params (_type_): Unused.

        Raises:
            pydaqmx_import_error: Raised when the pydaqmx could not be imported.
        """
        if pydaqmx_import_error is not None:
            raise pydaqmx_import_error

        self._time_started = None
        self.duration = float(duration)

        self.task = daq.Task()
        self.task.CreateCOPulseChanFreq(output_channel, "", daq.DAQmx_Val_Hz, daq.DAQmx_Val_Low, 0.0, frequency, duty_cycle)
        self.task.CfgImplicitTiming(daq.DAQmx_Val_ContSamps, 1000)

        if self.duration > 0:  # if zero, will stop when nothing is to be outputted
            self._thread_timer = threading.Timer(self.duration, self.finish, kwargs={"stop_service": True})

    def start(self):
        self.task.StartTask()
        self.log.warning("Started")
        self._time_started = time.time()
        if hasattr(self, "_thread_timer"):
            self.log.warning(f"duration {self.duration} seconds")
            self._thread_timer.start()
            self.log.warning("finish timer started")

    def stop(self):
        self.task.StopTask()
        self.log.warning("Stopped")

    def finish(self, stop_service=False):
        self.log.warning("stopping")
        self.stop()
        time.sleep(0.2)
        self.task.ClearTask()
        self.cleanup()
        # clean up code here
        self.log.warning("   stopped ")
        # mode log file and savefilename
        if stop_service:
            time.sleep(0.2)
            self.service_stop()
        return True

    def is_busy(self):
        return self._time_started is not None

    def test(self):
        return True

    def cleanup(self):
        # self.finish()
        # your code here
        return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        ser = sys.argv[1]
    else:
        ser = "default"
    if len(sys.argv) > 2:
        port = sys.argv[2]
    else:
        port = NIC.SERVICE_PORT
    s = NIC(serializer=ser)
    s.bind("tcp://0.0.0.0:{0}".format(port))  # broadcast on all IPs
    s.run()
