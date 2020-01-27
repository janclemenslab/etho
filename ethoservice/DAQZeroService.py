#!/usr/bin/env python
from .ZeroService import BaseZeroService  # import super class
import time     # for timer
import threading
import os
import sys
import copy
import yaml
from typing import Iterable, Sequence
from .utils.log_exceptions import for_all_methods, log_exceptions
import logging
try:
    from .utils.IOTask import *
except ImportError as e:
    print("IGNORE IF RUN ON HEAD")
    print(e)


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class DAQ(BaseZeroService):
    '''Bundles and synchronizes analog/digital input and output tasks.'''

    LOGGING_PORT = 1449   # set this to range 1420-1460
    SERVICE_PORT = 4249   # last to digits match logging port - but start with "42" instead of "14"
    SERVICE_NAME = "DAQ"  # short, uppercase, 3-letter ID of the service (equals class name)

    # def setup(self, savefilename, duration, analog_chans_out=["ao0", "ao1"], analog_chans_in=["ai2", "ai3", "ai0"]):
    def setup(self, savefilename: str=None, play_order: Iterable=None, playlist_info=None,
              duration: float=-1, fs: int=10000, display=False, realtime=False, 
              nb_inputsamples_per_cycle=None,
              analog_chans_out: Sequence=None, analog_chans_in: Sequence=['ai0'], digital_chans_out: Sequence=None,
              analog_data_out: Sequence=None, digital_data_out: Sequence=None, metadata={}):
        """[summary]
        
        Args:
            savefilename (str, optional): [description]. Defaults to None.
            play_order (Iterable, optional): [description]. Defaults to None.
            playlist_info ([type], optional): [description]. Defaults to None.
            duration (float, optional): [description]. Defaults to -1.
            fs (int, optional): [description]. Defaults to 10000.
            display (bool, optional): [description]. Defaults to False.
            realtime (bool, optional): [description]. Defaults to False.
            nb_inputsamples_per_cycle ([type], optional): [description]. Defaults to None.
            analog_chans_out (Sequence, optional): [description]. Defaults to None.
            analog_chans_in (Sequence, optional): [description]. Defaults to ['ai0'].
            digital_chans_out (Sequence, optional): [description]. Defaults to None.
            analog_data_out (Sequence, optional): [description]. Defaults to None.
            digital_data_out (Sequence, optional): [description]. Defaults to None.
            metadata (dict, optional): [description]. Defaults to {}.
        
        Raises:
            ValueError: [description]
        """
        self._time_started = None
        self.duration = duration
        self.savefilename = savefilename
        # APPLICATION SPECIFIC SETUP CODE HERE
        self.analog_chans_out = analog_chans_out
        self.analog_chans_in = analog_chans_in
        self.digital_chans_out = digital_chans_out

        # ANALOG OUTPUT
        if self.analog_chans_out:
            self.taskAO = IOTask(cha_name=self.analog_chans_out, rate=fs)
            if analog_data_out[0].shape[-1] is not len(self.analog_chans_out):
                raise ValueError(f'Number of analog output channels ({len(self.analog_chans_out)}) does not match the number of channels in the sound files ({analog_data_out[0].shape[-1]}).')
            play_order_new = copy.deepcopy(play_order)
            self.taskAO.data_gen = data_playlist(analog_data_out, play_order_new, playlist_info, self.log , name='AO')
            self.taskAO.CfgDigEdgeStartTrig("ai/StartTrigger", DAQmx_Val_Rising)
            print(self.taskAO)
        # DIGITAL OUTPUT
        if self.digital_chans_out:
            self.taskDO = IOTask(cha_name=self.digital_chans_out, rate=fs)
            play_order_new = copy.deepcopy(play_order)
            self.taskDO.data_gen = data_playlist(digital_data_out, play_order_new, name='DO')
            self.taskDO.CfgDigEdgeStartTrig("ai/StartTrigger", DAQmx_Val_Rising)
            print(self.taskDO)
        # ANALOG INPUT
        if self.analog_chans_in:
            self.taskAI = IOTask(cha_name=self.analog_chans_in, rate=fs, 
                                 nb_inputsamples_per_cycle=nb_inputsamples_per_cycle)
            self.taskAI.data_rec = []
            if self.savefilename is not None:  # save
                os.makedirs(os.path.dirname(self.savefilename), exist_ok=True)
                attrs = {'rate': fs, 'analog_chans_in': analog_chans_in, **metadata}
                self.save_task = ConcurrentTask(task=save, comms="queue", taskinitargs=[self.savefilename, len(self.analog_chans_in), attrs])
                self.taskAI.data_rec.append(self.save_task)
            if display:
                self.disp_task = ConcurrentTask(task=plot_fast, taskinitargs=[display], comms="pipe")
                self.taskAI.data_rec.append(self.disp_task)
            if realtime:
                self.proc_task = ConcurrentTask(task=process_analog, comms="array", maxsize=(100, 18))
                self.taskAI.data_rec.append(self.proc_task)
            print(self.taskAI)

        if self.duration > 0:  # if zero, will stop when nothing is to be outputted
            self._thread_timer = threading.Timer(self.duration, self.finish, kwargs={'stop_service': True})

    def start(self):
        self._time_started = time.time()

        for task in self.taskAI.data_rec:
            task.start()

        # Arm the output tasks - won't start until the AI start is triggered
        if self.analog_chans_out:
            self.taskAO.StartTask()

        if self.digital_chans_out:
            self.taskDO.StartTask()

        # Start the AI task - generates AI start trigger and triggers the output tasks
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

        # stop tasks and properly close callbacks (e.g. flush data to disk and close file)
        if hasattr(self, 'digital_chans_out') and self.digital_chans_out:
            try:
                self.taskDO.StopTask()
            except GenStoppedToPreventRegenOfOldSamplesError as e:
                pass
            print('\n   stoppedDO')
            self.taskDO.stop()

        if hasattr(self, 'analog_chans_out') and self.analog_chans_out:
            try:
                self.taskAO.StopTask()
            except GenStoppedToPreventRegenOfOldSamplesError as e:
                pass
            print('\n   stoppedAO')
            self.taskAO.stop()

        # stop this last since this is the trigger/master clock - NO! AI is...
        self.taskAI.StopTask()
        print('\n   stoppedAI')
        self.taskAI.stop()
        # maybe this won't be necessary
        for task in self.taskAI.data_rec:
            try:
                task.close()
            except Exception as e:
                pass  # print(e)

        if self.analog_chans_out:
            self.taskAO.ClearTask()

        if self.digital_chans_out:
            self.taskDO.ClearTask()
        self.taskAI.ClearTask()

        self.log.warning('   stopped ')
        if stop_service:
            time.sleep(0.5)
            self.service_stop()

    def disp(self):
        pass

    def is_busy(self, ai=True, ao=True):
        taskCheckFailed = False

        taskIsDoneAI = daq.c_ulong()
        if self.analog_chans_out:
            taskIsDoneAO = daq.c_ulong()
        if ai:
            try:
                self.taskAI.IsTaskDone(taskIsDoneAI)
            except daq.InvalidTaskError as e:
                taskCheckFailed = True
        else:
            taskIsDoneAI = 0
        if ao and self.analog_chans_out:
            try:
                self.taskAO.IsTaskDone(taskIsDoneAO)
            except daq.InvalidTaskError as e:
                taskCheckFailed = True
        else:
            taskIsDoneAO = 0

        return not bool(taskIsDoneAI) and not bool(taskIsDoneAO) and not taskCheckFailed

    def test(self):
        return True

    def cleanup(self):
        self.finish()
        return True

    def info(self):
        if self.is_busy():
            pass  # your code here
        else:
            return None


if __name__ == '__main__':
    if len(sys.argv) > 1:
        ser = sys.argv[1]
    else:
        ser = 'default'
    s = DAQ(serializer=ser)  # expose class via zerorpc
    s.bind("tcp://0.0.0.0:{0}".format(DAQ.SERVICE_PORT))  # broadcast on all IPs
    s.run()
