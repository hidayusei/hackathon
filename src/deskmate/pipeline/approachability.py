"""Derive privacy-safe approachability from confirmed states only."""

from deskmate.config.schema import ShareConfig
from deskmate.core.clock import Clock
from deskmate.core.enums import Approachability, DeskStatus, SystemStatus

from .duration import DurationTracker


class ApproachabilityResolver:
    """Resolve and hold the secondary shared indicator without feature access."""

    def __init__(self, config: ShareConfig, clock: Clock) -> None:
        self._config = config
        self._clock = clock
        self.reset()

    def reset(self) -> None:
        """Reset held result."""
        self._current = Approachability.UNDETERMINED
        self._changed_at = self._clock.monotonic()

    def _candidate(
        self,
        status: DeskStatus,
        system_status: SystemStatus,
        duration: float,
        confidence: float,
        tracker: DurationTracker,
        now: float,
    ) -> Approachability:
        c = self._config
        if system_status is not SystemStatus.RUNNING or confidence < c.min_confidence:
            return Approachability.UNDETERMINED
        if status in {DeskStatus.NO_MOTION, DeskStatus.UNKNOWN, DeskStatus.TRANSITION}:
            return Approachability.UNDETERMINED
        if status is DeskStatus.SHORT_BREAK and duration >= c.approachable_after_break_seconds:
            return Approachability.LIKELY_OK
        if status is DeskStatus.WORKING and tracker.had_status_within(
            {DeskStatus.FOCUSED, DeskStatus.ORGANIZING},
            c.recent_busy_lookback_seconds,
            now,
            exclude_current=True,
        ):
            return Approachability.LIKELY_OK
        if (
            status in {DeskStatus.FOCUSED, DeskStatus.ORGANIZING}
            and duration >= c.prefer_later_min_seconds
        ):
            return Approachability.PREFER_LATER
        return Approachability.UNDETERMINED

    def resolve(
        self,
        status: DeskStatus,
        system_status: SystemStatus,
        duration_seconds: float,
        confidence: float,
        tracker: DurationTracker,
        now: float,
    ) -> Approachability:
        """Return the held or newly resolved secondary indicator."""
        candidate = self._candidate(
            status, system_status, duration_seconds, confidence, tracker, now
        )
        if candidate is Approachability.UNDETERMINED:
            if self._current is not candidate:
                self._changed_at = now
            self._current = candidate
        elif candidate is not self._current and now - self._changed_at >= self._config.min_hold_seconds:
            self._current = candidate
            self._changed_at = now
        return self._current
