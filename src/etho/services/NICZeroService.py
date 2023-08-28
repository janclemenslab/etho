from .ZeroService import BaseZeroService
import time
import sys
import numpy as np
from .utils.log_exceptions import for_all_methods, log_exceptions
import logging

try:
    import PyDAQmx as daq

    pydaqmx_import_error = None
except ImportError as pydaqmx_import_error:
    pass


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class NIC(BaseZeroService):
    """[summary]"""

    LOGGING_PORT = 1450  # set this to range 1420-1460
    SERVICE_PORT = 4250  # last to digits match logging output_channels - but start with "42" instead of "14"
    SERVICE_NAME = "NIC"  # short, uppercase, 3-letter ID of the service (equals class name)

    def setup(self, period, duty_cycle, duration, output_channel):
        """Setup the trigger service (intiates the digital output channels).

        Args:
            duration (float): Unused - kept to keep the interface same across services [description]
            output_channels (str): , e.g. "/dev1/port0/line0:1"
        """
        if pydaqmx_import_error is not None:
            raise pydaqmx_import_error

        self._time_started = None
        self.duration = float(duration)

        self.task = daq.Task()
        self.task.CreateCOPulseChanFreq(output_channel, "", daq.DAQmx_Val_Hz, daq.DAQmx_Val_Low, 0.0, 1/float(period),duty_cycle)
        self.task.DAQmxCfgImplicitTiming(daq.DAQmx_Val_ContSamps, 1000)

    def start(self):
        self.task.DAQmxStartTask()
        self._time_started = time.time()

    def stop(self):
        self.task.DAQmxStopTask()

    def finish(self, stop_service=False):
        self.log.warning("stopping")
        self.stop()
        time.sleep(0.2)
        self.task.DAQmxClearTask()
        self.cleanup()
        # clean up code here
        self.log.warning("   stopped ")
        # mode log file and savefilename
        if stop_service:
            time.sleep(.2)
            self.service_stop()
        return True

    def is_busy(self):
        return self._time_started is not None

    def test(self):
        return True

    def cleanup(self):
        self.finish()
        # your code here
        return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        ser = sys.argv[1]
    else:
        ser = "default"
    s = NIC(serializer=ser)
    s.bind("tcp://0.0.0.0:{0}".format(NIC.SERVICE_PORT))  # broadcast on all IPs
    s.run()
