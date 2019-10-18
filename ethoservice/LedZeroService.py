#!/usr/bin/env python
import threading
from .ZeroService import BaseZeroService
import zerorpc
import RPi.GPIO as GPIO
import time
import sys
from .utils.log_exceptions import for_all_methods, log_exceptions
import logging


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class LED(BaseZeroService):
    """
    LED control
    select output port, amp, freq, dc, duration etc. - !via playlist!
    uses RPi.GPIO - NO - use GPIOzero
    maybe split protocol - one effector LED (red and green - map to two GPIO ports)
                         - one IR LED for logging/synchronization
    """
    LOGGING_PORT = 1453
    SERVICE_PORT = 4253
    SERVICE_NAME = 'LED'

    def setup(self, pin_out, pin_frequency, pin_dc, duration):
        self.pin_out = pin_out
        self.pin_period = pin_frequency
        self.pin_dc = pin_dc
        self.duration = duration
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.pin_out, GPIO.OUT)

        self._thread_stopper = threading.Event()
        self._queue_thread = threading.Thread(
            target=self._dummy, args=(self._thread_stopper,))

    def start(self):
        self._time_started = time.time()
        self._queue_thread.start()

    def _dummy(self, stop_event):
        RUN = True
        while RUN and not stop_event.wait(0.1):
            pass

    def finish(self):
        if hasattr(self, '_thread_stopper'):
            self._thread_stopper.set()

    def led_on(self, frequency, dc):
        GPIO.output(self.pin_out, GPIO.HIGH)

    def led_off(self):
        GPIO.output(self.pin_out, GPIO.LOW)

    def disp(self):
        pass

    def is_busy(self):
        return True

    def info(self):
        return "info"

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
    s = LED(serializer=ser)
    s.bind("tcp://0.0.0.0:{0}".format(LED.SERVICE_PORT))
    s.run()
