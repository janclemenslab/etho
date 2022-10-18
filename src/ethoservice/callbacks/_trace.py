"""[summary]

TODO: register for logging: `@for_all_methods(log_exceptions(logging.getLogger(__name__)))`
TODO: Make generic/abstract HDF writer
"""

import logging
from os import system
import numpy as np
from numpy.core.numeric import False_
import scipy.signal as ss

from ..utils.ConcurrentTask import ConcurrentTask
from . import register_callback
from typing import List
from ._base import BaseCallback

try:
    import tables
except ImportError:
    pass

try:
    import peakutils
except ImportError:
    pass


@register_callback
class PlotMPL(BaseCallback):

    FRIENDLY_NAME = 'plot'

    def __init__(self, data_source, *, poll_timeout=0.01,
                 channels_to_plot: List, nb_samples: int = 10_000,
                 **kwargs):
        super().__init__(data_source=data_source, poll_timeout=poll_timeout, **kwargs)
        self.channels_to_plot = channels_to_plot
        self.nb_channels = len(self.channels_to_plot)
        self.nb_samples = nb_samples

        import matplotlib
        matplotlib.use('tkagg')
        import matplotlib.pyplot as plt

        plt.ion()
        self.fig = plt.figure()
        self.fig.canvas.set_window_title('traces: daq')
        self.ax = [self.fig.add_subplot(self.nb_channels, 1, channel + 1) for channel in range(self.nb_channels)]
        plt.show(block=False)
        plt.draw()
        self.fig.canvas.start_event_loop(0.01)  # otherwise plot freezes after 3-4 iterations
        self.bgrd = [self.fig.canvas.copy_from_bbox(this_ax.bbox) for this_ax in self.ax]
        self.points = [ax.plot(np.arange(self.nb_samples), np.zeros((self.nb_samples, 1)), linewidth=0.4)[0] for ax in self.ax]  # init plot content
        [ax.set_ylim(-5, 5) for ax in self.ax]  # init plot content
        [ax.set_xlim(0, self.nb_samples) for ax in self.ax]  # init plot content
        for cnt, ax in enumerate(self.fig.get_axes()[::-1]):
            ax.label_outer()
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
        plt.show(block=False)
        plt.draw()

    def _loop(self, data):
        data_to_plot, timestamp = data
        self.nb_samples = data_to_plot.shape[0]
        x = np.arange(self.nb_samples)
        for ax, bgrd, points, chn in zip(self.ax, self.bgrd, self.points, self.channels_to_plot):
            self.fig.canvas.restore_region(bgrd)  # restore background
            points.set_data(x, data_to_plot[:self.nb_samples, chn])
            ax.draw_artist(points)  # redraw just the points
            self.fig.canvas.blit(ax.bbox)  # fill in the axes rectangle
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()


@register_callback
class PlotPQG(BaseCallback):

    FRIENDLY_NAME = 'plot_fast'

    def __init__(self, data_source, *, poll_timeout=0.01,
                 channels_to_plot: List, nb_samples: int = 10_000,
                 **kwargs):
        super().__init__(data_source=data_source, poll_timeout=poll_timeout, **kwargs)
        self.channels_to_plot = channels_to_plot
        self.nb_channels = len(self.channels_to_plot)
        self.nb_samples = nb_samples

        from pyqtgraph.Qt import QtGui
        import pyqtgraph as pg
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('leftButtonPan', False)
        # set up window and subplots
        self.app = QtGui.QApplication([])
        self.win = pg.GraphicsWindow(title="DAQ")
        self.win.resize(1000, min(100 * self.nb_channels, 1000))
        self.p = []
        for _ in range(self.nb_channels):
            w = self.win.addPlot(y=np.zeros((self.nb_samples,)))
            w.setXRange(0, self.nb_samples, padding=0)
            w.setYRange(-5, 5)
            w.setMouseEnabled(x=False, y=False)
            w.enableAutoRange('xy', False_)
            self.p.append(w.plot(pen='k'))
            self.win.nextRow()
        self.app.processEvents()

    def _loop(self, data):
        data_to_plot, timestamp = data
        for plot, chan in zip(self.p, self.channels_to_plot):
            plot.setData(data_to_plot[:, chan])
        self.app.processEvents()


@register_callback
class SaveHDF(BaseCallback):

    FRIENDLY_NAME = 'save_h5'
    SUFFIX = '_daq.h5'

    def __init__(self, data_source, *, file_name, attrs=None, poll_timeout=0.01, **kwargs):
        super().__init__(data_source=data_source, poll_timeout=poll_timeout, **kwargs)
        self.file_name = file_name
        self.f = tables.open_file(self.file_name + self.SUFFIX, mode="w")
        self.vanilla: bool = True
        self.arrays = dict()

    @classmethod
    def make_concurrent(cls, task_kwargs, comms='queue'):
        return ConcurrentTask(task=cls.make_run, task_kwargs=task_kwargs, comms=comms)


    def _init_data(self, data, systemtime):
        filters = tables.Filters(complevel=4, complib='zlib', fletcher32=True)

        self.arrays['samples'] = self.f.create_earray(self.f.root, 'samples',
                                                    tables.Atom.from_dtype(data.dtype),
                                                    shape=[0, *data.shape[1:]],
                                                    chunkshape=[*data.shape],
                                                    filters=filters)

        self.arrays['systemtime'] = self.f.create_earray(self.f.root, 'systemtime',
                            tables.Atom.from_dtype(np.array(systemtime).dtype),
                            shape=[0, 1],
                            chunkshape=[100, 1],
                            filters=filters)

        samplenumber = self.f.root['samples'].shape[:1]
        self.arrays['samplenumber'] = self.f.create_earray(self.f.root, 'samplenumber',
                            tables.Atom.from_dtype(np.array([samplenumber])[:, np.newaxis].dtype),
                            shape=[0, 1],
                            chunkshape=[100, 1],
                            filters=filters)

    def _append_data(self, data, systemtime):
        self.arrays['samples'].append(data)

        samplenumber = data.shape[:1]  # self.f.root['samples'].shape[:1]
        self.arrays['samplenumber'].append(np.array([samplenumber]))

        self.arrays['systemtime'].append(systemtime)

    def _loop(self, data):
        data_to_save, systemtime = data  # unpack
        if self.vanilla:
            self._init_data(data_to_save, np.array([systemtime])[:, np.newaxis])
            self.vanilla = False
        self._append_data(data_to_save, np.array([systemtime])[:, np.newaxis])

    def _cleanup(self):
        if self.f.isopen:
            self.f.flush()
            self.f.close()
        else:
            logging.debug(f"{self.file_name} already closed.")


@register_callback
class SaveDLP_HDF(BaseCallback):
    """
    Save dict of dicts of single values to h5.
    First dict's keys map to groups, second dict's keys to variables.
    """

    FRIENDLY_NAME = 'savedlp_h5'
    SUFFIX = '_dlp.h5'

    def __init__(self, data_source, *, file_name, attrs=None, poll_timeout=0.01, **kwargs):
        super().__init__(data_source=data_source, poll_timeout=poll_timeout, **kwargs)
        self.file_name = file_name
        self.f = tables.open_file(self.file_name + self.SUFFIX, mode="w")
        self.vanilla: bool = True  # True if the data structure has not been initialized (via `_init_data`)
        self.arrays = dict()

    @classmethod
    def make_concurrent(cls, task_kwargs, comms='queue'):
        return ConcurrentTask(task=cls.make_run, task_kwargs=task_kwargs, comms=comms)

    def _init_data(self, data, systemtime):
        filters = tables.Filters(complevel=4, complib='zlib', fletcher32=True)
        for grp_name, grp_data in data.items():
            group = self.f.create_group('/', name=grp_name)
            self.arrays[grp_name] = dict()
            for key, val in grp_data.items():
                self.arrays[grp_name][key] = self.f.create_earray(group, key,
                                                    tables.Atom.from_dtype(np.array(val).dtype),
                                                    shape=(0,),
                                                    chunkshape=(1000,),
                                                    filters=filters)

        self.arrays['systemtime'] = self.f.create_earray(self.f.root, 'systemtime',
                            tables.Atom.from_dtype(systemtime.dtype),
                            shape=(0,),
                            chunkshape=(1000,),
                            filters=filters)
        self.vanilla = False

    def _append_data(self, data, systemtime):
        for grp_name, grp_data in data.items():
            for key, val in grp_data.items():
                self.arrays[grp_name][key].append(np.array([val]))
        self.arrays['systemtime'].append(systemtime)

    def _loop(self, data):
        data_to_save, systemtime = data  # unpack
        if self.vanilla:
            self._init_data(data_to_save, np.array([systemtime]))
        self._append_data(data_to_save, np.array([systemtime]))

    def _cleanup(self):
        if self.f.isopen:
            self.f.flush()
            self.f.close()
        else:
            logging.debug(f"{self.file_name} already closed.")


@register_callback
class RealtimeDSS(BaseCallback):
    def __init__(self, data_source, *, poll_timeout=0.01,
                 model_save_name: str = None,
                 **kwargs):
        super().__init__(data_source=data_source, poll_timeout=poll_timeout, **kwargs)
        """Coroutine for rt processing of data."""
        from ethomaster.head.ZeroClient import ZeroClient
        from ethoservice.ANAZeroService import ANA
        import subprocess
        import tensorflow as tf
        import dss.utils
        import dss.event_utils

        print("   started RT processing")
        ip_address = 'localhost'
        # init DAQ for output
        self.nit = ZeroClient(ip_address, 'nidaq')
        self.sp = subprocess.Popen('python -m ethoservice.ANAZeroService')
        self.nit.connect("tcp://{0}:{1}".format(ip_address, ANA.SERVICE_PORT))
        self.nit.setup(-1, 0)
        # nit.init_local_logger('{0}/{1}/{1}_nit.log'.format(daq_save_folder, filename))

        self.samplerate = 10_000  # make sure audio data and the annotations are all on the same sampling rate
        # bandpass to get rid of slow baseline fluctuations and high-freuqency ripples
        self.sos_bp = ss.butter(5, [50, 1000], 'bandpass', output='sos', fs=self.samplerate)

        print('preparing network')
        # model_save_name = 'C:/Users/ncb.UG-MGEN/dss/vibrations1024/20191109_074320'
        # model_save_name = 'C:/Users/ncb.UG-MGEN/dss/vibrations4096/20191108_235948'
        # model_save_name = 'C:/Users/ncb.UG-MGEN/dss/vibrations8192/20191109_080559'
        self.model_save_name = model_save_name
        self.model, self.params = dss.utils.load_model_and_params(self.model_save_name)
        self.input_shape = self.model.inputs[0].shape[1:]
        self.model.predict(np.zeros((1, *self.input_shape)))  # use model.input_shape

        self.data_buffer = np.zeros(self.input_shape)
        self.started = False

    @classmethod
    def make_concurrent(cls, task_kwargs, comms='array'):
        return ConcurrentTask(task=cls.make_run, task_kwargs=task_kwargs, comms=comms)

    def _append_to_buffer(self, buffer, x):
        buffer = np.roll(buffer, shift=-x.shape[0], axis=0)
        buffer[-len(x):, ...] = x
        return buffer

    def _loop(self, data):
        # TODO: save raw data, filtered data and prediction to file...
        data = data[:, :self.input_shape[-1]]
        data = ss.sosfiltfilt(self.sos_bp, data, axis=0).astype(np.float16)
        self.data_buffer = self._append_to_buffer(self.data_buffer, data)
        batch = self.data_buffer.reshape((1, *self.data_buffer.shape))  # model expects [nb_batches, nb_samples=1024, nb_channels=16]
        # batch = data.reshape((1, *data.shape))  # model expects [nb_batches, nb_samples=1024, nb_channels=16]
        prediction = self.model.predict(batch)

        # detect vibration pulses:
        # pulsetimes_pred, pulsetimes_pred_confidence = dss.event_utils.detect_events((prediction[0, ..., 1]>0.2).astype(np.float), thres=0.5, min_dist=500)
        pulsetimes_pred = peakutils.indexes(prediction[0, ..., 1], thres=0.25, min_dist=500, thres_abs=True)

        # filter vibrations by preceding IPI
        min_ipi = 1000  # 100ms
        max_ipi = 2000  # 200ms
        good_pulses = np.logical_and(np.diff(pulsetimes_pred, append=0) > min_ipi,
                                    np.diff(pulsetimes_pred, append=0) < max_ipi)
        print(pulsetimes_pred, pulsetimes_pred[good_pulses])
        pulsetimes_pred = pulsetimes_pred[good_pulses]
        vibrations_present = len(pulsetimes_pred)>1

        if not self.started and vibrations_present:
            print('   sending START')
            self.nit.send_trigger(1.5, duration=3)
            self.started = True
        elif self.started and not vibrations_present:
            self.nit.send_trigger(0, duration=None)
            self.started = False

    def _cleanup(self):
        print("   stopped RT processing")
        self.nit.send_trigger(0, duration=None)
        self.nit.finish()
        self.nit.stop_server()
        del(self.nit)
        self.sp.terminate()
        self.sp.kill()


if __name__ == "__main__":
    import time

    # ct = PlotPQG.make_concurrent(task_kwargs={'channels_to_plot': [0, 2], 'rate': .2}, comms='pipe')
    # ct.start()
    # for _ in range(1000):
    #     timestamp = time.time()
    #     ct.send((np.random.randn(10_000, 4), timestamp))
    # ct.finish()
    # ct.close()

    ct = SaveHDF.make_concurrent({'file_name': 'test'})
    ct.start()
    for _ in range(10):
        timestamp = time.time()
        print(timestamp)
        # ct.send((np.random.randn(10_000, 4), timestamp))
        ct.send((np.zeros((10_000, 4)), timestamp))
        time.sleep(1)
    ct.finish()
    ct.close()
