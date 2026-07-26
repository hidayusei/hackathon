"""Step 5 duration-history tests."""

from deskmate.core.enums import DeskStatus
from deskmate.pipeline.duration import DurationTracker


def test_duration_reaches_ten_seconds() -> None:
    tracker = DurationTracker()
    tracker.update(DeskStatus.WORKING, False, 0.8, 0)
    assert tracker.update(DeskStatus.WORKING, False, 0.8, 10) == 10


def test_changed_resets_duration() -> None:
    tracker = DurationTracker()
    tracker.update(DeskStatus.WORKING, False, 0.8, 0)
    assert tracker.update(DeskStatus.FOCUSED, True, 0.8, 10) == 0


def test_previous_state_has_end_time() -> None:
    tracker = DurationTracker()
    tracker.update(DeskStatus.WORKING, False, 0.8, 0)
    tracker.update(DeskStatus.FOCUSED, True, 0.8, 10)
    assert tracker.history[0].ended_monotonic == 10


def test_recent_status_is_found() -> None:
    tracker = DurationTracker()
    tracker.update(DeskStatus.FOCUSED, False, 0.8, 0)
    tracker.update(DeskStatus.WORKING, True, 0.8, 10)
    assert tracker.had_status_within({DeskStatus.FOCUSED}, 120, 60)


def test_old_status_is_not_found() -> None:
    tracker = DurationTracker()
    tracker.update(DeskStatus.FOCUSED, False, 0.8, 0)
    tracker.update(DeskStatus.WORKING, True, 0.8, 10)
    assert not tracker.had_status_within({DeskStatus.FOCUSED}, 120, 140)


def test_exclude_current_ignores_current_status() -> None:
    tracker = DurationTracker()
    tracker.update(DeskStatus.FOCUSED, False, 0.8, 0)
    assert not tracker.had_status_within({DeskStatus.FOCUSED}, 120, 10)


def test_retention_removes_expired_entries() -> None:
    tracker = DurationTracker(history_retention_minutes=1)
    tracker.update(DeskStatus.FOCUSED, False, 0.8, 0)
    tracker.update(DeskStatus.WORKING, True, 0.8, 1)
    tracker.update(DeskStatus.UNKNOWN, True, 0.8, 100)
    assert all(entry.status is not DeskStatus.FOCUSED for entry in tracker.history)


def test_history_limit_is_enforced() -> None:
    tracker = DurationTracker(history_limit=2)
    for index, status in enumerate(
        [DeskStatus.FOCUSED, DeskStatus.WORKING, DeskStatus.UNKNOWN, DeskStatus.WORKING]
    ):
        tracker.update(status, index > 0, 0.8, float(index))
    assert len(tracker.history) <= 3
