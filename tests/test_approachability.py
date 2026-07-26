"""Step 5 privacy-safe approachability tests."""

import inspect

from conftest import FakeClock
from deskmate.config.loader import load_config
from deskmate.core.enums import Approachability, DeskStatus, SystemStatus
from deskmate.pipeline.approachability import ApproachabilityResolver
from deskmate.pipeline.duration import DurationTracker


def _resolve(status, duration=0, confidence=0.8, system=SystemStatus.RUNNING, now=10):
    clock = FakeClock()
    resolver = ApproachabilityResolver(load_config().share, clock)
    tracker = DurationTracker()
    return resolver.resolve(status, system, duration, confidence, tracker, now)


def test_long_short_break_is_likely_ok() -> None:
    assert _resolve(DeskStatus.SHORT_BREAK, 15) is Approachability.LIKELY_OK


def test_short_short_break_is_undetermined() -> None:
    assert _resolve(DeskStatus.SHORT_BREAK, 5) is Approachability.UNDETERMINED


def test_focused_long_is_prefer_later() -> None:
    assert _resolve(DeskStatus.FOCUSED, 60) is Approachability.PREFER_LATER


def test_focused_short_is_undetermined() -> None:
    assert _resolve(DeskStatus.FOCUSED, 10) is Approachability.UNDETERMINED


def test_no_motion_is_undetermined() -> None:
    assert _resolve(DeskStatus.NO_MOTION) is Approachability.UNDETERMINED


def test_transition_is_undetermined() -> None:
    assert _resolve(DeskStatus.TRANSITION) is Approachability.UNDETERMINED


def test_low_confidence_is_undetermined() -> None:
    assert _resolve(DeskStatus.SHORT_BREAK, 20, 0.3) is Approachability.UNDETERMINED


def test_nonrunning_system_is_undetermined() -> None:
    assert _resolve(DeskStatus.SHORT_BREAK, 20, system=SystemStatus.PAUSED) is Approachability.UNDETERMINED


def test_resolver_signature_has_no_feature_frame() -> None:
    assert "FeatureFrame" not in str(inspect.signature(ApproachabilityResolver.resolve))


def test_working_after_recent_focus_is_likely_ok() -> None:
    clock = FakeClock()
    resolver = ApproachabilityResolver(load_config().share, clock)
    tracker = DurationTracker()
    tracker.update(DeskStatus.FOCUSED, False, 0.8, 0)
    tracker.update(DeskStatus.WORKING, True, 0.8, 10)
    assert resolver.resolve(
        DeskStatus.WORKING, SystemStatus.RUNNING, 10, 0.8, tracker, 20
    ) is Approachability.LIKELY_OK


def test_working_without_recent_busy_history_is_undetermined() -> None:
    assert _resolve(DeskStatus.WORKING, 20) is Approachability.UNDETERMINED


def test_nonundetermined_change_holds_for_five_seconds() -> None:
    clock = FakeClock()
    resolver = ApproachabilityResolver(load_config().share, clock)
    tracker = DurationTracker()
    assert resolver.resolve(
        DeskStatus.SHORT_BREAK, SystemStatus.RUNNING, 15, 0.8, tracker, 10
    ) is Approachability.LIKELY_OK
    assert resolver.resolve(
        DeskStatus.FOCUSED, SystemStatus.RUNNING, 60, 0.8, tracker, 13
    ) is Approachability.LIKELY_OK


def test_nonundetermined_change_applies_after_hold() -> None:
    clock = FakeClock()
    resolver = ApproachabilityResolver(load_config().share, clock)
    tracker = DurationTracker()
    resolver.resolve(DeskStatus.SHORT_BREAK, SystemStatus.RUNNING, 15, 0.8, tracker, 10)
    assert resolver.resolve(
        DeskStatus.FOCUSED, SystemStatus.RUNNING, 60, 0.8, tracker, 16
    ) is Approachability.PREFER_LATER


def test_undetermined_change_is_immediate() -> None:
    clock = FakeClock()
    resolver = ApproachabilityResolver(load_config().share, clock)
    tracker = DurationTracker()
    resolver.resolve(DeskStatus.SHORT_BREAK, SystemStatus.RUNNING, 15, 0.8, tracker, 10)
    assert resolver.resolve(
        DeskStatus.NO_MOTION, SystemStatus.RUNNING, 1, 0.8, tracker, 11
    ) is Approachability.UNDETERMINED
