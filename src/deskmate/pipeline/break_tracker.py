"""Independent focused-streak and break-prompt tracking."""

from dataclasses import dataclass

from deskmate.config.schema import BreakConfig
from deskmate.core.clock import Clock
from deskmate.core.enums import DeskStatus, SystemStatus


@dataclass(frozen=True, slots=True)
class BreakState:
    """Current break-prompt state."""

    focus_streak_seconds: float
    break_due: bool
    snoozed_until: float | None


class BreakTracker:
    """Track focused time without adding another inferred desk state."""

    def __init__(self, config: BreakConfig, clock: Clock) -> None:
        self._config = config
        self._clock = clock
        self.reset()

    @property
    def state(self) -> BreakState:
        """Return an immutable state snapshot."""

        return BreakState(
            self._focus_streak_seconds,
            self._break_due,
            self._snoozed_until,
        )

    def reset(self) -> None:
        """Clear focused time and prompt state."""

        self._focus_streak_seconds = 0.0
        self._non_focus_seconds = 0.0
        self._break_due = False
        self._snoozed_until: float | None = None

    def update(
        self,
        status: DeskStatus,
        system_status: SystemStatus,
        window_seconds: float,
        now: float,
    ) -> BreakState:
        """Update the focused streak for one processed window."""

        if not self._config.enabled:
            self._break_due = False
            return self.state

        duration = max(0.0, window_seconds)
        if status is DeskStatus.FOCUSED:
            self._focus_streak_seconds += duration
            self._non_focus_seconds = 0.0
        else:
            self._non_focus_seconds += duration
            reset_after = self._config.reset_seconds * self._config.demo_scale
            if self._non_focus_seconds >= reset_after:
                self._focus_streak_seconds = 0.0
                self._non_focus_seconds = 0.0
                self._break_due = False
                self._snoozed_until = None

        snoozed = self._snoozed_until is not None and now < self._snoozed_until
        due_after = self._config.after_seconds * self._config.demo_scale
        self._break_due = (
            system_status is SystemStatus.RUNNING
            and status is DeskStatus.FOCUSED
            and self._focus_streak_seconds >= due_after
            and not snoozed
        )
        return self.state

    def snooze(self, now: float) -> None:
        """Hide the prompt until the configured monotonic time."""

        self._snoozed_until = now + self._config.snooze_seconds
        self._break_due = False

    def acknowledge(self, now: float) -> None:
        """Acknowledge a break and reset the focused streak."""

        del now
        self.reset()
