"""Three-state smoothing tests."""

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


def test_initial_state_is_idle() -> None:
    assert StatusSmoother(load_config().smoothing, FakeClock()).current is DeskStatus.IDLE


def test_majority_confirms_focused_after_dwell() -> None:
    clock = FakeClock()
    smoother = StatusSmoother(load_config().smoothing, clock)
    assert _feed(smoother, clock, DeskStatus.FOCUSED).status is DeskStatus.FOCUSED


def test_low_confidence_does_not_enter() -> None:
    clock = FakeClock()
    smoother = StatusSmoother(load_config().smoothing, clock)
    assert _feed(
        smoother, clock, DeskStatus.FOCUSED, confidence=0.4
    ).status is DeskStatus.IDLE


def test_force_away_is_immediate() -> None:
    clock = FakeClock()
    smoother = StatusSmoother(load_config().smoothing, clock)
    result = smoother.update(_vote(DeskStatus.AWAY), 0, force_away=True)
    assert result.status is DeskStatus.AWAY
    assert result.changed


def test_motion_return_leaves_away_immediately_via_idle() -> None:
    clock = FakeClock()
    smoother = StatusSmoother(load_config().smoothing, clock)
    smoother.update(_vote(DeskStatus.AWAY), 0, force_away=True)
    result = smoother.update(_vote(DeskStatus.FOCUSED), 0.2)
    assert result.status is DeskStatus.IDLE
    assert result.changed


def test_all_three_state_transitions_are_possible() -> None:
    clock = FakeClock()
    smoother = StatusSmoother(load_config().smoothing, clock)
    _feed(smoother, clock, DeskStatus.FOCUSED)
    clock.advance(4)
    assert _feed(smoother, clock, DeskStatus.IDLE).status is DeskStatus.IDLE
    smoother.update(_vote(DeskStatus.AWAY), clock.monotonic(), force_away=True)
    assert smoother.current is DeskStatus.AWAY
