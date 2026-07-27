"""Independent break-prompt timing tests."""

from conftest import FakeClock
from deskmate.config.loader import load_config
from deskmate.core.enums import DeskStatus, SystemStatus
from deskmate.pipeline.break_tracker import BreakTracker


def _update(
    tracker: BreakTracker,
    clock: FakeClock,
    status: DeskStatus,
    seconds: float,
):
    clock.advance(seconds)
    return tracker.update(status, SystemStatus.RUNNING, seconds, clock.monotonic())


def test_due_after_25_minutes_focused() -> None:
    clock = FakeClock()
    tracker = BreakTracker(load_config().break_prompt, clock)
    assert _update(tracker, clock, DeskStatus.FOCUSED, 1499).break_due is False
    assert _update(tracker, clock, DeskStatus.FOCUSED, 1).break_due is True


def test_short_idle_does_not_reset_focus_streak() -> None:
    clock = FakeClock()
    tracker = BreakTracker(load_config().break_prompt, clock)
    _update(tracker, clock, DeskStatus.FOCUSED, 1000)
    state = _update(tracker, clock, DeskStatus.IDLE, 60)
    assert state.focus_streak_seconds == 1000


def test_three_minutes_non_focus_resets() -> None:
    clock = FakeClock()
    tracker = BreakTracker(load_config().break_prompt, clock)
    _update(tracker, clock, DeskStatus.FOCUSED, 1500)
    state = _update(tracker, clock, DeskStatus.IDLE, 180)
    assert state.focus_streak_seconds == 0
    assert not state.break_due


def test_snooze_reappears_after_five_minutes() -> None:
    clock = FakeClock()
    tracker = BreakTracker(load_config().break_prompt, clock)
    _update(tracker, clock, DeskStatus.FOCUSED, 1500)
    tracker.snooze(clock.monotonic())
    assert not _update(tracker, clock, DeskStatus.FOCUSED, 299).break_due
    assert _update(tracker, clock, DeskStatus.FOCUSED, 1).break_due


def test_acknowledge_resets_streak() -> None:
    clock = FakeClock()
    tracker = BreakTracker(load_config().break_prompt, clock)
    _update(tracker, clock, DeskStatus.FOCUSED, 1500)
    tracker.acknowledge(clock.monotonic())
    assert tracker.state.focus_streak_seconds == 0


def test_prompt_is_suppressed_when_not_running() -> None:
    clock = FakeClock()
    tracker = BreakTracker(load_config().break_prompt, clock)
    state = tracker.update(
        DeskStatus.FOCUSED, SystemStatus.PAUSED, 1500, clock.monotonic()
    )
    assert not state.break_due


def test_demo_scale_shortens_due_time() -> None:
    clock = FakeClock()
    config = load_config({"break": {"demo_scale": 0.02}}).break_prompt
    tracker = BreakTracker(config, clock)
    assert _update(tracker, clock, DeskStatus.FOCUSED, 30).break_due
