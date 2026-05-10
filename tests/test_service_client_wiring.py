import pytest

import etho.client as client
from etho import services as service_module


def test_service_registry_resolves_suffixed_names():
    assert service_module.SERVICE_REGISTRY["GOV"].SERVICE_NAME == "GOV"
    assert service_module.SERVICE_REGISTRY["GCM"].SERVICE_NAME == "GCM"
    assert service_module.SERVICE_REGISTRY["DAQ"].SERVICE_NAME == "DAQ"
    assert service_module.SERVICE_REGISTRY["NIC"].SERVICE_NAME == "NIC"
    assert service_module.SERVICE_REGISTRY["SIT"].SERVICE_NAME == "SIT"
    assert service_module.service_class_for("GCM2").SERVICE_NAME == "GCM"

    with pytest.raises(ValueError, match="Unknown service"):
        service_module.service_class_for("NOPE")


def test_register_service_decorator_adds_class(monkeypatch):
    registry = {}
    monkeypatch.setattr(service_module, "SERVICE_REGISTRY", registry)

    @service_module.register_service
    class FakeService:
        SERVICE_NAME = "FAK"

    assert registry == {"FAK": FakeService}


def test_client_uses_service_owned_setup_and_start_groups(monkeypatch):
    started = []

    class FakeService:
        def __init__(self, name):
            self.name = name

        def information(self):
            return {}

        def progress(self):
            return {"total": 1, "elapsed": 0}

        def start(self):
            started.append(self.name)

    class FakePre:
        SERVICE_NAME = "PRE"
        CLIENT_START_GROUP = "pre"

        @classmethod
        def setup_client(cls, service_key, service_index, prot, defaults, playlistfile, save_prefix, preview, new_console):
            return FakeService(service_key)

    class FakeTrigger:
        SERVICE_NAME = "TRG"
        CLIENT_START_GROUP = "trigger"

        @classmethod
        def setup_client(cls, service_key, service_index, prot, defaults, playlistfile, save_prefix, preview, new_console):
            return FakeService(service_key)

    class FakeDaq:
        SERVICE_NAME = "DAQ"
        CLIENT_START_GROUP = "daq"

        @classmethod
        def setup_client(cls, service_key, service_index, prot, defaults, playlistfile, save_prefix, preview, new_console):
            return FakeService(service_key)

    service_classes = {
        "PRE": FakePre,
        "TRG": FakeTrigger,
        "DAQ": FakeDaq,
    }

    monkeypatch.setattr(client.service_module, "service_class_for", lambda service_name: service_classes[service_name])
    monkeypatch.setattr(client.rich, "print", lambda *args, **kwargs: None)
    monkeypatch.setattr(client, "rich_information", lambda *args, **kwargs: None)
    monkeypatch.setattr(client.time, "sleep", lambda *args, **kwargs: None)

    protocol = {
        "maxduration": 1,
        "use_services": ["DAQ", "PRE", "TRG"],
        "DAQ": {},
        "PRE": {},
        "TRG": {},
    }

    result = client.client(None, protocol=protocol, save_prefix="test", show_progress=False)

    assert list(result) == ["DAQ", "PRE", "TRG"]
    assert started == ["PRE", "TRG", "DAQ"]
