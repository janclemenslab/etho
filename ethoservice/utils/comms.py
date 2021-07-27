"""Communication primitives with a common interface
and a helper class for running tasks in independent processes."""
from multiprocessing import Process
import multiprocessing as mp
import time
import sys
import numpy as np
import ctypes
from typing import Optional, Any, Tuple
import multiprocessing.connection


class AbstractComms():

    def __init__(self) -> Tuple:
        self.qsize = 1
        self.duplex = False  # if True, both sender and receiver have send/get, 
                             # otherwise  sender has send and receiver has get
        self.sender, self.receiver = None, None
        
    def get(self, block: bool = True, timeout: Optional[float] = 0.001, empty_value: Any =None) -> Any:
        pass
    
    def send(self, data: Any, timeout: Optional[float] = 0.001):
        pass


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


from multiprocessing.sharedctypes import Value, Array
from ctypes import Structure, c_float, c_int, c_wchar_p
import ctypes

# class Struct(Structure):
#     @classmethod
#     def from_dict(cls, dict):
        
#         # _fields_ = [('x', c_double), ('y', c_double)]
#         return Struct

class SharedCType:

    def __init__(self, ctype):
        # ctype is one of https://docs.python.org/3.7/library/ctypes.html#fundamental-data-types
        # map ctypes to python types via dict:
        # type_map = {float: c_float, int: c_int, str: c_wchar_p, dict: Struct.from_dict, list: Array}
        if issubclass(ctype, Structure):
            self._shared_array = Array(ctype(), ctypes.sizeof(ctype))
        else:
            self._shared_array = Value(ctype())

        # shared lock
        self._lock = mp.Lock()
        self._stale = mp.RawValue('b', True)

    @property
    def stale(self):
        """Thread safe access to whether or not the current array values have been get-ed already."""
        with self._lock:
            return self._stale.value
    
    def poll(self):
        """Returns true if the array has been update since the last put."""
        return not self.stale

    def get(self, timeout=None, block=True):
        """Returns array values. Block is unsed and their for interface consistency with Queue."""
        with self._lock:
            self._stale.value = True
            return self._shared_array.value

    def put(self, data):
        """Update the values in the shared array."""
        if data is None:
            return

        with self._lock:
            self._shared_array.value = data
            self._stale.value = False

    def send(self, *args, **kwargs):
        return self.put(*args, **kwargs)

    def close(self):
        del(self)


class Faucet():
    """Wrapper for Pipe connection objects that exposes
    `get` function for common interface with Queues."""

    WHOAMI = 'pipe'

    def __init__(self, connection: multiprocessing.connection.Connection):
        """Wraps Connection object returned when calling Pipe and
        delegates function calls to have a common interface with the Queue.

        Args:
            connection (multiprocessing.connection.Connection): [description]
        """
        self.connection = connection
        self.qsize = 0

        # delegate function calls
        self.send = self.connection.send
        self.close = self.connection.close
        self.closed = self.connection.closed
    

    def get(self, block: bool = True, timeout: Optional[float] = 0.001, empty_value: Any =None) -> Any:
        """Mimics the logic of the `Queue.get`.

        Args:
            block (bool, optional): [description]. Defaults to True.
            timeout (float, optional): [description]. Defaults to 0.001.
            empty_value ([type], optional): [description]. Defaults to None.

        Returns:
            [type]: [description]
        """
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
    receiver = sender
    return sender, receiver


def NumpyArray(shape=(1,), ctype=ctypes.c_double):
    sender = SharedNumpyArray(shape, ctype)
    sender.send = sender.put
    receiver = sender
    return sender, receiver
