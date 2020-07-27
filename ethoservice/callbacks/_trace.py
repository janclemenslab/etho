import numpy as np
import h5py
import logging
import sys
from ..utils.log_exceptions import for_all_methods, log_exceptions
from . import _register_callback


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
@_register_callback
def plot(disp_queue, channels_to_plot):
    """Coroutine for plotting with matplotlib (not so fast).

    Fast-ish, realtime as per: https://gist.github.com/pklaus/62e649be55681961f6c4
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


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
@_register_callback
def plot_fast(disp_queue, channels_to_plot, nb_samples=10_000):
    """Coroutine for plotting using pyqtgraph (FAST!!)."""
    from pyqtgraph.Qt import QtGui
    import pyqtgraph as pg
    pg.setConfigOption('background', 'w')
    pg.setConfigOption('leftButtonPan', False)

    nb_channels = len(channels_to_plot)
    if nb_samples is None:
        nb_samples = 10_000
    # set up window and subplots
    app = QtGui.QApplication([])
    win = pg.GraphicsWindow(title="DAQ")
    win.resize(1000, min(100 * nb_channels, 1000))
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


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
@_register_callback
def save(sample_queue, filename, num_channels=1, attrs=None, sizeincrement=100,
         chunk_duration=10_000, start_time=None):
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
                                    maxshape=[None, num_channels], chunks=(chunk_duration, num_channels),
                                    dtype=np.float64, compression="gzip")
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


def _append_to_buffer(buffer, x):
    buffer = np.roll(buffer, shift=-x.shape[0], axis=0)
    buffer[-len(x):, ...] = x
    return buffer


@for_all_methods(log_exceptions(logging.getLogger(__name__)))
@_register_callback
def process_dss(sample_queue):
    """Coroutine for rt processing of data."""
    print("   started RT processing")
    # init digital output - turn on if any channel crosses threshold
    from ethomaster.head.ZeroClient import ZeroClient
    from ethoservice.ANAZeroService import ANA
    import subprocess

    print('preparing storage')
    import zarr
    filename = 'C:/Users/ncb.UG-MGEN/data/rt_test.zarr'
    f = zarr.open(filename, mode="w")

    num_channels = 16
    dset_raw = f.create_dataset("data_raw", shape=[0, 4096, num_channels],
                                    chunks=[100, 8192, num_channels], dtype=np.float64)
    dset_pre = f.create_dataset("data_preprocessed", shape=[0, 8192, num_channels],
                                    chunks=[100, 8192, num_channels], dtype=np.float64)
    dset_post = f.create_dataset("inference", shape=[0, 8192, 2],
                                    chunks=[100, 8192, 2], dtype=np.float64)

    ip_address = 'localhost'
    # init DAQ for output
    print([ANA.SERVICE_PORT, ANA.SERVICE_NAME])
    nit = ZeroClient("{0}".format(ip_address), 'nidaq')
    sp = subprocess.Popen('python -m ethoservice.ANAZeroService')
    nit.connect("tcp://{0}:{1}".format(ip_address, ANA.SERVICE_PORT))
    nit.setup(-1, 0)
    # nit.init_local_logger('{0}/{1}/{1}_nit.log'.format(daq_save_folder, filename))
    started = False

    samplerate = 10_000  # make sure audio data and the annotations are all on the same sampling rate
    # bandpass to get rid of slow baseline fluctuations and high-freuqency ripples
    import scipy.signal as ss
    sos_bp = ss.butter(5, [50, 1000], 'bandpass', output='sos', fs=samplerate)
    print('preparing network')
    # init network
    import tensorflow as tf
    import dss.utils
    import dss.event_utils
    import peakutils

    # model_save_name = 'C:/Users/ncb.UG-MGEN/dss/vibrations1024/20191109_074320'
    # model_save_name = 'C:/Users/ncb.UG-MGEN/dss/vibrations4096/20191108_235948'
    model_save_name = 'C:/Users/ncb.UG-MGEN/dss/vibrations8192/20191109_080559'
    model, params = dss.utils.load_model_and_params(model_save_name)
    input_shape = model.inputs[0].shape[1:]
    model.predict(np.zeros((1, *input_shape)))  # use model.input_shape

    RUN = True
    print('DONE DONE DONE')

    data_buffer = np.zeros(input_shape)

    while RUN:
        if sample_queue.poll():
            data = sample_queue.get()
            if data is None:
                pass  # RUN = False
                # break
            else:
                # TODO: save raw data, filtered data and prediction to file...
                data = data[:, :16]
                dset_raw.append(data.reshape(1, *data.shape), axis=0)
                data = ss.sosfiltfilt(sos_bp, data, axis=0).astype(np.float16)
                data_buffer = _append_to_buffer(data_buffer, data)
                batch = data_buffer.reshape((1, *data_buffer.shape))  # model expects [nb_batches, nb_samples=1024, nb_channels=16]
                dset_pre.append(batch, axis=0)
                # batch = data.reshape((1, *data.shape))  # model expects [nb_batches, nb_samples=1024, nb_channels=16]
                prediction = model.predict(batch)
                dset_post.append(prediction, axis=0)  # model return [nb_batches, nb_samples, nb_classes]

                # detect vibration pulses:
                # pulsetimes_pred, pulsetimes_pred_confidence = dss.event_utils.detect_events((pred_buffer[..., 0]>0.2).astype(np.float), thres=0.5, min_dist=500)
                # pulsetimes_pred, pulsetimes_pred_confidence = dss.event_utils.detect_events((prediction[0, ..., 1]>0.2).astype(np.float),
                #                                                                             thres=0.5, min_dist=500)
                pulsetimes_pred = peakutils.indexes(prediction[0, ..., 1], thres=0.25, min_dist=500, thres_abs=True)

                # filter vibrations by preceding IPI
                min_ipi = 1000  # 100ms
                max_ipi = 2000  # 200ms
                good_pulses = np.logical_and(np.diff(pulsetimes_pred, append=0) > min_ipi,
                                             np.diff(pulsetimes_pred, append=0) < max_ipi)
                print(pulsetimes_pred, pulsetimes_pred[good_pulses])
                pulsetimes_pred = pulsetimes_pred[good_pulses]
                vibrations_present = len(pulsetimes_pred)>1

                if not started and vibrations_present:
                    print('   sending START')
                    nit.send_trigger(1.5, duration=3)
                    started = True
                elif started and not vibrations_present:
                    nit.send_trigger(0, duration=None)
                    started = False

    print("   stopped RT processing")
    f.close()
    nit.send_trigger(0, duration=None)
    nit.finish()
    nit.stop_server()
    del(nit)
    sp.terminate()
    sp.kill()


# def log(file_name):
#     f = open(file_name, 'r')      # open file
#     try:
#         while True:
#             message = (yield)  # gets sent variables
#             f.write(message)  # write log to file
#     except GeneratorExit:
#         print("   closing file \"{0}\".".format(file_name))
#         f.close()  # close file


def _format_playlist(playlist, cnt):
    string = f'cnt: {cnt}; '
    for key, val in playlist.items():
        string += f'{key}: {val}; '
    return string


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
