# -*- coding: utf-8 -*-
import PyDAQmx as daq
from PyDAQmx.DAQmxCallBack import *
from PyDAQmx.DAQmxConstants import *
from PyDAQmx.DAQmxFunctions import *

import threading
import sys
import time
import numpy as np

from .ConcurrentTask import ConcurrentTask


class IOTask(daq.Task):
    """IOTask does X."""

    def __init__(self, dev_name="Dev1", cha_name=["ai0"], limits=10.0, rate=10000.0,
                 nb_inputsamples_per_cycle=None):
        """[summary]
        
        Args:
            dev_name (str, optional): [description]. Defaults to "Dev1".
            cha_name (list, optional): [description]. Defaults to ["ai0"].
            limits (float, optional): [description]. Defaults to 10.0.
            rate (float, optional): [description]. Defaults to 10000.0.
            nb_inputsamples_per_cycle ([type], optional): [description]. Defaults to None.
        
        Raises:
            TypeError: [description]
            ValueError: [description]
        """
        # check inputs
        daq.Task.__init__(self)
        if not isinstance(cha_name, (list, tuple)):
            raise TypeError(f'`cha_name` is {type(cha_name)}. Should be `list` or `tuple`')

        self.samples_read = daq.int32()
        cha_types = {"ai": "analog_input", "ao": "analog_output", 'po': 'digital_output'}
        self.cha_type = [cha_types[cha[:2]] for cha in cha_name]
        if len(set(self.cha_type)) > 1:
            raise ValueError('channels should all be of the same type but are {0}.'.format(set(self.cha_type)))

        self.cha_name = [dev_name + '/' + ch for ch in cha_name]  # append device name
        self.cha_string = ", ".join(self.cha_name)
        self.num_channels = len(cha_name)
        if nb_inputsamples_per_cycle is None:
            nb_inputsamples_per_cycle = int(rate)
            
        # FIX: input and output tasks can have different sizes
        self.callback = None
        self.data_gen = None  # called at start of callback
        self.data_rec = None  # called at end of callback
        if self.cha_type[0] is "analog_input":
            self.num_samples_per_chan = nb_inputsamples_per_cycle
            self.num_samples_per_event = nb_inputsamples_per_cycle  # self.num_samples_per_chan*self.num_channels
            self.CreateAIVoltageChan(self.cha_string, "", DAQmx_Val_RSE, -limits, limits, DAQmx_Val_Volts, None)
            self.AutoRegisterEveryNSamplesEvent(DAQmx_Val_Acquired_Into_Buffer, self.num_samples_per_event, 0)
            self.CfgInputBuffer(self.num_samples_per_chan * self.num_channels * 4)
            clock_source = 'OnboardClock'  # ao/SampleClock'  # None  # use internal clock
        elif self.cha_type[0] is "analog_output":
            self.num_samples_per_chan = 5000
            self.num_samples_per_event = 1000  # determines shortest interval at which new data can be generated
            self.CreateAOVoltageChan(self.cha_string, "", -limits, limits, DAQmx_Val_Volts, None)
            self.AutoRegisterEveryNSamplesEvent(DAQmx_Val_Transferred_From_Buffer, self.num_samples_per_event, 0)
            self.CfgOutputBuffer(self.num_samples_per_chan * self.num_channels * 2)
            # self.CfgOutputBuffer(self.num_samples_per_chan)
            # ensures continuous output and avoids collision of old and new data in buffer
            self.SetWriteRegenMode(DAQmx_Val_DoNotAllowRegen)
            clock_source = 'ai/SampleClock'  # 'OnboardClock'  # None  # use internal clock
        elif self.cha_type[0] is "digital_output":
            self.num_samples_per_chan = 5000
            self.num_samples_per_event = 1000  # determines shortest interval at which new data can be generated
            self.CreateDOChan(self.cha_string, "", DAQmx_Val_ChanPerLine)
            self.AutoRegisterEveryNSamplesEvent(DAQmx_Val_Transferred_From_Buffer, self.num_samples_per_event, 0)
            self.CfgOutputBuffer(self.num_samples_per_chan * self.num_channels * 2)
            # ensures continuous output and avoids collision of old and new data in buffer
            self.SetWriteRegenMode(DAQmx_Val_DoNotAllowRegen)
            clock_source = 'ai/SampleClock'  # None  # use internal clock

        if 'digital' in self. cha_type[0]:
            self._data = np.zeros((self.num_samples_per_chan, self.num_channels), dtype=np.uint8)  # init empty data array
        else:
            self._data = np.zeros((self.num_samples_per_chan, self.num_channels), dtype=np.float64)  # init empty data array
        self.CfgSampClkTiming(clock_source, rate, DAQmx_Val_Rising, DAQmx_Val_ContSamps, self.num_samples_per_chan)
        self.AutoRegisterDoneEvent(0)
        self._data_lock = threading.Lock()
        self._newdata_event = threading.Event()
        if 'output' in self.cha_type[0]:
            self.EveryNCallback()

    def __repr__(self):
        return '{0}: {1}'.format(self.cha_type[0], self.cha_string)

    def stop(self):
        """Stop DAQ."""
        if self.data_gen is not None:
            self._data = self.data_gen.close()  # close data generator
        if self.data_rec is not None:
            for data_rec in self.data_rec:
                data_rec.send(None)
                data_rec.finish(verbose=True, sleepcycletimeout=2)
                data_rec.close()

    def EveryNCallback(self):
        """Call whenever there is data to be read/written from/to the buffer.

        Calls `self.data_gen` or `self.data_rec` for requesting/processing data.
        """
        # for clean teardown, catch PyDAQmx.DAQmxFunctions.GenStoppedToPreventRegenOfOldSamplesError
        with self._data_lock:
            systemtime = time.time()
            if self.data_gen is not None:
                try:
                    self._data = next(self.data_gen)  # get data from data generator
                except StopIteration:
                    self._data = None

            if self.cha_type[0] is "analog_input":
                # should only read self.num_samples_per_event!! otherwise recordings will be zeropadded for each chunk
                self.ReadAnalogF64(DAQmx_Val_Auto, 1.0, DAQmx_Val_GroupByScanNumber,
                                   self._data, self.num_samples_per_chan * self.num_channels, daq.byref(self.samples_read), None)
                # only keep samples that were actually read, .value converts c_long to int
                self._data = self._data[:self.samples_read.value, :]

            elif self.cha_type[0] is "analog_output" and self._data is not None:
                self.WriteAnalogF64(self._data.shape[0], 0, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByScanNumber,
                                    self._data, daq.byref(self.samples_read), None)
            elif self.cha_type[0] is 'digital_output' and self._data is not None:
                self.WriteDigitalLines(self._data.shape[0], 0, DAQmx_Val_WaitInfinitely, DAQmx_Val_GroupByScanNumber,
                                       self._data, daq.byref(self.samples_read), None)

            if self.data_rec is not None:
                for data_rec in self.data_rec:
                    if self._data is not None:
                        data_rec.send((self._data, systemtime))
            self._newdata_event.set()
        return 0  # The function should return an integer

    def DoneCallback(self, status):
        """Call when Task is stopped/done."""
        print("Done status", status)
        return 0  # The function should return an integer


def plot(disp_queue, channels_to_plot):
    """Coroutine for plotting with matplotlib (not so fast).

    Fast, realtime as per: https://gist.github.com/pklaus/62e649be55681961f6c4
    """
    import matplotlib
    matplotlib.use('tkagg')
    import matplotlib.pyplot as plt
    plt.ion()

    nb_channels = len(channels_to_plot)
    nb_samples = 10_000
    fig = plt.figure()
    fig.canvas.set_window_title('traces: daq')
    ax = [fig.add_subplot(nb_channels, 1, channel + 1) for channel in range(nb_channels)]
    plt.show(False)
    plt.draw()
    fig.canvas.start_event_loop(0.01)  # otherwise plot freezes after 3-4 iterations
    bgrd = [fig.canvas.copy_from_bbox(this_ax.bbox) for this_ax in ax]
    points = [this_ax.plot(np.arange(nb_samples), np.zeros((nb_samples, 1)), linewidth=0.4)[0] for this_ax in ax]  # init plot content
    [this_ax.set_ylim(-5, 5) for this_ax in ax]  # init plot content
    [this_ax.set_xlim(0, nb_samples) for this_ax in ax]  # init plot content
    for cnt, ax2 in enumerate(fig.get_axes()[::-1]):
        ax2.label_outer()
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)

    RUN = True
    while RUN:
        try:
            if disp_queue.poll(0.1):
                data = disp_queue.recv()
                if data is not None:
                    nb_samples = data[0].shape[0]
                    x = np.arange(nb_samples)
                    for cnt, chn in enumerate(channels_to_plot):
                        fig.canvas.restore_region(bgrd[cnt])  # restore background
                        points[cnt].set_data(x, data[0][:nb_samples, chn])
                        ax[cnt].draw_artist(points[cnt])  # redraw just the points
                        fig.canvas.blit(ax[cnt].bbox)  # fill in the axes rectangle
                    fig.canvas.draw()
                    fig.canvas.flush_events()
                else:
                    RUN = False
        except Exception as e:
            print(e)
    # clean up
    print("   closing plot")
    plt.close(fig)


def plot_fast(disp_queue, channels_to_plot):
    """Coroutine for plotting using pyqtgraph (FAST!!)."""
    from pyqtgraph.Qt import QtGui
    import pyqtgraph as pg
    pg.setConfigOption('background', 'w')
    pg.setConfigOption('leftButtonPan', False)

    nb_channels = len(channels_to_plot)
    nb_samples = 10_000
    # set up window and subplots
    app = QtGui.QApplication([])
    win = pg.GraphicsWindow(title="DAQ")
    win.resize(1000, 100 * nb_channels)
    p = []
    for chan in range(nb_channels):
        w = win.addPlot(y=np.zeros((nb_samples,)))
        w.setXRange(0, nb_samples, padding=0)
        w.setYRange(-5, 5)
        w.setMouseEnabled(x=False, y=False)
        w.enableAutoRange('xy', False)
        p.append(w.plot(pen='k'))
        win.nextRow()

    app.processEvents()
    RUN = True
    while RUN:
        try:
            if disp_queue.poll(0.1):
                data = disp_queue.recv()
                if data is not None:
                    for plot, chan in zip(p, channels_to_plot):
                        plot.setData(data[0][:, chan])
                    app.processEvents()
                else:
                    RUN = False
        except Exception as e:
            print(e)
    # clean up
    print("   closing plot.")


def save(sample_queue, filename, num_channels=1, attrs=None, sizeincrement=100, start_time=None):
    """Coroutine for saving data."""
    import h5py

    f = h5py.File(filename, "w")

    if attrs is not None:
        for key, val in attrs.items():
            try:
                f.attrs[key] = val
            except (NameError, TypeError):
                f.attrs[key] = str(val)
            f.flush()

    dset_samples = f.create_dataset("samples", shape=[0, num_channels],
                                    maxshape=[None, num_channels], dtype=np.float64, compression="gzip")
    dset_systemtime = f.create_dataset("systemtime", shape=[sizeincrement, 1],
                                       maxshape=[None, 1], dtype=np.float64, compression="gzip")
    dset_samplenumber = f.create_dataset("samplenumber", shape=[sizeincrement, 1],
                                         maxshape=[None, 1], dtype=np.float64, compression="gzip")
    print("opened file \"{0}\".".format(filename))
    framecount = 0
    RUN = True
    while RUN:
        frame_systemtime = sample_queue.get()
        if framecount % sizeincrement == sizeincrement - 1:
            f.flush()
            dset_systemtime.resize(dset_systemtime.shape[0] + sizeincrement, axis=0)
            dset_samplenumber.resize(dset_samplenumber.shape[0] + sizeincrement, axis=0)
        if frame_systemtime is None:
            print("   stopping save")
            RUN = False
        else:
            frame, systemtime = frame_systemtime  # unpack
            if start_time is None:
                start_time = systemtime
            sys.stdout.write("\r   {:1.1f} seconds: saving {} ({})".format(
                             systemtime - start_time, frame.shape, framecount))
            dset_samples.resize(dset_samples.shape[0] + frame.shape[0], axis=0)
            dset_samples[-frame.shape[0]:, :] = frame
            dset_systemtime[framecount, :] = systemtime
            dset_samplenumber[framecount, :] = frame.shape[0]
            framecount += 1
    f.flush()
    f.close()
    print("   closed file \"{0}\".".format(filename))

def process_digital(sample_queue):
    """Coroutine for rt processing of data."""
    print("   started RT processing")
    # init digital output - turn on if any channel crosses threshold
    from ethomaster.head.ZeroClient import ZeroClient
    from ethoservice.NITriggerZeroService import NIT
    import subprocess

    ip_address = 'localhost'
    port = "/Dev1/port0/line8:9"  # maps to P0.0 and P0.1 on the amplifier box
    trigger_types = {'START': [1, 1],
                     'STOP': [0, 0],
                    }
    print([NIT.SERVICE_PORT, NIT.SERVICE_NAME])
    nit = ZeroClient("{0}".format(ip_address), 'nidaq')
    sp = subprocess.Popen('python -m ethoservice.NITriggerZeroService')
    nit.connect("tcp://{0}:{1}".format(ip_address, NIT.SERVICE_PORT))
    nit.setup(-1, port)
    # nit.init_local_logger('{0}/{1}/{1}_nit.log'.format(daq_save_folder, filename))
    started = False
    thres = 3.5
    RUN = True

    while RUN:
        # if sample_queue.poll(0.001):
            # content = sample_queue.recv()
        content = sample_queue.get()
        if content is None:
            pass #RUN = False
        else: 
            data, systemtime = content
            peak_values = np.max(np.abs(data[:,:16]), axis=0)
            peak_crossing_channels = np.where(peak_values > thres)[0]
            if not started and len(peak_crossing_channels):
                print('   sending START')
                nit.send_trigger(trigger_types['START'], duration=None)
                started = True
            elif started and not len(peak_crossing_channels):
                print('   sending STOP')
                nit.send_trigger(trigger_types['STOP'], duration=None)
                started = False
            elif started:
                print('   RUNNING')
    print("   stopped RT processing")

    nit.finish()
    nit.stop_server()
    del(nit)
    sp.terminate()
    sp.kill()


def process_analog(sample_queue):
    """Coroutine for rt processing of data."""
    print("   started RT processing")
    # init digital output - turn on if any channel crosses threshold
    from ethomaster.head.ZeroClient import ZeroClient
    from ethoservice.ANAZeroService import ANA
    import subprocess

    ip_address = 'localhost'
    
    print([ANA.SERVICE_PORT, ANA.SERVICE_NAME])
    nit = ZeroClient("{0}".format(ip_address), 'nidaq')
    sp = subprocess.Popen('python -m ethoservice.ANAZeroService')
    nit.connect("tcp://{0}:{1}".format(ip_address, ANA.SERVICE_PORT))
    nit.setup(-1, 0)
    # nit.init_local_logger('{0}/{1}/{1}_nit.log'.format(daq_save_folder, filename))
    started = False
    thres = 3.5
    RUN = True

    while RUN:
        if sample_queue.poll():
            print('pre', sample_queue.stale)
            data = sample_queue.get()
            print('post', sample_queue.stale)
            # content = sample_queue.get()
            if data is None:
                # print('none')
                pass  # RUN = False
                # break
            else: 
                # data, systemtime = content
                print(data.shape)
                peak_values = np.max(np.abs(data[:,:16]), axis=0)
                print(peak_values)
                peak_crossing_channels = np.where(peak_values > thres)[0]
                if not started and len(peak_crossing_channels):
                    print('   sending START')
                    nit.send_trigger(2, duration=1)
                    started = True
                elif started and not len(peak_crossing_channels):
                    nit.send_trigger(0, duration=None)
                    started = False
    print("   stopped RT processing")

    nit.send_trigger(0, duration=None)
    nit.finish()
    nit.stop_server()
    del(nit)
    sp.terminate()
    sp.kill()


def log(file_name):
    f = open(file_name, 'r')      # open file
    try:
        while True:
            message = (yield)  # gets sent variables
            f.write(message)  # write log to file
    except GeneratorExit:
        print("   closing file \"{0}\".".format(file_name))
        f.close()  # close file


def coroutine(func):
    """ decorator that auto-initializes (calls `next(None)`) coroutines"""
    def start(*args, **kwargs):
        cr = func(*args, **kwargs)
        next(cr)
        return cr
    return start


@coroutine
def data_playlist(sounds, play_order, playlist_info=None, logger=None, name='standard'):
    """sounds - list of nparrays"""
    first_run = True
    run_cnt = 0
    playlist_cnt = 0
    try:
        while play_order:
            run_cnt += 1
            # duplicate first stim - otherwise we miss the first in the playlist
            if first_run:
                pp = 0
                first_run = False
            else:
                pp = next(play_order)
                playlist_cnt += 1
                if playlist_info is not None:
                    msg = _format_playlist(playlist_info.loc[pp], playlist_cnt)
                    print(f'\n{msg}')
                    if logger:
                        logger.info(msg)
            stim = sounds[pp]
            yield stim
    except (GeneratorExit, StopIteration):
        print(f"   {name} cleaning up datagen.")


def _format_playlist(playlist, cnt):
    string = f'cnt: {cnt}; '
    for key, val in playlist.items():
        string += f'{key}: {val}; '
    return string
