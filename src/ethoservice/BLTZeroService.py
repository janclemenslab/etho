#!/usr/bin/env python
# required imports
from .ZeroService import BaseZeroService  # import super class
import time    # for timer
import threading
import sys
import logging
import defopt
from typing import Optional
import os

from .utils.log_exceptions import for_all_methods, log_exceptions
from .utils.concurrent_task import Pipe

try:
    from pybmt.callback.threshold_callback import ThresholdCallback
    from pybmt.callback.broadcast_callback import BroadcastCallback
    from pybmt.fictrac.service import FicTracDriver
    pybmt_error = None
except ImportError as pybmt_error:
    pass

# decorate all methods in the class so that exceptions are properly logged
@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class BLT(BaseZeroService):

    LOGGING_PORT = 1452  # set this to range 1420-1460
    SERVICE_PORT = 4252  # last two digits match logging port - but start with "42" instead of "14"
    SERVICE_NAME = "BLT" # short, uppercase, 3-letter ID of the service (must equal class name)

    def setup(self, savefilename, duration, params):
        if pybmt_error is not None:
            raise pybmt_error
        self.log.info('setup')
        self._time_started = None
        self.duration = float(duration)

        # APPLICATION SPECIFIC SETUP CODE HERE

        # Instantiate a FicTracDriver object to handle running of FicTrac in the background
        # and communication of program state.
        self.tracDrv = FicTracDriver.as_server(config_file=params['config_file'],  savefilename=savefilename)

        # self._thread_stopper = threading.Event()
        if self.duration>0:
            self._thread_timer = threading.Timer(self.duration, self.finish, kwargs={'stop_service':True})
        # self._worker_thread = threading.Thread(target=self._worker, args=(self._thread_stopper,))

    def start(self):
        self._time_started = time.time()
        # self._worker_thread.start()
        # background jobs should be run and controlled via a thread
        self.log.info('started')
        if hasattr(self, '_thread_timer'):
             self.log.info('duration {0} seconds'.format(self.duration))
             self._thread_timer.start()
             self.log.info('finish timer started')

    # def _worker(self, stop_event):
    #     pass

    def finish(self, stop_service=False):
        self.log.warning('stopping')
        # stop thread if necessary
        if hasattr(self, '_thread_stopper'):
            self._thread_stopper.set()
        if hasattr(self, '_thread_timer'):
            self._thread_timer.cancel()
        # clean up code here
        self.tracDrv.fictrac_process.terminate()
        del self.tracDrv  # free resource

        self.log.warning('   stopped ')
        # mode log file and savefilename
        if stop_service:
            time.sleep(2)
            self.service_stop()

    def disp(self):
        pass

    def is_busy(self):
        return True # should return True/False

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


def cli(serializer: str = 'default', port: Optional[str] = None):
    if port == None:
        port = BLT.SERVICE_PORT
    s = BLT(serializer=serializer)
    s.bind("tcp://0.0.0.0:{0}".format(port))  # broadcast on all IPs
    print('running BLTZeroService')
    s.run()
    print('done')


if __name__ == '__main__':
    defopt.run(cli)
