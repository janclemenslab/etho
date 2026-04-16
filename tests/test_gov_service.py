from datetime import datetime
import sys
import threading
import types

if "scipy" not in sys.modules:
    scipy = types.ModuleType("scipy")
    scipy_io = types.ModuleType("scipy.io")
    scipy_io_wavfile = types.ModuleType("scipy.io.wavfile")
    scipy_signal = types.ModuleType("scipy.signal")
    scipy.io = scipy_io
    scipy.signal = scipy_signal
    scipy_io.wavfile = scipy_io_wavfile
    sys.modules["scipy"] = scipy
    sys.modules["scipy.io"] = scipy_io
    sys.modules["scipy.io.wavfile"] = scipy_io_wavfile
    sys.modules["scipy.signal"] = scipy_signal

if "h5py" not in sys.modules:
    sys.modules["h5py"] = types.ModuleType("h5py")

if "defopt" not in sys.modules:
    defopt = types.ModuleType("defopt")
    defopt.run = lambda *args, **kwargs: None
    sys.modules["defopt"] = defopt

if "zerorpc" not in sys.modules:
    zerorpc = types.ModuleType("zerorpc")

    class Context:
        def register_serializer(self, *args, **kwargs):
            return None

    class Server:
        def __init__(self, *args, **kwargs):
            return None

        def bind(self, *args, **kwargs):
            return None

        def run(self, *args, **kwargs):
            return None

        def stop(self, *args, **kwargs):
            return None

    zerorpc.Context = Context
    zerorpc.Server = Server
    sys.modules["zerorpc"] = zerorpc

if "etho.utils.sound" not in sys.modules:
    sound = types.ModuleType("etho.utils.sound")
    sound.parse_table = lambda *args, **kwargs: None
    sound.load_sounds = lambda *args, **kwargs: None
    sound.build_playlist = lambda *args, **kwargs: ([], 0)
    sys.modules["etho.utils.sound"] = sound

if "etho.utils.tui" not in sys.modules:
    tui = types.ModuleType("etho.utils.tui")
    tui.rich_information = lambda *args, **kwargs: None
    sys.modules["etho.utils.tui"] = tui

for module_name, class_name in (
    ("etho.services.ThuAZeroService", "THUA"),
    ("etho.services.DAQZeroService", "DAQ"),
    ("etho.services.GCMZeroService", "GCM"),
    ("etho.services.NICounterZeroService", "NIC"),
):
    if module_name not in sys.modules:
        module = types.ModuleType(module_name)
        setattr(module, class_name, type(class_name, (), {"SERVICE_PORT": None}))
        sys.modules[module_name] = module

import etho.client as client
from etho.services.GOVZeroService import (
    GOV,
    H5075_MANUFACTURER_ID,
    H5075Measurement,
    decode_h5075_measurement,
    format_measurement_log_line,
    normalize_address,
)


def encode_h5075_payload(temperature_c, humidity, battery=0):
    raw = int(round(abs(temperature_c) * 10)) * 1000 + int(round(humidity * 10))
    if temperature_c < 0:
        raw |= 0x800000
    return bytes([0]) + raw.to_bytes(3, byteorder="big") + bytes([battery])


class DummyLogger:
    def __init__(self):
        self.messages = []
        self.handlers = []

    def info(self, message):
        self.messages.append(message)

    def warning(self, message):
        self.messages.append(message)

    def debug(self, message):
        self.messages.append(message)


class DummyDevice:
    def __init__(self, address):
        self.address = address


class DummyAdvertisement:
    def __init__(self, manufacturer_data):
        self.manufacturer_data = manufacturer_data


def make_service(interval=60, address="AA:BB:CC:DD:EE:FF"):
    service = object.__new__(GOV)
    service.log = DummyLogger()
    service.address = normalize_address(address)
    service.interval = interval
    service.measurement = None
    service.data = None
    service._state_lock = threading.Lock()
    service._latest_measurement = None
    service._latest_measurement_seen_at = None
    service._last_logged_measurement_seen_at = None
    service._last_emit_monotonic = None
    return service


def test_decode_h5075_measurement():
    measurement = decode_h5075_measurement(encode_h5075_payload(21.9, 63.1), datetime(2024, 1, 2, 3, 4, 5))
    assert measurement.temperature_c == 21.9
    assert measurement.humidity == 63.1
    assert format_measurement_log_line(measurement) == "2024-01-02 03:04:05,21.9,63.1"

    negative = decode_h5075_measurement(encode_h5075_payload(-5.4, 42.0))
    assert negative.temperature_c == -5.4
    assert negative.humidity == 42.0


def test_detection_callback_filters_by_address():
    service = make_service()
    payload = encode_h5075_payload(19.8, 47.5)

    service._detection_callback(
        DummyDevice("11:22:33:44:55:66"),
        DummyAdvertisement({H5075_MANUFACTURER_ID: payload}),
    )

    assert service.measurement is None
    assert service.log.messages == []

    service._detection_callback(
        DummyDevice("aa:bb:cc:dd:ee:ff"),
        DummyAdvertisement({H5075_MANUFACTURER_ID: payload}),
    )

    assert service.measurement.temperature_c == 19.8
    assert service.measurement.humidity == 47.5
    assert service.log.messages
    assert service.log.messages[-1].endswith(",19.8,47.5")


def test_logging_is_throttled_by_interval():
    service = make_service(interval=60)

    first = H5075Measurement(datetime(2024, 1, 1, 12, 0, 0), 21.9, 63.1)
    second = H5075Measurement(datetime(2024, 1, 1, 12, 0, 30), 22.0, 64.0)

    service._record_measurement(first, seen_at=0)
    service._maybe_log_latest_measurement(now_monotonic=0)
    assert service.log.messages == ["2024-01-01 12:00:00,21.9,63.1"]

    service._record_measurement(second, seen_at=30)
    service._maybe_log_latest_measurement(now_monotonic=30)
    assert service.log.messages == ["2024-01-01 12:00:00,21.9,63.1"]

    service._maybe_log_latest_measurement(now_monotonic=61)
    assert service.log.messages == [
        "2024-01-01 12:00:00,21.9,63.1",
        "2024-01-01 12:00:30,22.0,64.0",
    ]


def test_client_wires_gov_service(monkeypatch):
    class FakeRemoteService:
        def __init__(self):
            self.setup_args = None
            self.log_path = None
            self.started = False

        def setup(self, address, interval, duration):
            self.setup_args = (address, interval, duration)

        def init_local_logger(self, path):
            self.log_path = path

        def information(self):
            return {}

        def start(self):
            self.started = True

    class FakeGOV:
        SERVICE_PORT = 4255
        last_instance = None

        @classmethod
        def make(cls, serializer, user, host, python_exe, port=None):
            instance = FakeRemoteService()
            instance.make_args = (serializer, user, host, python_exe, port)
            cls.last_instance = instance
            return instance

    monkeypatch.setattr(client, "GOV", FakeGOV)
    monkeypatch.setattr(client, "rich_information", lambda *args, **kwargs: None)

    protocol = {
        "maxduration": 5,
        "use_services": ["GOV"],
        "GOV": {
            "address": "AA:BB:CC:DD:EE:FF",
        },
    }

    services = client.client(None, protocol=protocol, save_prefix="testgov", show_progress=False)

    service = FakeGOV.last_instance
    assert services["GOV"] is service
    assert service.make_args[-1] == FakeGOV.SERVICE_PORT
    assert service.setup_args == ("AA:BB:CC:DD:EE:FF", 60, 15)
    assert service.started is True
    assert service.log_path.endswith("testgov/testgov_gov.log")
