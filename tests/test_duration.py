"""Confirmed-state duration and history tests."""

from deskmate.core.enums import DeskStatus
from deskmate.pipeline.duration import DurationTracker


def test_duration_reaches_ten_seconds() -> None:
    tracker = DurationTracker()
    tracker.update(DeskStatus.IDLE, False, 0.8, 0)
    assert tracker.update(DeskStatus.IDLE, False, 0.8, 10) == 10


def test_changed_resets_duration_and_closes_previous_entry() -> None:
    tracker = DurationTracker()
    tracker.update(DeskStatus.IDLE, False, 0.8, 0)
    assert tracker.update(DeskStatus.FOCUSED, True, 0.8, 10) == 0
    assert tracker.history[0].ended_monotonic == 10


def test_recent_returns_intersecting_entries() -> None:
    tracker = DurationTracker()
    tracker.update(DeskStatus.FOCUSED, False, 0.8, 0)
    tracker.update(DeskStatus.IDLE, True, 0.8, 10)
    assert DeskStatus.FOCUSED in {entry.status for entry in tracker.recent(120, 60)}


def test_retention_removes_expired_entries() -> None:
    tracker = DurationTracker(history_retention_minutes=1)
    tracker.update(DeskStatus.FOCUSED, False, 0.8, 0)
    tracker.update(DeskStatus.IDLE, True, 0.8, 1)
    tracker.update(DeskStatus.AWAY, True, 0.8, 100)
    assert all(entry.status is not DeskStatus.FOCUSED for entry in tracker.history)
