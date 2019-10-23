#!/usr/bin/env python
# required imports
from .ZeroService import BaseZeroService  # import super class
import zerorpc # for starting service in `main()`
import time    # for timer
import threading
import sys
from .utils.log_exceptions import for_all_methods, log_exceptions
import logging


# decorate all methods in the class so that exceptions are properly logged
@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class TMP(BaseZeroService):

    LOGGING_PORT = 1443  # set this to range 1420-1460
    SERVICE_PORT = 4243  # last to digits match logging port - but start with "42" instead of "14"
    SERVICE_NAME = "TMP" # short, uppercase, 3-letter ID of the service (equals class name)

    def setup(self, duration):
        self._time_started = None
        self.duration = float(duration)

        # APPLICATION SPECIFIC SETUP CODE HERE

        # background jobs should be run and controlled via a thread
        # threads can be stopped by setting an event: `_thread_stopper.set()`
        self._thread_stopper = threading.Event()
        # and/or via a timer
        if self.duration>0:
            self._thread_timer = threading.Timer(self.duration, self.finish, kwargs={'stop_service':True})
        #
        self._worker_thread = threading.Thread(
            target=self._worker, args=(self._thread_stopper,))

    def start(self):
        self._time_started = time.time()

        # background jobs should be run and controlled via a thread
        self._worker_thread.start()
        self.log.info('started')
        if hasattr(self, '_thread_timer'):
             self.log.info('duration {0} seconds'.format(self.duration))
             self._thread_timer.start()
             self.log.info('finish timer started')

    def _worker(self, stop_event):
        RUN = True
        while RUN and not stop_event.wait(0.1):
            pass # APPLICATION SPECIFIC SETUP CODE HERE

    def finish(self, stop_service=False):
        self.log.warning('stopping')
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


if __name__ == '__main__':
    if len(sys.argv) > 1:
        ser = sys.argv[1]
    else:
        ser = 'default'
    s = TMP(serializer=ser)
    s.bind("tcp://0.0.0.0:{0}".format(TMP.SERVICE_PORT))  # broadcast on all IPs
    s.run()
