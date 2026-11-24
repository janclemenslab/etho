"""Local hardware discovery shared by services and the command line."""

from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class HardwareDevice:
    name: str
    protocol: Mapping[str, str | int] = field(default_factory=dict)
    details: str = ""


HardwareProbe = Callable[[], Iterable[HardwareDevice]]


@dataclass(frozen=True)
class HardwareDiscovery:
    service: str
    probe: str | None = None
    devices: tuple[HardwareDevice, ...] = ()
    error: Exception | None = None


def discover_hardware(*, ble_duration: float = 10.0) -> Iterator[HardwareDiscovery]:
    """Run each registered service's local probes independently."""
    from . import SERVICE_IMPORT_ERRORS, SERVICE_REGISTRY

    for name in sorted(SERVICE_REGISTRY.keys() | SERVICE_IMPORT_ERRORS.keys()):
        if name not in SERVICE_REGISTRY:
            yield HardwareDiscovery(name, error=SERVICE_IMPORT_ERRORS[name])
            continue

        try:
            probes = SERVICE_REGISTRY[name].hardware_probes(ble_duration=ble_duration)
        except Exception as exc:
            yield HardwareDiscovery(name, error=exc)
            continue

        for label, probe in probes.items():
            try:
                devices = tuple(probe())
            except Exception as exc:
                yield HardwareDiscovery(name, label, error=exc)
            else:
                yield HardwareDiscovery(name, label, devices)
