#!/usr/bin/env python
# required imports
from .ZeroService import BaseZeroService  # import super class
import zerorpc # for starting service in `main()`
import time    # for timer
import threading
import sys
from .utils.log_exceptions import for_all_methods, log_exceptions
from .utils import dlp_runners
import logging
import defopt
from typing import Optional, Any
import pycrafter4500
import os

from pybmt.callback.threshold_callback import ThresholdCallback
from pybmt.callback.broadcast_callback import BroadcastCallback
from pybmt.fictrac.service import FicTracDriver
from pybmt.fictrac.state import FicTracState
import mmap
import ctypes


# decorate all methods in the class so that exceptions are properly logged
@for_all_methods(log_exceptions(logging.getLogger(__name__)))
class DLP(BaseZeroService):

    LOGGING_PORT = 1453  # set this to range 1420-1460
    SERVICE_PORT = 4253  # last two digits match logging port - but start with "42" instead of "14"
    SERVICE_NAME = "DLP" # short, uppercase, 3-letter ID of the service (must equal class name)

    def setup(self, duration, params=None):
        self._time_started = None
        self.duration = float(duration)
        # APPLICATION SPECIFIC SETUP CODE HERE
        if params is None or 'runner' not in params:
            self.runner = dlp_runners.runners['default']
        else:
            self.runner = dlp_runners.runners[params['runner']]

        self.tracDrv = FicTracDriver.as_client(remote_endpoint_url="localhost:5556")

        # 180 hz, 7 bit depth, white
        pycrafter4500.pattern_mode(num_pats=3,
                                fps=180,
                                bit_depth=7,
                                led_color=0b111,  # BGR flags                 
                                )

        # background jobs should be run and controlled via a thread
        # threads can be stopped by setting an event: `_thread_stopper.set()`
        self._thread_stopper = threading.Event()
        # and/or via a timer
        if self.duration>0:
            self._thread_timer = threading.Timer(self.duration, self.finish, kwargs={'stop_service':True})
        #
        self._worker_thread = threading.Thread(target=self._worker, args=(self._thread_stopper,))

    def start(self):
        self._time_started = time.time()

        # background jobs should be run and controlled via a thread
        self._worker_thread.start()
        self.log.info('started')
        if hasattr(self, '_thread_timer'):
             self.log.info('duration {0} seconds'.format(self.duration))
             self._thread_timer.start()
             self.log.info('finish timer started')

    def _worker(self, stop_event): 
        self.runner(self.log, self.tracDrv)

    # def _workerX(self, stop_event):
    #     # need to import here since psychopy can only work in the thread where it's imported
    #     import pyglet.app #
    #     from psychopy import visual, event, core
    #     from psychopy.visual.windowframepack import ProjectorFramePacker
    #     win = visual.Window([800,800], monitor="testMonitor", screen=1, units="deg", fullscr=True, useFBO = True)
    #     framePacker = ProjectorFramePacker(win)

    #     rect = visual.Rect(win, width=5, height=5, autoLog=None, units='', lineWidth=1.5, lineColor=None,
    #                         lineColorSpace='rgb', fillColor=[0.0,0.0,0.0], fillColorSpace='rgb', pos=(-10, 0), size=None, ori=0.0, 
    #                         opacity=1.0, contrast=1.0, depth=0, interpolate=True, name=None, autoDraw=False)

    #     cnt = 0
    #     period = 100
    #     RUN = True
    #     WHITE = True
    #     self.log.info('run')
    #     while RUN:
    #         cnt +=1
    #         if WHITE:
    #             rect.fillColor = [1.0, 1.0, 1.0]  # advance phase by 0.05 of a cycle
    #         else:
    #             rect.fillColor = [-1.0, -1.0, -1.0]  # advance phase by 0.05 of a cycle
    #         if cnt % period == 0:
    #             WHITE = not WHITE
    #             rect.pos = rect.pos + [0.01, 0]
    #             if self.tracDrv is not None:
    #                 print(self.tracDrv._read_message())

    #         rect.draw()
    #         win.flip()

    #         if len(event.getKeys())>0:
    #             break
    #         event.clearEvents()
        
    #     win.close()
    #     core.quit()

    def finish(self, stop_service=False):
        self.log.warning('stopping')
        # stop thread if necessary
        if hasattr(self, '_thread_stopper'):
            self._thread_stopper.set()
        if hasattr(self, '_thread_timer'):
            self._thread_timer.cancel()
        # clean up code here

        self.log.warning('   stopped ')
        # mode log file and savefilename
        if stop_service:
            time.sleep(2)
            self.service_stop()

    def disp(self):
        pass

    def is_busy(self):
        return True # should return True/False

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



def cli(serializer: str = 'default', port: Optional[str] = None):
    if port == None:
        port = DLP.SERVICE_PORT
    s = DLP(serializer=serializer)
    s.bind("tcp://0.0.0.0:{0}".format(port))  # broadcast on all IPs
    print('running DLPZeroService')
    s.run()
    print('done')
    

if __name__ == '__main__':
    defopt.run(cli)
