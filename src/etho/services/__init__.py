import logging
import re
from typing import Dict, Type

from .ZeroService import BaseZeroService


SERVICE_REGISTRY: Dict[str, Type[BaseZeroService]] = {}
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
        available = ", ".join(sorted(SERVICE_REGISTRY))
        raise ValueError(f"Unknown service '{service_name}'. Available services: {available}.")


from .DLPZeroService import DLP
from .BLTZeroService import BLT
from .GOVZeroService import GOV
from .GCMZeroService import GCM
from .DAQZeroService import DAQ
from .NICounterZeroService import NIC
from .ScanImageTriggerZeroService import SIT


__all__ = [
    "SERVICE_REGISTRY",
    "service_base_name",
    "service_class_for",
    "GOV",
    "GCM",
    "DAQ",
    "DLP",
    "BLT",
    "SIT",
]
