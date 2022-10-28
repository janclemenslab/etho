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
class NIT(BaseZeroService):
    """[summary]"""

    LOGGING_PORT = 1450  # set this to range 1420-1460
    SERVICE_PORT = 4250  # last to digits match logging output_channels - but start with "42" instead of "14"
    SERVICE_NAME = "NIT"  # short, uppercase, 3-letter ID of the service (equals class name)

    def setup(self, duration, output_channels):
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
        self.task.CreateDOChan(output_channels, "", daq.DAQmx_Val_ChanForAllLines)
        self.nb_channels = None  # TODO: get nb_channels from task obhect
        self.task.StartTask()

        # APPLICATION SPECIFIC SETUP CODE HERE

        # background jobs should be run and controlled via a thread
        # threads can be stopped by setting an event: `_thread_stopper.set()`

    def send_trigger(self, state, duration=0.0001):
        """Set the digital output channels to specified state.

        Args:
            state ([type]): [description]
            duration (float, optional): How long the trigger state should last (in seconds).
                                        Will reset to all 0 after the duration.
                                        If None will return immediatelly and keep the trigger state permanent.
                                        Defaults to 0.0001.
        """
        # if len(state) != self.nb_channels:
        #     raise ValueError(f"State vector should have same length as the number of digital output channels. Is {len(state)}, should be {'x'}.")
        self.log.info('sending {state} on {output_channels}')
        state = np.array(state, dtype=np.uint8)
        self.task.WriteDigitalLines(1, 1, 10.0, daq.DAQmx_Val_GroupByChannel, state, None, None)
        if duration is not None:
            time.sleep(duration)  # alternatively could  return immediately using a threaded timer
            self.task.WriteDigitalLines(1, 1, 10.0, daq.DAQmx_Val_GroupByChannel, 0*state, None, None)
        self.log.info('   success.')

    def start(self):
        pass

    def finish(self, stop_service=False):
        self.log.warning('stopping')
        self.task.StopTask()

        # clean up code here
        self.log.warning('   stopped ')
        # mode log file and savefilename
        if stop_service:
            time.sleep(2)
            self.service_stop()

    def is_busy(self):
        return True # should return True/False

    def test(self):
        return True

    def cleanup(self):
        self.finish()
        # your code here
        return True


if __name__ == '__main__':
    if len(sys.argv) > 1:
        ser = sys.argv[1]
    else:
        ser = 'default'
    s = NIT(serializer=ser)
    s.bind("tcp://0.0.0.0:{0}".format(NIT.SERVICE_PORT))  # broadcast on all IPs
    s.run()
