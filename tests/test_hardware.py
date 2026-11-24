import sys
from datetime import datetime
from types import SimpleNamespace

import pytest

from etho import cli, services
from etho.services import GOVZeroService
from etho.services.camera import basler, hamamatsu, spinnaker, ximea
from etho.services.hardware import HardwareDevice


def test_hardware_lists_devices_and_reports_independent_failures(monkeypatch, capsys):
    class CameraService:
        @classmethod
        def hardware_probes(cls, *, ble_duration):
            def failed_camera():
                raise OSError("camera SDK failed")

            return {
                "Basler": failed_camera,
                "Spinnaker": tuple,
                "Webcam": lambda: [HardwareDevice("Desk camera", {"cam_type": "Webcam", "cam_serialnumber": 0})],
            }

    async def scan_govee(duration):
        assert duration == 2.5
        measurement = GOVZeroService.H5075Measurement(datetime.now(), 21.2, 47.5)
        return [("AA:BB:CC:DD:EE:FF", "Desk sensor", measurement)]

    monkeypatch.setattr(services, "SERVICE_REGISTRY", {"GCM": CameraService, "GOV": services.GOV})
    monkeypatch.setattr(services, "SERVICE_IMPORT_ERRORS", {"DAQ": ImportError("driver failed")})
    monkeypatch.setattr(GOVZeroService, "discover_h5075_sensors", scan_govee)
    cli.hardware(ble_duration=2.5)

    output = capsys.readouterr().out
    assert "DAQ: unavailable (driver failed)" in output
    assert "GCM / Basler: unavailable (camera SDK failed)" in output
    assert "GCM / Spinnaker: no devices found" in output
    assert "Desk camera  (cam_type=Webcam, cam_serialnumber=0)" in output
    assert "Desk sensor  (address=AA:BB:CC:DD:EE:FF, 21.2°C, 47.5% RH)" in output


def test_nidaq_probe_reports_device_names_and_models(monkeypatch):
    def write_text(text, buffer, size):
        if buffer is None:
            assert size == 0
            return len(text) + 1
        assert size == len(text) + 1
        buffer.value = text
        return 0

    models = {b"Dev1": b"USB-6211", b"cDAQ1Mod1": b"NI 9263"}
    functions = SimpleNamespace(
        DAQmxGetSysDevNames=lambda buffer, size: write_text(b"Dev1, cDAQ1Mod1", buffer, size),
        DAQmxGetDevProductType=lambda name, buffer, size: write_text(models[name], buffer, size),
    )
    monkeypatch.setitem(sys.modules, "PyDAQmx.DAQmxFunctions", functions)

    discover = services.DAQ.hardware_probes(ble_duration=10)["NI-DAQmx"]
    assert list(discover()) == [
        HardwareDevice("USB-6211", {"device": "Dev1"}),
        HardwareDevice("NI 9263", {"device": "cDAQ1Mod1"}),
    ]


def test_dlp_probe_filters_usb_devices_without_opening_them(monkeypatch):
    def find(**filters):
        assert filters == {"find_all": True, "idVendor": 0x0451, "idProduct": 0x6401}
        return iter([SimpleNamespace(bus=1, address=3), SimpleNamespace(bus=1, address=6)])

    monkeypatch.setitem(sys.modules, "usb.core", SimpleNamespace(find=find))

    discover = services.DLP.hardware_probes(ble_duration=10)["LightCrafter 4500"]
    assert list(discover()) == [
        HardwareDevice("TI LightCrafter 4500", details="USB bus 1, address 3"),
        HardwareDevice("TI LightCrafter 4500", details="USB bus 1, address 6"),
    ]


@pytest.mark.parametrize("read_fails", [False, True])
def test_spinnaker_probe_releases_sdk_resources(monkeypatch, read_fails):
    calls = []

    def get_node(name):
        if read_fails:
            raise RuntimeError("camera disconnected")
        return SimpleNamespace(GetValue=lambda: {"DeviceSerialNumber": "123", "DeviceModelName": "Blackfly S"}[name])

    camera = SimpleNamespace(GetTLDeviceNodeMap=lambda: SimpleNamespace(GetNode=get_node))
    cameras = SimpleNamespace(GetSize=lambda: 1, GetByIndex=lambda _: camera, Clear=lambda: calls.append("clear"))
    system = SimpleNamespace(GetCameras=lambda: cameras, ReleaseInstance=lambda: calls.append("release"))
    sdk = SimpleNamespace(System=SimpleNamespace(GetInstance=lambda: system), CStringPtr=lambda node: node, IsReadable=lambda _: True)
    monkeypatch.setattr(spinnaker, "PySpin", sdk, raising=False)
    monkeypatch.setattr(spinnaker, "pyspin_error", None)

    if read_fails:
        with pytest.raises(RuntimeError, match="camera disconnected"):
            spinnaker.Spinnaker.enumerate_devices()
    else:
        assert spinnaker.Spinnaker.enumerate_devices() == [("123", "Blackfly S")]
    assert calls == ["clear", "release"]


def test_camera_sdk_probes_use_protocol_identifiers(monkeypatch):
    basler_device = SimpleNamespace(GetSerialNumber=lambda: "0132", GetModelName=lambda: "acA1300")
    factory = SimpleNamespace(EnumerateDevices=lambda: [basler_device])
    monkeypatch.setattr(basler, "pylon_error", None)
    monkeypatch.setattr(basler, "py", SimpleNamespace(TlFactory=SimpleNamespace(GetInstance=lambda: factory)), raising=False)
    monkeypatch.setattr(hamamatsu, "hamamatsu_error", None)
    monkeypatch.setattr(hamamatsu, "DCAM", SimpleNamespace(get_cameras_number=lambda: 2), raising=False)

    def ximea_camera(dev_id=0):
        info = {"device_sn": f"X{dev_id}".encode(), "device_name": b"xiQ"}
        return SimpleNamespace(get_number_devices=lambda: 2, get_device_info_string=info.__getitem__)

    monkeypatch.setattr(ximea, "ximea_error", None)
    monkeypatch.setattr(ximea, "xiapi", SimpleNamespace(Camera=ximea_camera), raising=False)

    probes = services.GCM.hardware_probes(ble_duration=10)
    assert list(probes["Basler"]()) == [HardwareDevice("acA1300", {"cam_type": "Basler", "cam_serialnumber": "0132"})]
    assert [device.protocol["cam_serialnumber"] for device in probes["Hamamatsu"]()] == [0, 1]
    assert [device.protocol["cam_serialnumber"] for device in probes["Ximea"]()] == ["X0", "X1"]
    assert "Dummy" not in probes
