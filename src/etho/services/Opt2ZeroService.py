#!/usr/bin/env python
import threading
from .ZeroService import BaseZeroService
from .utils.log_exceptions import for_all_methods, log_exceptions
import time
import logging
import sys

try:
    from .utils.delay_pwmled import Delay_PWMLED

    import_error = None
except ImportError as import_error:
    pass


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class OPT2(BaseZeroService):
    """Service for controlling multiple LEDs on raspberry pi.
    Uses [gpiozero](https://gpiozero.readthedocs.io) to control LEDs via (via GPIO pins).
    Individual LEDs can be controlled with independent temporal patterns and amplitudes."""

    LOGGING_PORT = 1452
    SERVICE_PORT = 4252
    SERVICE_NAME = "OPT2"

    def setup(self, pins, duration, blink_pers, blink_durs, blink_paus, blink_nums, blink_dels, blink_amps):
        """Setup up service

        Args:
            pins (List[int]): list of pin numbers
            duration ([type]): duration (in seconds) the service should run
            blink_pers ([type]): List [trials,] of trial periods (=durations)
            Lists [trials, number of pins]:
                blink_durs ([type]): [description]
                blink_paus ([type]): [description]
                blink_nums ([type]): [description]
                blink_dels ([type]): [description]
                blink_amps ([type]): [description]
        """
        if import_error is not None:
            raise import_error
        self.pins = [int(pin) for pin in pins]
        self.LEDs = [Delay_PWMLED(pin, initial_value=0, frequency=1000) for pin in self.pins]  # try to set frequency to 1000

        self.duration = float(duration)  # total duration of experiments
        self.LED_blinkinterval = blink_pers  # common clock for all pins - [trials,]

        # TODO: blinkduration/pause number should be each be a list of lists = trials x pins
        self.LED_blinkduration = blink_durs
        self.LED_blinkpause = blink_paus
        self.LED_blinknumber = blink_nums
        self.LED_blinkdelay = blink_dels
        self.LED_blinkamplitude = blink_amps
        # import pdb;pdb.set_trace()
        # compute in the event loop
        self._turn_off()  # make sure LED is off at start of experiment
        self.trial = -1
        self._thread_stopper = threading.Event()
        if duration > 0:
            self._thread_timer = threading.Timer(interval=self.duration, function=self.finish, kwargs={"stop_service": True})
        self._worker_thread = threading.Thread(target=self._worker, args=(self._thread_stopper,))
        for led in self.LEDs:
            led.blink(on_time=0.1, off_time=0, initial_delay=0, value=0, n=1)

    def start(self):
        self._time_started = time.time()

        # background jobs should be run and controlled via a thread
        self._worker_thread.start()

        if self.duration > 0:
            self.log.info("duration {0} seconds".format(self.duration))
            # will execute FINISH after N seconds
            self._thread_timer.start()
            self.log.info("finish timer started")

    def _worker(self, stop_event):
        # schedule next execution - waits self.LED_blinkinterval seconds before running the _worker function again
        if not stop_event.is_set():
            self.trial += 1
            threading.Timer(interval=self.LED_blinkinterval[self.trial], function=self._worker, args=[stop_event]).start()
            # turn on LED
            for led, dur, pau, num, amp, dely in zip(
                self.LEDs,
                self.LED_blinkduration[self.trial],
                self.LED_blinkpause[self.trial],
                self.LED_blinknumber[self.trial],
                self.LED_blinkamplitude[self.trial],
                self.LED_blinkdelay[self.trial],
            ):
                logging.info(f"{led}, {dur}, {pau}, {num}, {amp}, {dely}")
                # led.value = amp
                led.blink(on_time=dur, off_time=pau, initial_delay=dely, value=amp, n=num)

    def finish(self, stop_service=False):
        self.log.warning("stopping")
        if hasattr(self, "_thread_stopper"):
            self.log.info("stoppping thread stopper")
            self._thread_stopper.set()
        if hasattr(self, "_thread_timer"):
            self.log.info("cancelling thread timer")
            self._thread_timer.cancel()
            # self.log.info('joining thread timer')
            # self._thread_timer.join()
        # if hasattr(self, '_worker_thread'):
        #     self._worker_thread.join()
        self.log.info("turning off LED")
        self._turn_off()
        self.log.warning("   stopped ")
        if stop_service:
            self.service_stop()

    def _turn_on(self):
        """Turn LED on."""
        [led.on() for led in self.LEDs]

    def _turn_off(self):
        """Turn LED off."""
        [led.off() for led in self.LEDs]

    def disp(self):
        pass

    def is_busy(self):
        if any([led in self.LEDs]):
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
        if hasattr(self, "_queue_thread"):
            del self._queue_thread


if __name__ == "__main__":
    if len(sys.argv) > 1:
        ser = sys.argv[1]
    else:
        ser = "default"
    s = OPT2(serializer=ser)
    s.bind("tcp://0.0.0.0:{0}".format(s.SERVICE_PORT))
    s.run()
