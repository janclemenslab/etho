"""Communication primitives with a common interface
and a helper class for running tasks in independent processes."""
from multiprocessing import Process
import multiprocessing as mp
import time
import sys
import numpy as np
from typing import Optional, Any
import multiprocessing.connection
from .comms import Pipe, Queue, NumpyArray


class ConcurrentTask():
    """Helper class for running tasks in independent
    processes with communication tools attached."""

    def __init__(self, task, task_kwargs={}, comms='queue', comms_kwargs={}, taskstopsignal=None):
        """ [summary]

        Args:
            task ([type]): First arg to task must be the end of the comms and is provided via `args`.
            task_kwargs={}
            comms (str, optional): Use a pipe if you want speed and don't mind loosing data (displaying data)
                                   or if you want to ensure you are always assessing fresh data (realtime feedback).
                                   Queue are great when data loss is unacceptable (saving data).
                                   Defaults to 'queue'.
            comms_kwargs={}
            taskstopsignal ([type], optional): [description]. Defaults to None.
        Raises:
            ValueError: for unknown comms
        """
        self.comms = comms
        self.taskstopsignal = taskstopsignal
        if self.comms == "pipe":
            self._sender, self._receiver = Pipe(**comms_kwargs)
        elif self.comms == "queue":
            self._sender, self._receiver = Queue(**comms_kwargs)
        elif self.comms == "array":
            self._sender, self._receiver = NumpyArray(**comms_kwargs)
        else:
            raise ValueError(
                f'Unknown comms {comms} - allowed values are "pipe", "queue", "array"')

        # delegate send calls from sender
        self.send = self._sender.send

        self._process = Process(target=task, args=(self._receiver,), kwargs=task_kwargs)
        self.start = self._process.start

    def finish(self, verbose: bool = False, sleepduration: float = 1,
               sleepcycletimeout: int = 5, maxsleepcycles: int = 100000000):
        if self.comms == "queue":
            sleepcounter = 0
            try:
                queuesize = self._sender.qsize()
            except NotImplementedError:  # catch python bug on OSX
                return

            queuehasnotchangedcounter = 0
            while queuesize > 0 and sleepcounter < maxsleepcycles and queuehasnotchangedcounter < sleepcycletimeout:
                time.sleep(sleepduration)
                try:
                    queuesize = self._sender.qsize()
                except NotImplementedError:  # catch python bug on OSX
                    break
                sleepcounter += 1
                queuehasnotchanged = (queuesize == self._sender.qsize())
                if queuehasnotchanged:
                    queuehasnotchangedcounter += 1
                else:
                    queuehasnotchangedcounter = 0
                if verbose:
                    sys.stdout.write('\r   waiting {} seconds for {} frames to self.'.format(
                        sleepcounter, self._sender.qsize()))  # frame interval in ms

    def close(self, sleep_time: float = 0.5):
        self.send(self.taskstopsignal)
        time.sleep(sleep_time)
        try:
            self._process.terminate()
        except AttributeError:
            pass
        time.sleep(sleep_time)
        self._sender.close()
        del self._process
        del self._sender
        if self._receiver is not None:
            self._receiver.close()
            del self._receiver
