from importlib import import_module
import re
from typing import Dict, Type

from .ZeroService import BaseZeroService


SERVICE_REGISTRY: Dict[str, Type[BaseZeroService]] = {}
SERVICE_IMPORT_ERRORS: dict[str, Exception] = {}
_SUFFIX_RE = re.compile(r"\d+$")


def service_base_name(service_name: str) -> str:
    """Return the unsuffixed service name used for class lookup."""
    return _SUFFIX_RE.sub("", service_name)


def register_service(cls: Type[BaseZeroService]) -> Type[BaseZeroService]:
    """Register a protocol-runnable service class."""
    SERVICE_REGISTRY[cls.SERVICE_NAME] = cls
    return cls


def service_class_for(service_name: str) -> Type[BaseZeroService]:
    """Return the service class for a protocol service key."""
    base_name = service_base_name(service_name)
    try:
        return SERVICE_REGISTRY[base_name]
    except KeyError:
        if base_name in SERVICE_IMPORT_ERRORS:
            error = SERVICE_IMPORT_ERRORS[base_name]
            raise ValueError(f"Could not load service '{base_name}': {error}") from error
        available = ", ".join(sorted(SERVICE_REGISTRY))
        raise ValueError(f"Unknown service '{service_name}'. Available services: {available}.")


def _load_builtin_services():
    modules = {
        "DLP": ".DLPZeroService",
        "BLT": ".BLTZeroService",
        "GOV": ".GOVZeroService",
        "GCM": ".GCMZeroService",
        "DAQ": ".DAQZeroService",
        "NIC": ".NICounterZeroService",
        "SIT": ".ScanImageTriggerZeroService",
    }
    for name, module in modules.items():
        try:
            globals()[name] = getattr(import_module(module, __name__), name)
        except Exception as exc:
            SERVICE_REGISTRY.pop(name, None)
            SERVICE_IMPORT_ERRORS[name] = exc


_load_builtin_services()


__all__ = [
    "SERVICE_REGISTRY",
    "service_base_name",
    "service_class_for",
    *(name for name in ("GOV", "GCM", "DAQ", "DLP", "BLT", "SIT") if name in SERVICE_REGISTRY),
]
