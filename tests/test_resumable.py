import importlib

import numpy as np
import pandas as pd

from etho.resumable import ResumableExperimentRunner, playlist_arrays
from etho.services.resumable import ResumableDAQ, ResumableGCM


class FakeCallback:
    made = 0
    started = 0
    finished = 0
    closed = 0

    @classmethod
    def make_concurrent(cls, task_kwargs=None):
        cls.made += 1
        return cls()

    def start(self):
        type(self).started += 1

    def finish(self):
        type(self).finished += 1

    def close(self):
        type(self).closed += 1


class FakeTask:
    made = 0

    def __init__(self, **kwargs):
        type(self).made += 1
        self.kwargs = kwargs
        self.data_rec = []
        self.data_gen = None
        self.started = 0
        self.stopped = 0
        self.cleared = 0

    def StartTask(self):
        self.started += 1

    def StopTask(self):
        self.stopped += 1

    def ClearTask(self):
        self.cleared += 1


def test_resumable_daq_reuses_tasks_and_restarts_callbacks(monkeypatch):
    daq_module = importlib.import_module("etho.services.DAQZeroService")
    monkeypatch.setattr(daq_module, "daqmx_import_error", None, raising=False)
    monkeypatch.setattr(daq_module, "IOTask", FakeTask, raising=False)
    monkeypatch.setattr("etho.services.resumable.callbacks", {"save_h5": FakeCallback})

    FakeTask.made = 0
    FakeCallback.made = FakeCallback.started = FakeCallback.finished = FakeCallback.closed = 0
    params = {
        "samplingrate": 1000,
        "device": "Dev1",
        "clock_source": None,
        "nb_inputsamples_per_cycle": 100,
        "analog_chans_in": ["ai0"],
        "analog_chans_out": ["ao0"],
        "digital_chans_out": ["po0"],
        "callbacks": {"save_h5": None},
    }

    service = ResumableDAQ(params).setup_hardware()
    assert FakeTask.made == 3
    task_ai = service.taskAI
    task_ao = service.taskAO

    service.prepare_run("run1", analog_data_out=np.ones((1000, 1)), digital_data_out=np.zeros((1000, 1), dtype=np.uint8))
    service.start()
    service.progress()
    service.stop_run()
    service.prepare_run("run2", analog_data_out=np.ones((500, 1)), digital_data_out=np.zeros((500, 1), dtype=np.uint8))

    assert service.taskAI is task_ai
    assert service.taskAO is task_ao
    assert FakeCallback.made == 2
    assert task_ai.cleared == 0
    assert service._time_started is None
    assert service.prev_elapsed == 0

    service.close()
    assert task_ai.cleared == 1
    assert service.state == "closed"


class FakeCamera:
    made = 0

    def __init__(self, serialnumber):
        type(self).made += 1
        self.serialnumber = serialnumber
        self.started = 0
        self.stopped = 0
        self.closed = 0

    def init(self):
        pass

    def reset(self):
        pass

    def start(self):
        self.started += 1

    def stop(self):
        self.stopped += 1

    def close(self):
        self.closed += 1

    def get(self):
        return np.zeros((8, 10, 3), dtype=np.uint8), 0.0, 0.0

    def disable_gpio_strobe(self):
        pass

    def enable_gpio_strobe(self):
        pass

    def optimize_auto_exposure(self):
        pass

    @property
    def roi(self):
        return self._roi

    @roi.setter
    def roi(self, value):
        self._roi = value

    @property
    def framerate(self):
        return self._framerate

    @framerate.setter
    def framerate(self, value):
        self._framerate = value

    def __getattr__(self, name):
        if name in {"exposure", "brightness", "gamma", "gain", "binning", "external_trigger", "framerate"}:
            return getattr(self, "_" + name, None)
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name in {"exposure", "brightness", "gamma", "gain", "binning", "external_trigger", "framerate"}:
            self.__dict__["_" + name] = value
        else:
            self.__dict__[name] = value


def test_resumable_gcm_reuses_camera_and_restarts_callbacks(monkeypatch):
    monkeypatch.setitem(importlib.import_module("etho.services.camera").make, "Fake", FakeCamera)
    monkeypatch.setattr("etho.services.resumable.callbacks", {"save_avi": FakeCallback})

    FakeCamera.made = 0
    FakeCallback.made = FakeCallback.started = FakeCallback.finished = FakeCallback.closed = 0
    params = {
        "cam_type": "Fake",
        "cam_serialnumber": "1",
        "frame_width": 10,
        "frame_height": 8,
        "shutter_speed": 1000,
        "frame_rate": 30,
        "callbacks": {"save_avi": None},
    }

    service = ResumableGCM(params).setup_hardware()
    camera = service.c
    service.prepare_run("run1", 0.01)
    service.stop_run()
    service.prepare_run("run2", 0.01)

    assert FakeCamera.made == 1
    assert service.c is camera
    assert FakeCallback.made == 2
    assert camera.closed == 0

    service.close()
    assert camera.closed == 1


def test_resumable_gcm_preview_uses_display_callback(monkeypatch):
    monkeypatch.setitem(importlib.import_module("etho.services.camera").make, "Fake", FakeCamera)
    monkeypatch.setattr("etho.services.resumable.callbacks", {"save_avi": FakeCallback, "disp_fast": FakeCallback})

    FakeCallback.made = 0
    params = {
        "cam_type": "Fake",
        "cam_serialnumber": "1",
        "frame_width": 10,
        "frame_height": 8,
        "shutter_speed": 1000,
        "frame_rate": 30,
        "callbacks": {"save_avi": None},
    }

    service = ResumableGCM(params).setup_hardware()
    service.prepare_run("preview", 0.01, preview=True)

    assert service.callback_names == ["disp_fast"]
    assert FakeCallback.made == 1


def test_resumable_gcm_resets_reused_camera_timer(monkeypatch):
    monkeypatch.setitem(importlib.import_module("etho.services.camera").make, "Fake", FakeCamera)
    monkeypatch.setattr("etho.services.resumable.callbacks", {"save_avi": FakeCallback})
    monkeypatch.setattr("etho.services.resumable.time.time", lambda: 123.0)

    params = {
        "cam_type": "Fake",
        "cam_serialnumber": "1",
        "frame_width": 10,
        "frame_height": 8,
        "shutter_speed": 1000,
        "frame_rate": 30,
        "callbacks": {"save_avi": None},
    }

    service = ResumableGCM(params).setup_hardware()
    service.c._t0 = 1.0
    service.prepare_run("run1", 0.01)

    assert service.c._t0 == 123.0


def test_resumable_runner_lifecycle(monkeypatch):
    events = []

    class FakeDAQ:
        def __init__(self, params):
            self.params = params

        def setup_hardware(self):
            events.append("daq setup")
            return self

        def prepare_run(self, savefilename, analog_data_out=None, digital_data_out=None, duration=None, metadata=None):
            events.append(("daq prepare", savefilename, duration))

        def start(self):
            events.append("daq start")

        def stop_run(self):
            events.append("daq stop")

        def close(self):
            events.append("daq close")

    class FakeGCM:
        def __init__(self, params):
            self.params = params

        def setup_hardware(self):
            events.append("gcm setup")
            return self

        def prepare_run(self, savefilename, duration, preview=False):
            events.append(("gcm prepare", savefilename, duration))

        def start(self):
            events.append("gcm start")

        def stop_run(self):
            events.append("gcm stop")

        def close(self):
            events.append("gcm close")

    monkeypatch.setattr("etho.resumable.ResumableDAQ", FakeDAQ)
    monkeypatch.setattr("etho.resumable.ResumableGCM", FakeGCM)
    monkeypatch.setattr("etho.resumable.time.sleep", lambda *args: None)

    protocol = {
        "maxduration": 1,
        "use_services": ["GCM", "DAQ"],
        "GCM": {},
        "DAQ": {},
    }
    runner = ResumableExperimentRunner(protocol=protocol, save_prefix_root="run")
    runner.setup_hardware().prepare_run(analog_data_out=np.ones((10, 1))).start().stop_run()
    runner.prepare_run(analog_data_out=np.ones((10, 1))).start().close()

    assert events[:2] == ["gcm setup", "daq setup"]
    assert "gcm start" in events
    assert "daq start" in events
    assert events[-2:] == ["gcm close", "daq close"]


def test_resumable_runner_preview_skips_daq(monkeypatch):
    events = []

    class FakeDAQ:
        def __init__(self, params):
            self.state = "new"

        def setup_hardware(self):
            self.state = "ready"
            events.append("daq setup")
            return self

        def prepare_run(self, savefilename, analog_data_out=None, digital_data_out=None, duration=None, metadata=None):
            self.state = "prepared"
            events.append("daq prepare")

        def start(self):
            events.append("daq start")

        def stop_run(self):
            self.state = "stopped"
            events.append("daq stop")

        def close(self):
            events.append("daq close")

    class FakeGCM:
        def __init__(self, params):
            pass

        def setup_hardware(self):
            events.append("gcm setup")
            return self

        def prepare_run(self, savefilename, duration, preview=False):
            events.append(("gcm prepare", preview))

        def start(self):
            events.append("gcm start")

        def stop_run(self):
            events.append("gcm stop")

        def close(self):
            events.append("gcm close")

    monkeypatch.setattr("etho.resumable.ResumableDAQ", FakeDAQ)
    monkeypatch.setattr("etho.resumable.ResumableGCM", FakeGCM)
    monkeypatch.setattr("etho.resumable.time.sleep", lambda *args: None)

    protocol = {
        "maxduration": 1,
        "use_services": ["GCM", "DAQ"],
        "GCM": {},
        "DAQ": {},
    }
    ResumableExperimentRunner(protocol=protocol, save_prefix_root="run").setup_hardware().prepare_run(preview=True).start()

    assert ("gcm prepare", True) in events
    assert "gcm start" in events
    assert "daq prepare" not in events
    assert "daq start" not in events


def test_resumable_runner_uses_regular_save_dir_and_service_file_suffixes(monkeypatch, tmp_path):
    filenames = []

    class FakeGCM:
        def __init__(self, params):
            pass

        def setup_hardware(self):
            return self

        def prepare_run(self, savefilename, duration, preview=False):
            filenames.append(savefilename)

        def close(self):
            pass

    monkeypatch.setattr("etho.resumable.ResumableGCM", FakeGCM)
    monkeypatch.setitem(importlib.import_module("etho").config, "savefolder", str(tmp_path))

    protocol = {
        "maxduration": 1,
        "use_services": ["GCM", "GCM1"],
        "GCM": {},
        "GCM1": {},
    }
    ResumableExperimentRunner(protocol=protocol, save_prefix_root="trial").setup_hardware().prepare_run()

    assert (tmp_path / "trial").is_dir()
    assert filenames == [
        str(tmp_path / "trial" / "trial"),
        str(tmp_path / "trial" / "trial_2"),
    ]


def test_resumable_runner_timestamp_save_dir_uses_regular_format(monkeypatch, tmp_path):
    filenames = []

    class FakeGCM:
        def __init__(self, params):
            pass

        def setup_hardware(self):
            return self

        def prepare_run(self, savefilename, duration, preview=False):
            filenames.append(savefilename)

        def close(self):
            pass

    monkeypatch.setattr("etho.resumable.ResumableGCM", FakeGCM)
    monkeypatch.setitem(importlib.import_module("etho").config, "savefolder", str(tmp_path))
    monkeypatch.setitem(importlib.import_module("etho").config, "host", "rig")
    monkeypatch.setattr("etho.resumable.time.strftime", lambda *_: "20260521_123456")

    protocol = {
        "maxduration": 1,
        "use_services": ["GCM"],
        "GCM": {},
    }
    ResumableExperimentRunner(protocol=protocol).setup_hardware().prepare_run()

    assert (tmp_path / "rig-20260521_123456").is_dir()
    assert filenames == [str(tmp_path / "rig-20260521_123456" / "rig-20260521_123456")]


def test_playlist_arrays_reuses_loaded_stimuli_but_rebuilds_playlist(monkeypatch):
    calls = {"load": 0, "build": 0}

    def fake_load_sounds(*args, **kwargs):
        calls["load"] += 1
        return [np.ones((2, 1))]

    def fake_build_playlist(*args, **kwargs):
        calls["build"] += 1
        return [0], 2

    monkeypatch.setattr("etho.resumable.parse_table", lambda playlistfile: pd.DataFrame({"stimFileName": ["a"]}))
    monkeypatch.setattr("etho.resumable.load_sounds", fake_load_sounds)
    monkeypatch.setattr("etho.resumable.build_playlist", fake_build_playlist)
    monkeypatch.setitem(importlib.import_module("etho").config, "ATTENUATION", None)

    protocol = {
        "maxduration": 1,
        "use_services": ["DAQ"],
        "DAQ": {
            "samplingrate": 1,
            "shuffle": False,
            "digital_chans_out": None,
        },
    }
    cache = {}
    playlist_arrays(protocol, "playlist.txt", cache=cache)
    playlist_arrays(protocol, "playlist.txt", cache=cache)

    assert calls == {"load": 1, "build": 2}


def test_resumable_gui_reuses_existing_gui():
    import etho.app
    import etho.res_app

    assert issubclass(etho.res_app.MainWindow, etho.app.MainWindow)


def test_resumable_gui_keeps_preview_debug_and_removes_restart():
    import etho.res_app

    assert "camera_preview" in etho.res_app.MainWindow.__dict__
    assert "restart_experiment" not in etho.res_app.MainWindow.__dict__
    assert "closeEvent" in etho.res_app.MainWindow.__dict__


def test_cli_exposes_resumable_commands(monkeypatch):
    import etho.cli as cli

    subcommands = {}
    monkeypatch.setattr(cli.defopt, "run", lambda commands, show_defaults=False: subcommands.update(commands))

    cli.main()

    assert subcommands["res-run"] is cli.res_run
    assert "res-gui" in subcommands


def test_res_run_calls_resumable_runner(monkeypatch):
    import etho.cli as cli
    import etho.resumable

    called = {}
    monkeypatch.setattr(etho.resumable, "run", lambda **kwargs: called.update(kwargs) or "done")

    assert cli.res_run(
        "protocol.yml",
        "playlist.txt",
        save_prefix="trial",
        show_progress=False,
        debug=True,
        preview=True,
    ) == "done"
    assert called == {
        "protocolfile": "protocol.yml",
        "playlistfile": "playlist.txt",
        "save_prefix": "trial",
        "show_progress": False,
        "debug": True,
        "preview": True,
    }
