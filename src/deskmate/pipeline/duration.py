"""Confirmed-state duration and bounded history."""

from deskmate.core.enums import DeskStatus
from deskmate.core.types import HistoryEntry


class DurationTracker:
    """Track current duration and a bounded, expiring state history."""

    def __init__(
        self,
        history_limit: int = 200,
        history_retention_minutes: float = 60.0,
    ) -> None:
        self._limit = history_limit
        self._retention_seconds = history_retention_minutes * 60
        self.reset()

    def reset(self) -> None:
        """Clear current and historical state."""
        self._entries: list[HistoryEntry] = []
        self._current: HistoryEntry | None = None
        self._duration = 0.0

    def _prune(self, now: float) -> None:
        cutoff = now - self._retention_seconds
        self._entries = [
            entry
            for entry in self._entries
            if entry.ended_monotonic is None or entry.ended_monotonic >= cutoff
        ][-self._limit :]

    def update(
        self,
        status: DeskStatus,
        changed: bool,
        confidence: float,
        now: float,
    ) -> float:
        """Update the current state and return its duration in seconds."""
        if self._current is None:
            self._current = HistoryEntry(status, now, None, confidence)
        elif changed or status is not self._current.status:
            self._entries.append(
                HistoryEntry(
                    self._current.status,
                    self._current.started_monotonic,
                    now,
                    max(self._current.peak_confidence, confidence),
                )
            )
            self._current = HistoryEntry(status, now, None, confidence)
        elif confidence > self._current.peak_confidence:
            self._current = HistoryEntry(
                status, self._current.started_monotonic, None, confidence
            )
        self._duration = max(0.0, now - self._current.started_monotonic)
        self._prune(now)
        return self._duration

    @property
    def current_duration(self) -> float:
        """Return the most recently calculated duration."""
        return self._duration

    @property
    def history(self) -> list[HistoryEntry]:
        """Return entries in ascending start-time order, including current."""
        return [*self._entries, *([self._current] if self._current else [])]

    def recent(self, seconds: float, now: float) -> list[HistoryEntry]:
        """Return entries intersecting the recent interval."""
        cutoff = now - seconds
        return [
            entry
            for entry in self.history
            if (entry.ended_monotonic if entry.ended_monotonic is not None else now) >= cutoff
        ]

    def had_status_within(
        self,
        statuses: set[DeskStatus],
        seconds: float,
        now: float,
        exclude_current: bool = True,
    ) -> bool:
        """Return whether a selected status occurred in the recent interval."""
        entries = self._entries if exclude_current else self.history
        cutoff = now - seconds
        return any(
            entry.status in statuses
            and (entry.ended_monotonic if entry.ended_monotonic is not None else now) >= cutoff
            for entry in entries
        )
