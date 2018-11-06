#!/usr/bin/env python
# required imports
from .ZeroService import BaseZeroService  # import super class
import zerorpc  # for starting service in `main()`
import time    # for timer
import threading


from PyDAQmx import Task
import numpy as np


class NIT(BaseZeroService):

    LOGGING_PORT = 1450  # set this to range 1420-1460
    SERVICE_PORT = 4250  # last to digits match logging port - but start with "42" instead of "14"
    SERVICE_NAME = "NIT"  # short, uppercase, 3-letter ID of the service (equals class name)

    def setup(self, duration):
        self._time_started = None
        self.duration = float(duration)

        # APPLICATION SPECIFIC SETUP CODE HERE

        # background jobs should be run and controlled via a thread
        # threads can be stopped by setting an event: `_thread_stopper.set()`

    def send(port="/Dev1/port0/line0:7", data=np.array([0, 1, 1, 0, 1, 0, 1, 0], dtype=np.uint8)):
        self.log.info('sending {data} on {port}')
        task = Task()
        task.CreateDOChan(port, "", PyDAQmx.DAQmx_Val_ChanForAllLines)
        task.StartTask()
        task.WriteDigitalLines(1, 1, 10.0, PyDAQmx.DAQmx_Val_GroupByChannel, data, None, None)
        task.StopTask()
        self.log.info('   success.')

    def start(self):
        pass



if __name__ == '__main__':
    s = zerorpc.Server(NIT())  # expose class via zerorpc
    s.bind("tcp://0.0.0.0:{0}".format(NIT.SERVICE_PORT))  # broadcast on all IPs
    s.run()
