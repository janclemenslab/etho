import pickle

import numpy as np

from etho.services.DAQZeroService import DAQ


class FakeService:
    def setup(self, *args, **kwargs):
        self.play_order = args[1]

    def init_local_logger(self, *_):
        pass


class FakeTask:
    """Capture DAQ output setup without requiring NI hardware."""

    def __init__(self, **kwargs):
        self.data_gen = None
        self.prefilled = None

    def set_data_generator(self, data_gen):
        self.data_gen = data_gen
        self.prefilled = next(data_gen)

    def CfgDigEdgeStartTrig(self, *_):
        pass

    def DisableStartTrig(self):
        pass


def test_setup_client_passes_pickleable_playlist(monkeypatch):
    service = FakeService()
    monkeypatch.setattr(DAQ, "make", lambda *args, **kwargs: service)
    monkeypatch.setattr("etho.services.DAQZeroService.parse_table", lambda _: None)
    monkeypatch.setattr("etho.services.DAQZeroService.load_sounds", lambda *args, **kwargs: [np.zeros((1, 1)), np.zeros((1, 1))])
    monkeypatch.setattr("etho.services.DAQZeroService.build_playlist", lambda *args, **kwargs: ([1, 0], 2))

    daq = {
        "samplingrate": 1,
        "shuffle": False,
        "device": None,
        "port": None,
        "clock_source": None,
        "nb_inputsamples_per_cycle": 1,
        "analog_chans_in": [],
        "analog_chans_out": None,
        "digital_chans_out": None,
        "analog_chans_in_info": None,
        "analog_chans_out_info": None,
        "digital_chans_out_info": None,
    }
    defaults = {"host": "localhost", "serializer": "default", "python_exe": "python", "savefolder": "/tmp"}

    DAQ.setup_client("DAQ", 0, {"DAQ": daq, "maxduration": 1}, defaults, "playlist.txt", "run", False, False)

    assert service.play_order == [1, 0]
    pickle.dumps(service.play_order)


def test_setup_prefills_output_with_first_playlist_item(monkeypatch):
    monkeypatch.setattr("etho.services.DAQZeroService.IOTask", FakeTask)
    service = type("Service", (), {})()
    service.log = None

    sounds = [np.array([[1.0], [2.0]]), np.array([[3.0], [4.0]])]
    DAQ.setup(
        service,
        play_order=[1, 0],
        playlist_info=None,
        analog_chans_out=["ao0"],
        analog_data_out=sounds,
        analog_chans_in=[],
        params={},
    )

    assert service.taskAO.data_gen is not None
    np.testing.assert_array_equal(service.taskAO.prefilled, sounds[1])
