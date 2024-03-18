#!/usr/bin/env python
import threading
from .ZeroService import BaseZeroService
import time
import threading
from collections import namedtuple
import sys
from .utils.log_exceptions import for_all_methods, log_exceptions
import logging

try:
    import serial

    serial_import_error = None
except ImportError as serial_import_error:
    pass


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class THUA(BaseZeroService):
    """
    Temperature and Humidity sensor. connect to rpi via arduino. or directly to rpi if possible
    try DHT22 and https://github.com/adafruit/Adafruit_Python_DHT
    """

    LOGGING_PORT = 1454
    SERVICE_PORT = 4254
    SERVICE_NAME = "THUA"

    def setup(self, comport="COM3", delay=60, duration=0):
        if serial_import_error is not None:
            raise serial_import_error

        self.sensor = serial.Serial(comport, 115200, timeout=0.1)

        self.delay = delay  # delay between reads in seconds
        self.duration = duration  # total duration of experiments

        # initialize
        self._env = namedtuple("env", "type, value, units")
        self.data = []

        # setup up thread
        self._thread_timer = threading.Timer(self.duration, self.finish, kwargs={"stop_service": True})
        self._thread_stopper = threading.Event()  # not sure this is required here - but probably does not hurt
        self._queue_thread = threading.Thread(target=self._read_temperature_and_humidity, args=(self._thread_stopper,))
        self.finished = False

    def start(self):
        self._time_started = time.time()
        self._queue_thread.start()
        if self.duration > 0:
            self.log.info("duration {0} seconds".format(self.duration))
            # will execute FINISH after N seconds
            self._thread_timer.start()
            self.log.info("finish timer started")

    def _read_temperature_and_humidity(self, stop_event):
        RUN = True
        while RUN and not stop_event.wait(self.delay):
            data = self.sensor.readline()[:-2]  # the last bit gets rid of the new-line chars
            if data:
                datastr = data.decode("utf8")
                self.data = datastr
                self.log.info(datastr)

    def finish(self, stop_service=False):
        self.log.warning("stopping")
        if hasattr(self, "_thread_stopper"):
            self._thread_stopper.set()
            time.sleep(1)  # wait for thread to stop

        self.log.warning("   stopped ")
        self._flush_loggers()
        self.finished = True
        if stop_service:
            time.sleep(2)
            self.service_stop()

    def disp(self):
        pass

    def is_busy(self):
        return self._queue_thread.is_alive()  # is this the right way to check whether thread is running?

    def info(self):
        if self.is_busy():
            # NOTE: save to access thread variables? need lock or something?
            return str(self.data)
        else:
            return None

    def test(self):
        pass

    def cleanup(self):
        self.finish()
        if hasattr(self, "_queue_thread"):
            del self._queue_thread


if __name__ == "__main__":
    if len(sys.argv) > 1:
        ser = sys.argv[1]
    else:
        ser = "default"
    s = THUA(serializer=ser)
    s.bind("tcp://0.0.0.0:{0}".format(THUA.SERVICE_PORT))
    s.run()
