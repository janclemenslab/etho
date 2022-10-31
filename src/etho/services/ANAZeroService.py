from .ZeroService import BaseZeroService  # import super class
import time    # for timer
import sys
import numpy as np
from .utils.log_exceptions import for_all_methods, log_exceptions
import logging
try:
    import PyDAQmx as daq
    from PyDAQmx.DAQmxCallBack import *
    from PyDAQmx.DAQmxConstants import *
    from PyDAQmx.DAQmxFunctions import *
    pydaqmx_import_error = None
except ImportError as pydaqmx_import_error:
    pass


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class ANA(BaseZeroService):
    """[summary]"""

    LOGGING_PORT = 1451  # set this to range 1420-1460
    SERVICE_PORT = 4251  # last to digits match logging output_channels - but start with "42" instead of "14"
    SERVICE_NAME = "ANA"  # short, uppercase, 3-letter ID of the service (equals class name)

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

        self.samples_read = daq.int32()
        dev_name = '/Dev1'
        cha_name = ['ao2', 'ao3']
        self.cha_name = [dev_name + '/' + ch for ch in cha_name]  # append device name
        self.cha_string = ", ".join(self.cha_name)
        self.num_channels = len(cha_name)
        self.num_samples_per_chan = 10_000
        self._data = np.ones((self.num_samples_per_chan, self.num_channels), dtype=np.float64)  # init empty data array

        limits = 10
        self.task = daq.Task()
        self.task.CreateAOVoltageChan(self.cha_string, "", -limits, limits, DAQmx_Val_Volts, None)
        self.task.StartTask()

    def set_value(self, state, duration=0.0001):
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
        self.task.WriteAnalogF64(self._data.shape[0], 0, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByScanNumber,
                                    self._data * state, daq.byref(self.samples_read), None)

        # This is currently blocking - not so great
        if duration is not None:
            time.sleep(duration)  # alternatively could  return immediately using a threaded timer
            self.task.WriteAnalogF64(self._data.shape[0], 0, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByScanNumber,
                                     self._data * 0, daq.byref(self.samples_read), None)
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
    s = ANA(serializer=ser)
    s.bind("tcp://0.0.0.0:{0}".format(ANA.SERVICE_PORT))  # broadcast on all IPs
    s.run()
