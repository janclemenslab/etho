import gpiozero
from itertools import repeat, cycle, chain
from .log_exceptions import for_all_methods, log_exceptions
import logging

@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class Delay_PWMLED(gpiozero.PWMLED):

    def __init__(self, pin=None, active_high=True, initial_value=0, frequency=100, pin_factory=None):
        super().__init__(pin, active_high, initial_value, frequency, pin_factory)

    
    def blink(self, on_time=1, off_time=1, initial_delay=0, n=None, background=True):
        """
        Make the device turn on and off repeatedly.

        :param float on_time:
            Number of seconds on. Defaults to 1 second.

        :param float off_time:
            Number of seconds off. Defaults to 1 second.

        :param float initial_delay:
            Number of seconds to wait before starting to blink. Defaults to 0.

        :type n: int or None
        :param n:
            Number of times to blink; :data:`None` (the default) means forever.

        :param bool background:
            If :data:`True` (the default), start a background thread to
            continue blinking and return immediately. If :data:`False`, only
            return when the blink is finished (warning: the default value of
            *n* will result in this method never returning).
        """
        self._stop_blink()
        self._blink_thread = gpiozero.threads.GPIOThread(
            target=self._blink_device,
            args=(on_time, off_time, initial_delay, n)
        )
        self._blink_thread.start()
        if not background:
            self._blink_thread.join()
            self._blink_thread = None


    def _blink_device(
            self, on_time, off_time, initial_delay=0, n=1, fps=25):
        sequence = []
        sequence.append((1, on_time))
        sequence.append((0, off_time))
        sequence = (
                cycle(sequence) if n is None else
                chain.from_iterable(repeat(sequence, n))
                )
        if initial_delay > 0:  # prepend delay
            value, delay = (0, initial_delay)
            self._write(value)
            self._blink_thread.stopping.wait(delay)
        for value, delay in sequence:
            self._write(value)
            if self._blink_thread.stopping.wait(delay):
                break

