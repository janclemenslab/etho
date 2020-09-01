#!/usr/bin/env python
import threading
from .ZeroService import BaseZeroService
import zerorpc
import time
import sys
from .utils.log_exceptions import for_all_methods, log_exceptions
import logging

HAS_RPI4_LIB = False
HAS_RPI3_LIB = False

try:
    import Adafruit_DHT
    HAS_RPI3_LIB = True
except Exception as e:
    print("IGNORE IF RUN ON HEAD")
    print(e)

try:
    import adafruit_dht, board
    HAS_RPI4_LIB = True
except Exception as e:
    print("IGNORE IF RUN ON HEAD")
    print(e)


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class THU_rpi4():

    def __init__(self, pin):
        self.pin = pin
        self.sensor = adafruit_dht.DHT22(getattr(board, f'D{self.pin}'))

    def read(self):
        try:
            temperature = self.sensor.temperature
            humidity = self.sensor.humidity
        except RuntimeError:
            temperature = None
            humidity = None
        return humidity, temperature


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class THU_rpi3():

    def __init__(self, pin):
        self.pin = pin
        self.sensor = Adafruit_DHT.DHT22

    def read(self):
        humidity, temperature = Adafruit_DHT.read_retry(self.sensor, self.pin)
        return humidity, temperature


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class THU(BaseZeroService):
    '''
    Temperature and Humidity sensor. connect to rpi via arduino. or directly to rpi if possible
    try DHT22 and https://github.com/adafruit/Adafruit_Python_DHT
    '''
    LOGGING_PORT = 1446
    SERVICE_PORT = 4246
    SERVICE_NAME = 'THU'

    def setup(self, pin, delay, duration):
        self.pin = pin  # data pin
        if HAS_RPI4_LIB:
            self.sensor = THU_rpi4(self.pin)  # type of temperature sensor - make this arg?
        elif HAS_RPI3_LIB:
            self.sensor = THU_rpi3(self.pin)  # type of temperature sensor - make this arg?
        else:
            raise ValueError('Oh no, could not dht lib')
        self.delay = int(delay)  # delay between reads
        self.duration = duration  # total duration of experiments

        # initialize
        self.temperature = None
        self.humidity = None

        # setup up thread
        self._thread_timer = threading.Timer(self.duration, self.finish, kwargs={'stop_service':True})
        self._thread_stopper = threading.Event()  # not sure this is required here - but probably does not hurt
        self._queue_thread = threading.Thread(
            target=self._read_temperature_and_humidity, args=(self._thread_stopper,))

    def start(self):
        self._time_started = time.time()
        self._queue_thread.start()
        if self.duration > 0:
            self.log.info(f'duration {self.duration} seconds')
            self.log.info(f'reading from pin {self.pin} every {self.delay} seconds.')
            # will execute FINISH after N seconds
            self._thread_timer.start()
            self.log.info('finish timer started')

    def _read_temperature_and_humidity(self, stop_event):
        RUN = True
        while RUN:
            try:
                # self.humidity, self.temperature = Adafruit_DHT.read_retry(self.sensor, self.pin)
                self.humidity, self.temperature = self.sensor.read()

                try:
                    self.log.info(f'temperature: {self.temperature:0.1f}; humidity: {self.humidity:0.1f}')
                except TypeError as e:
                    self.log.warning(f'invalid values for temperature ({self.temperature}C) or humidity ({self.humidity}%).')
                time.sleep(self.delay)
            except Exception as e:
                self.log.error(e)

    def finish(self, stop_service=False):
        self.log.warning('stopping')
        if hasattr(self, '_thread_stopper'):
            self._thread_stopper.set()
            time.sleep(1)  # wait for thread to stop

        self.log.warning('   stopped ')
        self._flush_loggers()
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
            try:
                return f'temperature,{self.temperature:0.1f},C;humidity,{self.humidity:0.1f}%'
            except TypeError as e:
                return f'invalid values for temperature ({self.temperature}C) or humidity ({self.humidity}%).'
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
    s = THU(serializer=ser)
    s.bind("tcp://0.0.0.0:{0}".format(THU.SERVICE_PORT))
    s.run()
