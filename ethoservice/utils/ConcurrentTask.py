from multiprocessing import Process, Queue, Pipe
import time
import sys


class ConcurrentTask():
    """
    - tasks should stop when being sent None
    TODO
    - maybe the tasks should implement a defined interfact/communication protocol (sending `None` stops the task etc., START and STOP s)
    - the task objects should provide information about appropriate communication (e.g. `taskstopsignals`) and maybe even the communication channel (pipe vs queue). Maybe implement abstraction with a common interface for pipe, queue, zmq??
    """
    def __init__(self, task, taskinitargs=[], comms='queue', taskstopsignal=None):
        self.comms = comms
        self.taskstopsignal = taskstopsignal
        if self.comms == "pipe":
            self._sender, self._receiver = Pipe()
        elif self.comms == "queue":
            self._sender = Queue()
            self._receiver = self._sender

        taskinitargs.insert(0, self._receiver)  # prepend queue, i.e. sink end of pipe or end of queue
        self._process = Process(target=task, args=tuple(taskinitargs))

    def send(self, data):
        if self.comms == "queue":
            self._sender.put(data)
        elif self.comms == "pipe":
            self._sender.send(data)

    def start(self):
        self._process.start()

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
        self._process.terminate()
        time.sleep(0.5)
        self._sender.close()
        del self._process
        del self._sender
        if self._receiver is not None:
            self._receiver.close()
            del self._receiver
