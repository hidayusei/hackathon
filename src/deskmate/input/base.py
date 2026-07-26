"""The sole contract implemented by every event input."""

import abc

from deskmate.core.enums import SourceStatus
from deskmate.core.types import EventBatch


class EventSource(abc.ABC):
    """Abstract event source used only from the acquisition thread."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Return a human-readable source name."""

    @property
    @abc.abstractmethod
    def status(self) -> SourceStatus:
        """Return the source lifecycle state."""

    @abc.abstractmethod
    def open(self) -> None:
        """Open the source; implementations must be idempotent."""

    @abc.abstractmethod
    def read(self, timeout_s: float) -> EventBatch | None:
        """Return one event batch or None on timeout."""

    @abc.abstractmethod
    def close(self) -> None:
        """Release resources without raising."""

    def request_stop(self) -> None:
        """Request interruption of a blocking read."""

    def reset(self) -> None:
        """Close and reopen the source."""
        self.close()
        self.open()

    @property
    def supports_seek(self) -> bool:
        """Return whether seek is supported."""
        return False
