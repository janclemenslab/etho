#!/usr/bin/env python
# required imports
from .ZeroService import BaseZeroService  # import super class
import zerorpc  # for starting service in `main()`
import time     # for timer
import threading
try:
    from .utils.IOTask import *
    from .utils.daqtools import *
except Exception as e:
    print("IGNORE IF RUN ON HEAD")
    print(e)

from itertools import cycle


class DAQ(BaseZeroService):

    LOGGING_PORT = 1449   # set this to range 1420-1460
    SERVICE_PORT = 4249   # last to digits match logging port - but start with "42" instead of "14"
    SERVICE_NAME = "DAQ"  # short, uppercase, 3-letter ID of the service (equals class name)

    # def setup(self, savefilename, duration, channels_out=["ao0", "ao1"], channels_in=["ai2", "ai3", "ai0"]):
    def setup(self, savefilename, sounds, playlist, play_order, duration, fs):
        self._time_started = None
        self.duration = duration
        self.savefilename = savefilename
        # APPLICATION SPECIFIC SETUP CODE HERE
        self.channels_out = ["ao0", "ao1"]
        self.channels_in = ["ai0"]

        self.taskAO = IOTask(cha_name=self.channels_out)

        # make play_order endless (circular list)
        play_order_loop = cycle(play_order)

        # `sounds` is a python-list of sounds saved as lists (because of 0rpc) - make a list of nparrays
        np_sounds = list()
        for sound in sounds:
            np_sounds.append(np.array(sound, dtype=np.float64))
        del sounds

        self.taskAO.data_gen = data_playlist(np_sounds, play_order_loop)  # generator function that yields data upon request
        # self.taskAO.data_gen = data_sine(channels=2)  # generator function that yields data upon request
        # Connect AO start to AI start
        self.taskAO.CfgDigEdgeStartTrig("ai/StartTrigger", DAQmx_Val_Rising)

        self.taskAI = IOTask(cha_name=self.channels_in)
        # self.disp_task = ConcurrentTask(task=plot, comms="pipe")
        if self.savefilename is not None: # scope + save
            os.makedirs(os.path.dirname(self.savefilename), exist_ok=True)
            self.save_task = ConcurrentTask(task=save, comms="queue", taskinitargs=[self.savefilename, len(self.channels_in)])
            self.taskAI.data_rec = [self.save_task]
            # self.taskAI.data_rec = [self.disp_task, self.save_task]
        else: # scope only
            self.taskAI.data_rec = []#[self.disp_task]

        # threads can be stopped by setting an event: `_thread_stopper.set()`
        # via a timer
        if self.duration>0:
            self._thread_timer = threading.Timer(self.duration, self.finish, kwargs={'stop_service':True})

    def start(self):
        self._time_started = time.time()

        # !!!DAQ - no worker thread required!!!
        # self.disp_task.start()
        if self.savefilename is not None: # scope + save
            self.save_task.start()


        # Arm the AO task
        # It won't start until the start trigger signal arrives from the AI task
        self.taskAO.StartTask()

        # Start the AI task
        # This generates the AI start trigger signal and triggers the AO task
        self.taskAI.StartTask()

        self.log.info('started')
        if hasattr(self, '_thread_timer'):
             self.log.info('duration {0} seconds'.format(self.duration))
             self._thread_timer.start()
             self.log.info('finish timer started')

    def finish(self, stop_service=False):
        self.log.warning('stopping')
        # stop thread if necessary
        if hasattr(self, '_thread_stopper'):
            self._thread_stopper.set()
        if hasattr(self, '_thread_timer'):
            self._thread_timer.cancel()
        # clean up code here

        # !!! DAQ !!!
            # stop tasks and properly close callbacks (e.g. flush data to disk and close file)
        self.taskAO.StopTask()
        print('\n   stoppedAO')
        self.taskAO.stop()
        self.taskAI.StopTask()
        print('\n   stoppedAI')
        self.taskAI.stop()

        try:
            self.disp_task.close()
        except:
            pass
        if self.savefilename is not None:
            try:
                self.save_task.close()
            except:
                pass

        self.taskAO.ClearTask()
        self.taskAI.ClearTask()

        self.log.warning('   stopped ')
        if stop_service:
            time.sleep(2)
            self.service_stop()

    def disp(self):
        pass

    def is_busy(self):
        taskIsDoneAI = daq.c_ulong()
        taskIsDoneAO = daq.c_ulong()
        self.taskAI.IsTaskDone(taskIsDoneAI)
        self.taskAO.IsTaskDone(taskIsDoneAO)
        return not bool(taskIsDoneAI) and not bool(taskIsDoneAO)

    def test(self):
        return True

    def cleanup(self):
        self.finish()
        # your code here
        return True

    def info(self):
        if self.is_busy():
            pass  # your code here
        else:
            return None


if __name__ == '__main__':
    s = zerorpc.Server(DAQ())  # expose class via zerorpc
    s.bind("tcp://0.0.0.0:{0}".format(DAQ.SERVICE_PORT))  # broadcast on all IPs
    s.run()
