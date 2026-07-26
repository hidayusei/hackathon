"""Step 5 state smoothing tests."""

from conftest import FakeClock
from deskmate.config.loader import load_config
from deskmate.core.enums import DeskStatus
from deskmate.core.types import StatusEstimate
from deskmate.pipeline.smoother import StatusSmoother


def _vote(status: DeskStatus, confidence: float = 0.8) -> StatusEstimate:
    return StatusEstimate(status, confidence, status.value, status.value)


def _feed(smoother, clock, status, count=5, confidence=0.8, step=1.0):
    result = None
    for _ in range(count):
        clock.advance(step)
        result = smoother.update(_vote(status, confidence), clock.monotonic())
    return result


def test_five_equal_candidates_confirm_state() -> None:
    clock = FakeClock()
    smoother = StatusSmoother(load_config().smoothing, clock)
    assert _feed(smoother, clock, DeskStatus.WORKING).status is DeskStatus.WORKING


def test_minimum_dwell_blocks_immediate_change() -> None:
    clock = FakeClock()
    smoother = StatusSmoother(load_config().smoothing, clock)
    _feed(smoother, clock, DeskStatus.WORKING)
    result = _feed(smoother, clock, DeskStatus.FOCUSED, step=0.2)
    assert result.status is DeskStatus.WORKING


def test_change_after_dwell() -> None:
    clock = FakeClock()
    smoother = StatusSmoother(load_config().smoothing, clock)
    _feed(smoother, clock, DeskStatus.WORKING)
    clock.advance(4)
    assert _feed(smoother, clock, DeskStatus.FOCUSED).status is DeskStatus.FOCUSED


def test_low_confidence_does_not_enter() -> None:
    clock = FakeClock()
    smoother = StatusSmoother(load_config().smoothing, clock)
    assert _feed(smoother, clock, DeskStatus.WORKING, confidence=0.4).status is DeskStatus.UNKNOWN


def test_forbidden_organizing_to_focused() -> None:
    clock = FakeClock()
    smoother = StatusSmoother(load_config().smoothing, clock)
    _feed(smoother, clock, DeskStatus.ORGANIZING)
    clock.advance(4)
    assert _feed(smoother, clock, DeskStatus.FOCUSED).status is DeskStatus.ORGANIZING


def test_force_no_motion_is_immediate() -> None:
    clock = FakeClock()
    smoother = StatusSmoother(load_config().smoothing, clock)
    result = smoother.update(_vote(DeskStatus.NO_MOTION), 0, force_no_motion=True)
    assert result.status is DeskStatus.NO_MOTION and result.changed


def test_reset_returns_unknown() -> None:
    clock = FakeClock()
    smoother = StatusSmoother(load_config().smoothing, clock)
    _feed(smoother, clock, DeskStatus.WORKING)
    smoother.reset()
    assert smoother.current is DeskStatus.UNKNOWN


def test_three_to_two_majority_enters_majority() -> None:
    clock = FakeClock()
    smoother = StatusSmoother(load_config().smoothing, clock)
    result = None
    for status in (
        DeskStatus.WORKING,
        DeskStatus.FOCUSED,
        DeskStatus.WORKING,
        DeskStatus.FOCUSED,
        DeskStatus.WORKING,
    ):
        clock.advance(1)
        result = smoother.update(_vote(status, 0.6), clock.monotonic())
    assert result.status is DeskStatus.WORKING


def test_relaxed_exit_allows_two_votes() -> None:
    clock = FakeClock()
    smoother = StatusSmoother(load_config().smoothing, clock)
    clock.advance(3)
    result = None
    for status in (
        DeskStatus.WORKING,
        DeskStatus.FOCUSED,
        DeskStatus.ORGANIZING,
        DeskStatus.WORKING,
        DeskStatus.FOCUSED,
    ):
        result = smoother.update(_vote(status), clock.monotonic())
    assert result.vote_count == 2


def test_organizing_can_reach_focus_via_working() -> None:
    clock = FakeClock()
    smoother = StatusSmoother(load_config().smoothing, clock)
    _feed(smoother, clock, DeskStatus.ORGANIZING)
    clock.advance(4)
    _feed(smoother, clock, DeskStatus.WORKING)
    clock.advance(4)
    assert _feed(smoother, clock, DeskStatus.FOCUSED).status is DeskStatus.FOCUSED


def test_transition_timeout_forces_another_state() -> None:
    clock = FakeClock()
    smoother = StatusSmoother(load_config().smoothing, clock)
    smoother.reset(DeskStatus.TRANSITION)
    clock.advance(7)
    result = _feed(smoother, clock, DeskStatus.TRANSITION, step=0)
    assert result.status is not DeskStatus.TRANSITION


def test_tie_uses_rule_priority() -> None:
    clock = FakeClock()
    smoother = StatusSmoother(load_config().smoothing, clock)
    clock.advance(3)
    result = None
    for status in (
        DeskStatus.WORKING,
        DeskStatus.FOCUSED,
        DeskStatus.WORKING,
        DeskStatus.FOCUSED,
        DeskStatus.UNKNOWN,
    ):
        result = smoother.update(_vote(status), clock.monotonic())
    assert result.candidate is DeskStatus.FOCUSED


def test_changes_are_separated_by_dwell() -> None:
    clock = FakeClock()
    smoother = StatusSmoother(load_config().smoothing, clock)
    changes = []
    for index in range(100):
        clock.advance(0.2)
        status = DeskStatus.WORKING if (index // 20) % 2 == 0 else DeskStatus.FOCUSED
        result = smoother.update(_vote(status), clock.monotonic())
        if result.changed:
            changes.append(clock.monotonic())
    assert all(b - a >= 3 for a, b in zip(changes, changes[1:]))
