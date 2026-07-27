"""Current Japanese labels and input-mode badges."""

from deskmate.core.enums import DeskStatus, SourceStatus, SystemStatus
from deskmate.ui.labels import (
    STATUS_LABELS_JA,
    SYSTEM_LABELS_JA,
    format_duration,
    input_mode_text,
    resolve_label,
)


def test_duration_formats() -> None:
    assert format_duration(42) == "42秒"
    assert format_duration(312) == "5分12秒"
    assert format_duration(3780) == "1時間03分"


def test_three_state_labels() -> None:
    assert resolve_label(DeskStatus.FOCUSED) == "集中"
    assert resolve_label(DeskStatus.IDLE) == "非集中"
    assert resolve_label(DeskStatus.AWAY) == "離席中"


def test_system_label_overrides_state() -> None:
    assert resolve_label(
        DeskStatus.FOCUSED, SystemStatus.NO_SIGNAL
    ) == SYSTEM_LABELS_JA[SystemStatus.NO_SIGNAL]


def test_all_statuses_have_labels() -> None:
    assert set(STATUS_LABELS_JA) == set(DeskStatus)


def test_mode_badges_are_unambiguous() -> None:
    assert input_mode_text("metavision(live)", SourceStatus.STREAMING) == "LIVE"
    assert input_mode_text("metavision(raw)", SourceStatus.STREAMING) == "REPLAY"
    assert input_mode_text("dummy(demo)", SourceStatus.STREAMING) == "DUMMY MODE"
    assert input_mode_text("metavision(live)", SourceStatus.ERROR) == "CAMERA ERROR"
