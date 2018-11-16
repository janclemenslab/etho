#!/usr/bin/env python
import threading
from .ZeroService import BaseZeroService
import zerorpc
import time
from datetime import datetime
import sys

try:
    import gpiozero
except Exception as e:
    print("IGNORE IF RUN ON HEAD")
    print(e)


class OPT(BaseZeroService):

    LOGGING_PORT = 1452
    SERVICE_PORT = 4252
    SERVICE_NAME = 'OPT'

    def setup(self, pin, duration, LED_blinkinterval, LED_blinkduration):
        self.pin = int(pin)  # data pin
        self.duration =float(duration)  # total duration of experiments
        self.LED_blinkinterval = float(LED_blinkinterval)
        self.LED_blinkduration = float(LED_blinkduration)
        self.blinkpause = self.LED_blinkinterval-self.LED_blinkduration
        self.LED = gpiozero.LED(self.pin)

        self._thread_stopper = threading.Event()
        self._thread_timer = threading.Timer(self.duration, self.finish, kwargs={'stop_service':True})
        self._worker_thread = threading.Thread(target=self._worker, args=(self._thread_stopper,))

    def start(self):
        self._time_started = time.time()
        # self.LED.blink(on_time=self.LED_blinkduration, off_time=self.LED_blinkpause, n=10)

        # background jobs should be run and controlled via a thread
        self._worker_thread.start()

        if self.duration > 0:
            self.log.info('duration {0} seconds'.format(self.duration))
            # will execute FINISH after N seconds
            self._thread_timer.start()
            self.log.info('finish timer started')

    def _worker(self, stop_event):
        # schedule next execution
        if not stop_event.is_set():
            threading.Timer(self.LED_blinkinterval, self._worker, [stop_event]).start()
       # turn on LED
        self.LED.blink(on_time=self.LED_blinkduration, off_time=0, n=1)
        self.log.info("blinked")

    def finish(self, stop_service=False):
        self._turn_off() # turn LED of at finish
        self.log.warning('stopping')
        if hasattr(self, '_thread_stopper'):
            self._thread_stopper.set()
        if hasattr(self, '_thread_timer'):
            self._thread_timer.cancel()
        self._turn_off()
        self.log.warning('   stopped ')
        if self.MOVEFILES_ON_FINISH:
            files_to_move = list()
            if self.logfilename is not None:
                files_to_move.append(self.logfilename)
            self._movefiles(files_to_move, self.target)

        if stop_service:
            self.service_stop()

    def _turn_on(self):
        self.relay = gpiozero.LED(self.pin)

    def _turn_off(self):
        if self.relay:
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
    s = OPT(serializer=sys)
    s.bind("tcp://0.0.0.0:{0}".format(OPT.SERVICE_PORT))
    s.run()
