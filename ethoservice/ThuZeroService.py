#!/usr/bin/env python
import threading
from .ZeroService import BaseZeroService
import zerorpc
import time
import threading
try:
    import Adafruit_DHT
except Exception as e:
    print("IGNORE IF RUN ON HEAD")
    print(e)


class THU(BaseZeroService):
    '''
    Temperature and Humidity sensor. connect to rpi via arduino. or directly to rpi if possible
    try DHT22 and https://github.com/adafruit/Adafruit_Python_DHT
    '''
    LOGGING_PORT = 1446
    SERVICE_PORT = 4246
    SERVICE_NAME = 'THU'

    def setup(self, pin, delay, duration):
        self.sensor = Adafruit_DHT.DHT22  # type of temperature sensor - make this arg?
        self.pin = pin  # data pin
        self.delay = delay  # delay between reads
        self.duration = duration  # total duration of experiments

        # initialize
        self.temperature = None
        self.humidity = None

        # setup up thread
        self._thread_timer = threading.Timer(self.duration, self.finish, kwargs={'stop_service':True})
        self._thread_stopper = threading.Event()  # not sure this is required here - but probably does not hurt
        self._queue_thread = threading.Thread(
            target=self._read_temperature_and_humidity, args=(self._thread_stopper,))
        self.MOVEFILES_ON_FINISH = True

    def start(self):
        self._time_started = time.time()
        self._queue_thread.start()
        if self.duration > 0:
            self.log.info('duration {0} seconds'.format(self.duration))
            # will execute FINISH after N seconds
            self._thread_timer.start()
            self.log.info('finish timer started')

    def _read_temperature_and_humidity(self, stop_event):
        RUN = True
        while RUN and not stop_event.wait(self.delay):
            self.humidity, self.temperature = Adafruit_DHT.read_retry(self.sensor, self.pin)
            self.log.info('temperature,{0:0.1f},C;humidity,{1:0.1f},%'.format(self.temperature, self.humidity))

    def finish(self, stop_service=False):
        self.log.warning('stopping')
        if hasattr(self, '_thread_stopper'):
            self._thread_stopper.set()
            time.sleep(1)  # wait for thread to stop
        # clean up code here
        self.log.warning(self.MOVEFILES_ON_FINISH)
        if self.MOVEFILES_ON_FINISH:
            files_to_move = list()
            self.log.warning(self.logfilename)
            if self.logfilename is not None:
                files_to_move.append(self.logfilename)
            self.log.warning(files_to_move)            
            self._movefiles(files_to_move, self.targetpath)

        self.log.warning('   stopped ')
        self._flush_loggers()
        if stop_service:
            time.sleep(2)
            self.service_stop()

    def disp(self):
        pass

    def is_busy(self):
        return self._queue_thread.is_alive()  # is this the right why to check whether thread is running?

    def info(self):
        if self.is_busy():
            # NOTE: save to access thread variables? need lock or something?
            return 'temperature,{0:0.1f},C;humidity,{1:0.1f},%'.format(self.temperature, self.humidity)
        else:
            return None

    def test(self):
        pass

    def cleanup(self):
        self.finish()
        if hasattr(self, '_queue_thread'):
            del(self._queue_thread)


if __name__ == '__main__':
    s = zerorpc.Server(THU())
    s.bind("tcp://0.0.0.0:{0}".format(THU.SERVICE_PORT))
    s.run()
