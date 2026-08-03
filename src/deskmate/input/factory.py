"""Construct input sources from validated configuration."""

import importlib.util
from collections.abc import Callable

from deskmate.config.schema import InputConfig, SensorConfig
from deskmate.core.enums import SourceKind
from deskmate.core.errors import ConfigError

from .base import EventSource
from .dummy_source import DummyEventSource
from .file_source import FileEventSource
from .hdf5_source import Hdf5EventSource
from .metavision_source import MetavisionEventSource
from .udp_source import UdpEventSource


def resolve_source_kind(configured: SourceKind) -> tuple[SourceKind, str]:
    """Resolve AUTO without importing platform-specific Metavision modules."""

    if configured is not SourceKind.AUTO:
        return configured, "explicit selection"
    try:
        available = importlib.util.find_spec("metavision_core") is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        available = False
    if available:
        return SourceKind.METAVISION, "AUTO: Metavision SDK detected"
    return SourceKind.DUMMY, "AUTO: SDK unavailable; DUMMY MODE"


def _dummy(config: InputConfig, sensor: SensorConfig) -> EventSource:
    return DummyEventSource(config.dummy, sensor)


def _file(config: InputConfig, sensor: SensorConfig) -> EventSource:
    return FileEventSource(config.file, sensor)


def _hdf5(config: InputConfig, sensor: SensorConfig) -> EventSource:
    return Hdf5EventSource(config.hdf5, sensor)


def _metavision(config: InputConfig, sensor: SensorConfig) -> EventSource:
    return MetavisionEventSource(config.metavision, sensor)


def _udp(config: InputConfig, sensor: SensorConfig) -> EventSource:
    del sensor
    return UdpEventSource(config.udp)


SOURCE_REGISTRY: dict[
    SourceKind, Callable[[InputConfig, SensorConfig], EventSource]
] = {
    SourceKind.METAVISION: _metavision,
    SourceKind.REPLAY: _file,
    SourceKind.DUMMY: _dummy,
    SourceKind.FILE: _file,
    SourceKind.HDF5: _hdf5,
    SourceKind.UDP: _udp,
}


def create_event_source(config: InputConfig, sensor: SensorConfig) -> EventSource:
    """Create the selected source and retain its visible resolution reason."""

    resolved, reason = resolve_source_kind(config.source)
    factory = SOURCE_REGISTRY.get(resolved)
    if factory is None:
        raise ConfigError(f"unsupported input source: {resolved.value}")
    source = factory(config, sensor)
    source.resolution_reason = reason  # type: ignore[attr-defined]
    return source
