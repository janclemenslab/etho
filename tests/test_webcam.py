import logging
from types import SimpleNamespace

import av
import pytest

from etho.services.GCMZeroService import GCM
from etho.services.camera import Webcam
from etho.services.camera import webcam
from etho.services.resumable import ResumableGCM


UNSUPPORTED_CONTROLS = {
    "shutter_speed": "AUTO",
    "brightness": 15,
    "gamma": 2,
    "gain": 3,
    "binning": 2,
    "optimize_auto_exposure": True,
    "external_trigger": True,
}


def device(name, description, *media_types):
    return SimpleNamespace(name=name, description=description, media_types=media_types)


@pytest.mark.parametrize(
    "system, input_format, devices, expected",
    [
        (
            "Darwin",
            "avfoundation",
            [device("0", "Microphone", "audio"), device("1", "Desk camera", "video"), device("2", "Capture screen 0", "video")],
            [("1:none", "Desk camera")],
        ),
        (
            "Linux",
            "v4l2",
            [device("/dev/video2", "USB camera"), device("/dev/video0", "Desk camera")],
            [("/dev/video0", "Desk camera"), ("/dev/video2", "USB camera")],
        ),
        (
            "Windows",
            "dshow",
            [device("audio-id", "Microphone", "audio"), device("camera-id", "Desk camera", "video")],
            [("video=camera-id", "Desk camera")],
        ),
    ],
)
def test_webcam_numbers_match_list_and_select_ffmpeg_input(monkeypatch, system, input_format, devices, expected):
    monkeypatch.setattr(webcam.platform, "system", lambda: system)

    def enumerate_devices(requested_format):
        assert requested_format == input_format
        return devices

    monkeypatch.setattr(av, "enumerate_input_devices", enumerate_devices)
    assert list(Webcam.enumerate_devices()) == list(enumerate(name for _, name in expected))

    for number, (source, _) in enumerate(expected):
        camera = Webcam(str(number))
        camera.init()
        assert camera._source == source

    with pytest.raises(ValueError, match="unavailable"):
        Webcam(len(expected)).init()
    with pytest.raises(ValueError, match="nonnegative integer"):
        Webcam(-1).init()


@pytest.fixture
def synthetic_webcam(monkeypatch):
    monkeypatch.setattr(webcam.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(av, "enumerate_input_devices", lambda _: [device("0", "Test camera", "video")])
    open_input = av.open
    opens = []

    def open_webcam(source, *, format, container_options, timeout):
        assert source == "0:none"
        assert format == "avfoundation"
        assert container_options == {"video_size": "64x48", "framerate": "30.0"}
        capture = open_input("testsrc=size=64x48:rate=25", format="lavfi")
        opens.append(capture)
        return capture

    monkeypatch.setattr(av, "open", open_webcam)
    return opens


@pytest.mark.parametrize("resumable", [False, True])
def test_gcm_webcam_starts_and_releases_capture(monkeypatch, synthetic_webcam, resumable, caplog):
    params = {
        "cam_type": "Webcam",
        "cam_serialnumber": 0,
        "frame_width": 64,
        "frame_height": 48,
        "frame_rate": 30,
        "frame_offx": 10,
        "frame_offy": -2,
        **UNSUPPORTED_CONTROLS,
    }
    if resumable:
        service = ResumableGCM(params).setup_hardware()
        service.prepare_run("unused", 0, preview=False)
        stop = service.stop_run
    else:
        monkeypatch.setattr(GCM, "_init_network_logger", lambda service, _: setattr(service, "log", logging.getLogger(__name__)))
        service = GCM()
        service.setup("unused", 0, params)
        stop = service.finish

    assert service.test_image.shape == (48, 64, 3)
    assert service.c.roi == (0, 0, 64, 48)
    assert "Frame offsets are ignored for webcams." in caplog.messages
    assert f"Webcam ignores unsupported settings: {', '.join(UNSUPPORTED_CONTROLS)}." in caplog.messages
    assert service.framerate == 25
    assert service.info["image"][0]["width"] == 64
    assert service.info["image"][1]["exposure"] == "auto"
    assert service.c._container is None

    for _ in range(2 if resumable else 1):
        service.nFrames = 3
        service.start()
        service._worker_thread.join(timeout=5)

        shutdown = []
        service.callbacks.append(SimpleNamespace(finish=lambda: shutdown.append("finished"), close=lambda: shutdown.append("closed")))
        stop()
        stop()
        assert shutdown == ["finished", "closed"]
        assert service.frameNumber == 3
        assert service.c._container is None
        if resumable:
            service.prepare_run("unused", 0, preview=False)

    assert len(synthetic_webcam) == (3 if resumable else 2)


def test_gcm_client_warns_before_sending_webcam_settings(monkeypatch, tmp_path, caplog):
    def setup(savefilename, duration, params):
        assert params["frame_offx"] == params["frame_offy"] == 0
        assert "Frame offsets are ignored for webcams." in caplog.messages
        assert params["shutter_speed"] is None
        assert params["binning"] == 1
        assert params["external_trigger"] is False
        assert f"Webcam ignores unsupported settings: {', '.join(UNSUPPORTED_CONTROLS)}." in caplog.messages

    service = SimpleNamespace(setup=setup)
    monkeypatch.setattr(GCM, "make", lambda *args, **kwargs: service)
    defaults = {"serializer": "pickle", "host": "localhost", "python_exe": "python", "savefolder": tmp_path}
    prot = {"GCM": {"cam_type": "Webcam", "frame_offy": 20, **UNSUPPORTED_CONTROLS}}
    GCM.setup_client("GCM", 0, prot, defaults, None, "preview", True, False)


def test_webcam_neutral_controls_are_silent(caplog):
    params = {"frame_offx": 0, "shutter_speed": None, "binning": 1, "gamma": 1, "external_trigger": False}
    Webcam.ignore_unsupported_settings(params)
    assert not caplog.messages
