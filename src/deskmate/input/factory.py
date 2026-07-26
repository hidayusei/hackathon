"""Construct input sources from validated configuration."""

from collections.abc import Callable

from deskmate.config.schema import InputConfig, SensorConfig
from deskmate.core.enums import SourceKind
from deskmate.core.errors import ConfigError

from .base import EventSource
from .dummy_source import DummyEventSource
from .file_source import FileEventSource
from .hdf5_source import Hdf5EventSource


def _dummy(config: InputConfig, sensor: SensorConfig) -> EventSource:
    return DummyEventSource(config.dummy, sensor)


def _file(config: InputConfig, sensor: SensorConfig) -> EventSource:
    if config.file.path is None:
        raise ConfigError("input.file.path is required")
    return FileEventSource(config.file, sensor)


def _hdf5(config: InputConfig, sensor: SensorConfig) -> EventSource:
    if config.hdf5.path is None:
        raise ConfigError("input.hdf5.path is required")
    return Hdf5EventSource(config.hdf5, sensor)


SOURCE_REGISTRY: dict[
    SourceKind, Callable[[InputConfig, SensorConfig], EventSource]
] = {
    SourceKind.DUMMY: _dummy,
    SourceKind.FILE: _file,
    SourceKind.HDF5: _hdf5,
}


def create_event_source(config: InputConfig, sensor: SensorConfig) -> EventSource:
    """Create the selected source or raise ConfigError if it is unavailable."""
    factory = SOURCE_REGISTRY.get(config.source)
    if factory is None:
        raise ConfigError(f"unsupported input source: {config.source.value}")
    return factory(config, sensor)
