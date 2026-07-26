"""EXT-1 HDF5 input interface skeleton."""

from deskmate.config.schema import Hdf5InputConfig, SensorConfig
from deskmate.core.enums import SourceStatus
from deskmate.core.types import EventBatch
from deskmate.ui.labels import HDF5_NOT_IMPLEMENTED_JA

from .base import EventSource


class Hdf5EventSource(EventSource):
    """Future Metavision HDF5 source; conversion to canonical NPZ is preferred."""

    def __init__(self, config: Hdf5InputConfig, sensor: SensorConfig) -> None:
        self._config = config
        self._sensor = sensor
        self._status = SourceStatus.IDLE

    @property
    def name(self) -> str:
        """Return the implementation name."""
        return "hdf5"

    @property
    def status(self) -> SourceStatus:
        """Return source state."""
        return self._status

    def open(self) -> None:
        """Raise because EXT-1 is intentionally not implemented."""
        raise NotImplementedError(HDF5_NOT_IMPLEMENTED_JA)

    def read(self, timeout_s: float) -> EventBatch | None:
        """Raise because EXT-1 is intentionally not implemented."""
        raise NotImplementedError("EXT-1")

    def close(self) -> None:
        """Mark the skeleton source closed."""
        self._status = SourceStatus.CLOSED
