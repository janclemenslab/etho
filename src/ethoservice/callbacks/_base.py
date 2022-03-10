import queue
import time

from ..utils.ConcurrentTask import ConcurrentTask
from . import register_callback

class BaseCallback():

    def __init__(self, data_source, poll_timeout: float = None, rate: float = 0,
                 **kwargs):
        self.data_source = data_source
        self.poll_timeout = poll_timeout
        self.RUN: bool = True
        self.CLEAN: bool = False
        self.rate = rate

    @classmethod
    def make_run(cls, *class_args, **class_kwargs):
        obj = cls(*class_args, **class_kwargs)
        obj.RUN = True
        obj._run()

    @classmethod
    def make_concurrent(cls, comms='queue', **kwargs):
        return ConcurrentTask(task=cls.make_run, comms=comms, **kwargs)

    def start(self):
        self.RUN = True
        self._run()

    def stop(self):
        self.RUN = False

    def _run(self):
        t1 = 0
        while self.RUN:
            t0 = time.time()
            try:
                data = self.data_source.get(timeout=self.poll_timeout)
            except AttributeError:
                if self.data_source.poll(timeout=self.poll_timeout):
                    data = self.data_source.recv()
                else:
                    continue
            except queue.Empty:
                continue

            if data is not None:
                if (t0-t1)>=self.rate:
                    self._loop(data)
                    t1 = t0
            else:
                self.stop()

        self._cleanup()

    def _loop(self, data):
        pass

    def _cleanup(self):
        # close everything created during __init__
        # Maybe flush data_source (e.g. process all items from the queue). Or keep it simple?
        self.CLEAN = True

    def __del__(self):
        self.stop()
        if not self.CLEAN:
            self._cleanup()

@register_callback
class BroadcastCallback():
    """broadcast data w/o acting on it."""
    pass
