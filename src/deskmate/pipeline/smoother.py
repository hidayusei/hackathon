"""Vote, dwell, confidence, and transition smoothing."""

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


TRANSITION_TABLE: dict[DeskStatus, frozenset[DeskStatus]] = {
    DeskStatus.FOCUSED: frozenset(set(DeskStatus) - {DeskStatus.FOCUSED}),
    DeskStatus.WORKING: frozenset(set(DeskStatus) - {DeskStatus.WORKING}),
    DeskStatus.ORGANIZING: frozenset(
        set(DeskStatus) - {DeskStatus.ORGANIZING, DeskStatus.FOCUSED}
    ),
    DeskStatus.SHORT_BREAK: frozenset(
        set(DeskStatus) - {DeskStatus.SHORT_BREAK, DeskStatus.FOCUSED}
    ),
    DeskStatus.TRANSITION: frozenset(set(DeskStatus) - {DeskStatus.TRANSITION}),
    DeskStatus.NO_MOTION: frozenset(
        set(DeskStatus)
        - {DeskStatus.NO_MOTION, DeskStatus.FOCUSED, DeskStatus.ORGANIZING}
    ),
    DeskStatus.UNKNOWN: frozenset(set(DeskStatus) - {DeskStatus.UNKNOWN}),
}
_PRIORITY = {
    status: index
    for index, status in enumerate(
        (
            DeskStatus.NO_MOTION,
            DeskStatus.TRANSITION,
            DeskStatus.ORGANIZING,
            DeskStatus.FOCUSED,
            DeskStatus.SHORT_BREAK,
            DeskStatus.WORKING,
            DeskStatus.UNKNOWN,
        )
    )
}


class StatusSmoother:
    """Stabilize per-window estimates into a confirmed status."""

    def __init__(
        self,
        config: SmoothingConfig,
        clock: Clock,
        transition_max_seconds: float = 6.0,
    ) -> None:
        self._config = config
        self._clock = clock
        self._transition_max_seconds = transition_max_seconds
        self.reset()

    def reset(self, status: DeskStatus = DeskStatus.UNKNOWN) -> None:
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

    @staticmethod
    def is_transition_allowed(src: DeskStatus, dst: DeskStatus) -> bool:
        """Return whether the canonical transition table permits the edge."""
        return dst in TRANSITION_TABLE[src]

    def _dwell(self, status: DeskStatus) -> float:
        dwell = self._config.min_dwell_seconds
        return {
            DeskStatus.TRANSITION: dwell.transition,
            DeskStatus.NO_MOTION: dwell.no_motion,
            DeskStatus.UNKNOWN: dwell.unknown,
        }.get(status, dwell.default)

    def update(
        self, estimate: StatusEstimate, now: float, force_no_motion: bool = False
    ) -> SmoothingResult:
        """Update smoothing and return the confirmed result."""
        dt = max(0.0, now - self._last_update)
        self._last_update = now
        alpha = 1 - math.exp(-dt / self._config.confidence_ema_seconds)
        target = estimate.confidence if estimate.status is self._current else 0.0
        self._confidence += alpha * (target - self._confidence)
        self._votes.append(estimate)
        if force_no_motion:
            changed = self._current is not DeskStatus.NO_MOTION
            self._current = DeskStatus.NO_MOTION
            if changed:
                self._changed_at = now
            return SmoothingResult(self._current, changed, estimate.confidence, 1, estimate.status)
        if len(self._votes) < self._config.vote_window_size:
            return SmoothingResult(self._current, False, self._confidence, 0, estimate.status)
        candidates = list(self._votes)
        force_transition_exit = (
            self._current is DeskStatus.TRANSITION
            and now - self._changed_at > self._transition_max_seconds
        )
        if force_transition_exit:
            candidates = [vote for vote in candidates if vote.status is not DeskStatus.TRANSITION]
            if not candidates:
                candidates = [StatusEstimate(DeskStatus.UNKNOWN, 0.5, "forced", "timeout")]
        counts = Counter(vote.status for vote in candidates)
        top = min(counts, key=lambda status: (-counts[status], _PRIORITY[status]))
        vote_count = counts[top]
        confidence = sum(v.confidence for v in candidates if v.status is top) / vote_count
        if top is self._current:
            # The per-window EMA above already advanced this tick; applying it twice
            # would halve the configured confidence_ema_seconds time constant.
            return SmoothingResult(self._current, False, self._confidence, vote_count, top)
        minimum_votes = (
            self._config.vote_min_count - 1
            if self._confidence < self._config.exit_confidence
            else self._config.vote_min_count
        )
        can_change = self.is_transition_allowed(self._current, top) and (
            force_transition_exit
            or (
                now - self._changed_at >= self._dwell(self._current)
                and vote_count >= minimum_votes
                and confidence >= self._config.enter_confidence
            )
        )
        if can_change:
            self._current = top
            self._changed_at = now
            self._confidence = confidence
        return SmoothingResult(self._current, can_change, self._confidence, vote_count, top)
