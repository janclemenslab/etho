#!/usr/bin/env python
# required imports
from .ZeroService import BaseZeroService  # import super class
import zerorpc  # for starting service in `main()`
import time     # for timer
import threading
import os
import sys

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
    def setup(self, savefilename, sounds, playlist, play_order, duration, fs, params):
        self._time_started = None
        self.duration = duration
        self.savefilename = savefilename
        # APPLICATION SPECIFIC SETUP CODE HERE
        self.channels_out = params['channels_out']  # ["ao0", "ao1"]#
        self.channels_in = params['channels_in']  # ["ai0"]#

        self.taskAO = IOTask(cha_name=self.channels_out)

        # `sounds` is a python-list of sounds saved as lists (because of 0rpc) - make a list of nparrays
        np_sounds = list()
        for sound in sounds:
            np_sounds.append(np.array(sound, dtype=np.float64))
        del sounds
        # TODO: check if channels in np_sounds[0].shape[-1] matches taskAO.nb_channels

        self.taskAO.data_gen = data_playlist(np_sounds, play_order)  # generator function that yields data upon request
        # Connect AO start to AI start
        self.taskAO.CfgDigEdgeStartTrig("ai/StartTrigger", DAQmx_Val_Rising)
        print(self.taskAO)
        # DIGITAL OUTPUT
        if 'digital_channels_out' in params:
            self.digital_channnels_out = params['digital_channels_out']
        else:
            self.digital_channnels_out = None
        if self.digital_channnels_out:
            self.taskDO = IOTask(cha_name=params['digital_channels_out'])#self.digital_channels_out)

            # get digital pattern from sounds - duplicate sounds, add next trigger at beginning of each sound
            np_triggers = list()
            for sound in np_sounds:
                this_trigger = np.zeros((sound.shape[0], self.taskDO.num_channels), dtype=np.uint8)
                # if len(np_triggers) == 0:
                #     this_trigger[:5, 0] = 1  # START on first
                if len(np_triggers) == len(np_sounds)-1:
                    this_trigger[-5:, 1] = 1  # STOP on last
                else:
                    this_trigger[:5, 2] = 1  # NEXT
                this_trigger[:5, 2] = 1  # NEXT
                np_triggers.append(this_trigger.astype(np.uint8))
            self.taskDO.data_gen = data_playlist(np_triggers, play_order)
            self.taskDO.CfgDigEdgeStartTrig("ai/StartTrigger", DAQmx_Val_Rising)
            print(self.taskDO)
        # ANALOG INPUT
        self.taskAI = IOTask(cha_name=self.channels_in)
        self.taskAI.data_rec = []
        if self.savefilename is not None:  #  save
            os.makedirs(os.path.dirname(self.savefilename), exist_ok=True)
            self.save_task = ConcurrentTask(task=save, comms="queue", taskinitargs=[self.savefilename, len(self.channels_in)])
            self.taskAI.data_rec.append(self.save_task)
        if 'display' in params and eval(params['display']):
            self.disp_task = ConcurrentTask(task=plot, taskinitargs=[len(self.channels_in)], comms="pipe")
            self.taskAI.data_rec.append(self.disp_task)
        print(self.taskAI)

        # threads can be stopped by setting an event: `_thread_stopper.set()`
        if self.duration > 0:
            self._thread_timer = threading.Timer(self.duration, self.finish, kwargs={'stop_service': True})

    def start(self):
        self._time_started = time.time()

        for task in self.taskAI.data_rec:
            task.start()

        # Arm the AO task
        # It won't start until the start trigger signal arrives from the AI task
        self.taskAO.StartTask()

        if self.digital_channnels_out:
            self.taskDO.StartTask()

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

        if hasattr(self, '_thread_stopper'):
            self._thread_stopper.set()
        if hasattr(self, '_thread_timer'):
            self._thread_timer.cancel()

        # !!! DAQ !!!
        # stop tasks and properly close callbacks (e.g. flush data to disk and close file)

        if self.digital_channnels_out:
            self.taskDO.StopTask()
            print('\n   stoppedDO')
            self.taskDO.stop()

        self.taskAI.StopTask()
        print('\n   stoppedAI')
        self.taskAI.stop()

        # stop this last since this is the trigger/master clock
        self.taskAO.StopTask()
        print('\n   stoppedAO')
        self.taskAO.stop()

        # # maybe this won't be necessary
        # for task in self.taskAI.data_rec:
        #     try:
        #         task.close()
        #     except Exception as e:
        #         pass  # print(e)

        self.taskAO.ClearTask()
        if self.digital_channnels_out:
            self.taskDO.ClearTask()
        self.taskAI.ClearTask()

        self.log.warning('   stopped ')
        if stop_service:
            time.sleep(1)
            self.service_stop()

    def disp(self):
        pass

    def is_busy(self):
        taskIsDoneAI = daq.c_ulong()
        taskIsDoneAO = daq.c_ulong()
        taskCheckFailed = False
        try:
            self.taskAI.IsTaskDone(taskIsDoneAI)
        except daq.InvalidTaskError as e:
            taskCheckFailed = True
        try:
            self.taskAO.IsTaskDone(taskIsDoneAO)
        except daq.InvalidTaskError as e:
            taskCheckFailed = True
        return not bool(taskIsDoneAI) and not bool(taskIsDoneAO) and not taskCheckFailed

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
    s = DAQ(serializer=sys.argv[1])  # expose class via zerorpc
    s.bind("tcp://0.0.0.0:{0}".format(DAQ.SERVICE_PORT))  # broadcast on all IPs
    s.run()
