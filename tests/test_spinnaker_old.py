import importlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


spinnaker_old = importlib.import_module("etho.services.camera.spinnaker_old")


@pytest.mark.parametrize("ns_per_tick", [1, 8, 1000])
def test_estimate_offset_uses_legacy_nodes_and_midpoint(monkeypatch, ns_per_tick):
    camera = object.__new__(spinnaker_old.Spinnaker_OLD)
    offset = 1_788_280_000.0
    camera_times = [60_000, 60_001, 60_002]
    ticks = iter([seconds * 1_000_000_000 // ns_per_tick for seconds in camera_times])
    system_times = iter([
        value
        for seconds, delay in zip(camera_times, [0, 0.0002, 0.5])
        for value in [offset + seconds + delay - 0.002, offset + seconds + delay + 0.002]
    ])
    latch = Mock()
    camera.camera_attributes = {
        "Timestamp": SimpleNamespace(GetValue=lambda: next(ticks)),
        "TimestampIncrement": SimpleNamespace(GetValue=lambda: ns_per_tick),
    }
    camera.camera_methods = {"TimestampLatch": SimpleNamespace(Execute=latch)}
    monkeypatch.setattr(spinnaker_old, "PySpin", SimpleNamespace(IsReadable=lambda node: True), raising=False)
    monkeypatch.setattr(spinnaker_old, "time", SimpleNamespace(time=lambda: next(system_times)))

    result = camera._estimate_timestamp_offset(timestamp_offset_iterations=3)

    assert result == pytest.approx(offset + 0.0002, abs=1e-6, rel=0)
    assert latch.call_count == 3


def test_init_enables_offset_estimation(monkeypatch):
    sdk = Mock()
    camera = object.__new__(spinnaker_old.Spinnaker_OLD)
    camera.serialnumber = "123"
    camera._generate_attrs = Mock()
    camera._estimate_timestamp_offset = Mock(return_value=1_788_280_000.0)
    monkeypatch.setattr(spinnaker_old, "PySpin", sdk, raising=False)

    camera.init()

    camera._estimate_timestamp_offset.assert_called_once_with()
    assert camera.timestamp_offset == 1_788_280_000.0


def test_get_adds_offset_to_image_nanoseconds(monkeypatch):
    camera = object.__new__(spinnaker_old.Spinnaker_OLD)
    camera.c = Mock()
    camera.processor = Mock()
    camera.timeout = 1000
    camera.timestamp_offset = 1_788_280_000.0
    image = camera.c.GetNextImage.return_value
    image.IsIncomplete.return_value = False
    image.GetTimeStamp.return_value = 60_000_000_000_000
    monkeypatch.setattr(spinnaker_old, "PySpin", SimpleNamespace(PixelFormat_BGR8=1), raising=False)
    monkeypatch.setattr(spinnaker_old, "time", SimpleNamespace(time=lambda: 1_788_340_000.01))

    _, image_time, system_time = camera.get()

    assert image_time == 1_788_340_000.0
    assert system_time == 1_788_340_000.01
    image.Release.assert_called_once_with()
