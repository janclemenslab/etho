#!/usr/bin/env python
# required imports
from .ZeroService import BaseZeroService  # import super class
import zerorpc  # for starting service in `main()`
import time    # for timer
import threading
import sys
import PyDAQmx as daq
import numpy as np


class NIT(BaseZeroService):

    LOGGING_PORT = 1450  # set this to range 1420-1460
    SERVICE_PORT = 4250  # last to digits match logging port - but start with "42" instead of "14"
    SERVICE_NAME = "NIT"  # short, uppercase, 3-letter ID of the service (equals class name)

    def setup(self, duration, port):
        self._time_started = None
        self.duration = float(duration)

        self.task = daq.Task()
        self.task.CreateDOChan(port, "", daq.DAQmx_Val_ChanForAllLines)
        self.task.StartTask()

        # APPLICATION SPECIFIC SETUP CODE HERE

        # background jobs should be run and controlled via a thread
        # threads can be stopped by setting an event: `_thread_stopper.set()`

    def send_trigger(self, data, duration=0.0001):
        self.log.info('sending {data} on {port}')
        data = np.array(data, dtype=np.uint8)
        self.task.WriteDigitalLines(1, 1, 10.0, daq.DAQmx_Val_GroupByChannel, data, None, None)
        time.sleep(duration)
        self.task.WriteDigitalLines(1, 1, 10.0, daq.DAQmx_Val_GroupByChannel, 0*data, None, None)
        self.log.info('   success.')

    def start(self):
        pass

    def finish(self, stop_service=False):
        self.log.warning('stopping')
        self.task.StopTask()

        # stop thread if necessary
        if hasattr(self, '_thread_stopper'):
            self._thread_stopper.set()
        if hasattr(self, '_thread_timer'):
            self._thread_timer.cancel()
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
