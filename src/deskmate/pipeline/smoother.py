"""Vote, dwell, and confidence smoothing for three states."""

from collections import Counter, deque
from dataclasses import dataclass
import math

from deskmate.config.schema import SmoothingConfig
from deskmate.core.clock import Clock
from deskmate.core.enums import DeskStatus
from deskmate.core.types import StatusEstimate


@dataclass(frozen=True, slots=True)
class SmoothingResult:
    """One smoothing decision."""

    status: DeskStatus
    changed: bool
    confidence: float
    vote_count: int
    candidate: DeskStatus


_PRIORITY = {
    DeskStatus.AWAY: 0,
    DeskStatus.FOCUSED: 1,
    DeskStatus.IDLE: 2,
}


class StatusSmoother:
    """Stabilize per-window estimates into a confirmed status."""

    def __init__(self, config: SmoothingConfig, clock: Clock) -> None:
        self._config = config
        self._clock = clock
        self.reset()

    def reset(self, status: DeskStatus = DeskStatus.IDLE) -> None:
        """Reset state and vote buffer."""

        self._current = status
        self._votes: deque[StatusEstimate] = deque(maxlen=self._config.vote_window_size)
        self._changed_at = self._clock.monotonic()
        self._last_update = self._changed_at
        self._confidence = 0.0

    @property
    def current(self) -> DeskStatus:
        """Return the confirmed status."""

        return self._current

    def _dwell(self, status: DeskStatus) -> float:
        if status is DeskStatus.AWAY:
            return self._config.min_dwell_seconds.away
        return self._config.min_dwell_seconds.default

    def _change(
        self,
        status: DeskStatus,
        confidence: float,
        now: float,
        vote_count: int,
        candidate: DeskStatus,
    ) -> SmoothingResult:
        changed = self._current is not status
        self._current = status
        self._confidence = confidence
        if changed:
            self._changed_at = now
            self._votes.clear()
        return SmoothingResult(status, changed, confidence, vote_count, candidate)

    def update(
        self,
        estimate: StatusEstimate,
        now: float,
        force_away: bool = False,
    ) -> SmoothingResult:
        """Update smoothing and return the confirmed result."""

        dt = max(0.0, now - self._last_update)
        self._last_update = now
        alpha = 1.0 - math.exp(-dt / self._config.confidence_ema_seconds)
        target = estimate.confidence if estimate.status is self._current else 0.0
        self._confidence += alpha * (target - self._confidence)
        self._votes.append(estimate)

        if force_away:
            return self._change(
                DeskStatus.AWAY,
                estimate.confidence,
                now,
                1,
                estimate.status,
            )

        if (
            self._current is DeskStatus.AWAY
            and estimate.status is not DeskStatus.AWAY
        ):
            return self._change(
                DeskStatus.IDLE,
                estimate.confidence,
                now,
                1,
                estimate.status,
            )

        if len(self._votes) < self._config.vote_window_size:
            return SmoothingResult(
                self._current, False, self._confidence, 0, estimate.status
            )

        counts = Counter(vote.status for vote in self._votes)
        top = min(counts, key=lambda status: (-counts[status], _PRIORITY[status]))
        vote_count = counts[top]
        confidence = (
            sum(vote.confidence for vote in self._votes if vote.status is top)
            / vote_count
        )
        if top is self._current:
            return SmoothingResult(
                self._current, False, self._confidence, vote_count, top
            )

        minimum_votes = (
            self._config.vote_min_count - 1
            if self._confidence < self._config.exit_confidence
            else self._config.vote_min_count
        )
        can_change = (
            now - self._changed_at >= self._dwell(self._current)
            and vote_count >= minimum_votes
            and confidence >= self._config.enter_confidence
        )
        if can_change:
            return self._change(top, confidence, now, vote_count, top)
        return SmoothingResult(
            self._current, False, self._confidence, vote_count, top
        )
