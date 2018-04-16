#!/usr/bin/env python
import pygame
import numpy as np
import threading
import pandas as pd
from .ZeroService import BaseZeroService
import zerorpc
import time


class SND(BaseZeroService):

    LOGGING_PORT = 1443
    SERVICE_PORT = 4243
    SERVICE_NAME = "SND"

    def setup(self, np_sounds, playlist, playlist_items, duration, fs):
        self.duration = duration
        self._time_started = None
        self.log.info('duration {0} seconds'.format(self.duration))
        # init sound engine
        pygame.mixer.pre_init(frequency=fs, size=-16, channels=2, buffer=4096)
        pygame.mixer.init()
        pygame.init()  # init event system
        self.chan1 = pygame.mixer.find_channel()
        # Setup the end track event
        self.chan1.set_endevent(pygame.USEREVENT)

        self.log.info(pygame.mixer.get_init())
        # np arrays -> pygame sndarrays
        self.playlist = pd.read_msgpack(playlist)
        self.log.info('playlist')
        self.log.info(self.playlist.to_csv())
        self.soundlist = list()
        for np_sound in np_sounds:
            this_sound = pygame.sndarray.make_sound(np.array(np_sound))
            this_sound.set_volume(1.0)
            self.soundlist.append(this_sound)

        self.playlist_items = playlist_items
        self._thread_stopper = threading.Event()
        self._queue_thread = threading.Thread(
            target=self._queue_sounds, args=(self._thread_stopper,))
        self.MOVEFILES_ON_FINISH = True

    def start(self):
        self._time_started = time.time()
        self._queue_thread.start()
        # TODO: log playlist etc
        self.log.info('started')

    def _queue_next(self):
        if self.playlist_items:
            self.current_item = self.playlist_items.pop(0)  # return and remove first item on list
            self.chan1.queue(self.soundlist[self.current_item])

    def _queue_sounds(self, stop_event):
        RUN = True
        while RUN and not stop_event.wait(0.1):
            if self.chan1.get_queue() is None and self.playlist_items:
                self._queue_next()
                self.log.info(
                    self.playlist.iloc[self.current_item].to_csv().replace('\n',';'))
            if not self.playlist_items and not self.is_busy():
                self.log.warning('playlist empty and no playback running - stop queueing')
                RUN = False
        self.log.warning('playlist empty - stopping service')
        self.finish(stop_service=True)

    def finish(self, stop_service=False):
        self.log.warning('stopping playback')
        if hasattr(self, '_thread_stopper'):
            self._thread_stopper.set()

        if pygame.mixer.get_init():
            pygame.mixer.stop()
        self.log.warning('   stopped playback')
        self.log.warning(self.MOVEFILES_ON_FINISH)
        if self.MOVEFILES_ON_FINISH:
            files_to_move = list()
            self.log.warning(self.logfilename)
            if self.logfilename is not None:
                files_to_move.append(self.logfilename)
            self.log.warning(files_to_move)            
            self._movefiles(files_to_move, self.targetpath)
        self._flush_loggers()
        if stop_service:
            time.sleep(1)
            self.service_stop()

    def disp(self):
        pass

    def is_busy(self):
        return pygame.mixer.get_busy()

    def test(self):
        return True

    def cleanup(self):
        self.finish()
        if hasattr(self, '_queue_thread'):
            del(self._queue_thread)
        pygame.mixer.quit()
        return True

    def info(self):
        if self.is_busy():
            return self.playlist.iloc[self.current_item].to_msgpack()
        else:
            return None


if __name__ == '__main__':
    s = zerorpc.Server(SND())
    s.bind("tcp://0.0.0.0:{0}".format(SND.SERVICE_PORT))
    s.run()
