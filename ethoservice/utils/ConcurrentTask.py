from multiprocessing import Process
import multiprocessing as mp
import time
import sys
import numpy as np
import ctypes


class SharedNumpyArray:
    """Class for sharing a numpy array between processes.

    Contains functions for synchronized read/write access and a staleness indicator.
    """

    WHOAMI = 'array'

    def __init__(self, shape, ctype=ctypes.c_double):
        """[summary]

        Args:
            shape (tuple/list-like): [description]
            ctype ([type], optional): Data type of the numpy array. Defaults to ctypes.c_double (is np.float64).
        """
        self.shape = shape  # need to know shape before hand since the array has to be initialized at init
        self.qsize = 0  # for interface compatibility with Queues and Pipes
        self.first = True
        # indicator whether the current array values are "fresh"
        # stale is set to False upon `put` and to True on `get`
        self._stale = mp.RawValue('b', True)
        # add one more RawValue for system_time?

        # common lock to sync read/write access
        self._lock = mp.Lock()
        # will be the np representation of the base array - need to convert from base array
        # on both ends for updates to propagate - see _asnp()
        self._shared_array = None  # initialize with None to mark as not yet created

        # add one more RawValue for system_time?
        with self._lock:
            # create array in shared memory segment
            self._shared_array_base = mp.RawArray(
                ctype, int(np.prod(self.shape)))

    @property
    def stale(self):
        """Thread safe access to whether or not the current array values have been get-ed already."""
        with self._lock:
            return self._stale.value

    def _asnp(self):
        if self._shared_array is None:
            # need to get the np array from the underlying base array on both ends, but
            # only once - we detect first access by setting _array_base=None at init.
            # convert to numpy array vie ctypeslib
            self._shared_array = np.ctypeslib.as_array(self._shared_array_base)
            # do a reshape for correct shape
            # Returns a masked array containing the same data, but with a new shape.
            # The result is a view on the original array
            self._shared_array = self._shared_array.reshape(self.shape)
        return self._shared_array

    def poll(self):
        """Returns true if the array has been update since the last put."""
        return not self.stale

    def get(self, timeout=None, block=True):
        """Returns array values. Block is unsed and their for interface consistency with Queue."""
        with self._lock:
            self._stale.value = True
            return self._asnp()

    def put(self, data):
        """Update the values in the shared array."""
        if data is None:
            return

        with self._lock:
            self._shared_array = self._asnp()
            self._shared_array[:] = data[0][:]
            self._stale.value = False

    def close(self):
        del(self)


class Faucet():

    WHOAMI = 'pipe'

    def __init__(self, connection):
        self.connection = connection
        self.qsize = 0

        # automate this
        self.send = self.connection.send
        self.close = self.connection.close
        self.closed = self.connection.closed
        self.__del__ = self.connection.__del__

    def get(self, block=True, timeout=0.001, empty_value=None):
        if block:
            timeout = None
        if self.connection.poll(timeout):
            return self.connection.recv()
        else:
            return empty_value


def Pipe(duplex=False):
    receiver, sender = mp.Pipe(duplex)
    receiver = Faucet(receiver)
    sender = Faucet(sender)
    return sender, receiver

def Queue(maxsize=0):
    sender = mp.Queue(maxsize)
    sender.send = sender.put
    sender.WHOAMI = 'queue'
    receiver = sender

    return sender, receiver


def NumpyArray(shape=(1,), ctype=ctypes.c_double):
    sender = SharedNumpyArray(shape, ctype)
    sender.send = sender.put
    receiver = sender
    return sender, receiver


class ConcurrentTask():
    """
    - tasks should stop when being sent None
    TODO
    - maybe the tasks should implement a defined interface/communication protocol (sending `None` stops the task etc., START and STOP s)
    - the task objects should provide information about appropriate communication (e.g. `taskstopsignals`) and maybe even the communication channel (pipe vs queue). Maybe implement abstraction with a common interface for pipe, queue, zmq??
    """

    def __init__(self, task, taskinitargs=[], comms='queue', taskstopsignal=None, comms_kwargs={}, task_kwargs={}):
        """ [summary]

        Args:
            task ([type]): [description]
            taskinitargs (list, optional): [description]. Defaults to [].
            comms (str, optional): Use a pipe if you want speed and don't mind loosing data (displaying data)
                                   or if you want to ensure you are always assessing fresh data (realtime feedback).
                                   Queue are great when data loss is unacceptable (saving data).
                                   Defaults to 'queue'.
            taskstopsignal ([type], optional): [description]. Defaults to None.
            comms_kwargs={}
            task_kwargs={}
        Raises:
            ValueError: [description]
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
                f'Unknown comms type {comms} - allowed values are "pipe", "queue", "array"')

        self.send = self._sender.send

        # prepend queue, i.e. sink end of pipe or end of queue
        taskinitargs = list(taskinitargs)
        taskinitargs.insert(0, self._receiver)

        self._process = Process(target=task, args=tuple(taskinitargs), kwargs=task_kwargs)
        self.start = self._process.start

    def finish(self, verbose=False, sleepduration=1, sleepcycletimeout=5, maxsleepcycles=100000000):
        if self.comms == "queue":
            sleepcounter = 0
            queuesize = self._sender.qsize()
            queuehasnotchangedcounter = 0
            while queuesize > 0 and sleepcounter < maxsleepcycles and queuehasnotchangedcounter < sleepcycletimeout:
                time.sleep(sleepduration)
                queuesize = self._sender.qsize()
                sleepcounter += 1
                queuehasnotchanged = (queuesize == self._sender.qsize())
                if queuehasnotchanged:
                    queuehasnotchangedcounter += 1
                else:
                    queuehasnotchangedcounter = 0
                if verbose:
                    sys.stdout.write('\r   waiting {} seconds for {} frames to self.'.format(
                        sleepcounter, self._sender.qsize()))  # frame interval in ms

    def close(self):
        self.send(self.taskstopsignal)
        time.sleep(0.5)
        try:
            self._process.terminate()
        except AttributeError:
            pass
        time.sleep(0.5)
        self._sender.close()
        del self._process
        del self._sender
        if self._receiver is not None:
            self._receiver.close()
            del self._receiver
