#!/usr/bin/env python
import threading
from .ZeroService import BaseZeroService
import zerorpc
import time
import sys
from .utils.log_exceptions import for_all_methods, log_exceptions
import logging

try:
    import gpiozero
except Exception as e:
    print("IGNORE IF RUN ON HEAD")
    print(e)

@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class REL(BaseZeroService):
    '''
    toggle relay using gpiozero library
    very hacky since the relay cannot be toggled (requires 5V GPIO, not 3.3V as in rpi).
    so we turn on the relay by initializing the pin, and turn it off by de-initializing it
    '''
    LOGGING_PORT = 1447
    SERVICE_PORT = 4247
    SERVICE_NAME = 'REL'

    def setup(self, pin, duration):
        self.pin = pin  # data pin
        self.duration = duration  # total duration of experiments
        self.relay = None
        self._thread_timer = threading.Timer(self.duration, self.finish, kwargs={'stop_service':True})

    def start(self):
        self._time_started = time.time()
        self._turn_on()
        if self.duration > 0:
            self.log.info('duration {0} seconds'.format(self.duration))
            # will execute FINISH after N seconds
            self._thread_timer.start()
            self.log.info('finish timer started')

    def finish(self, stop_service=False):
        self.log.warning('stopping')
        if hasattr(self, '_thread_stopper'):
            self._thread_stopper.set()
        if hasattr(self, '_thread_timer'):
            self._thread_timer.cancel()
        self._turn_off()
        self.log.warning('   stopped ')
        if stop_service:
            self.service_stop()

    def _turn_on(self):
        self.relay = gpiozero.LED(self.pin)
        self.relay.on()

    def _turn_off(self):
        if self.relay:
            self.relay.off()
            self.relay.close()

    def disp(self):
        pass

    def is_busy(self):
        if self.relay:
            return True  # is this the right why to check whether thread is running?
        else:
            return False

    def info(self):
        if self.is_busy():
            # NOTE: save to access thread variables? need lock or something?
            return "state of relay is {1}".format(self.is_busy())
        else:
            return None

    def test(self):
        pass

    def cleanup(self):
        self.finish()
        if hasattr(self, '_queue_thread'):
            del(self._queue_thread)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        ser = sys.argv[1]
    else:
        ser = 'default'
    s = REL(serializer=ser)
    s.bind("tcp://0.0.0.0:{0}".format(REL.SERVICE_PORT))
    s.run()
