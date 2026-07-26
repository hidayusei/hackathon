"""Step 8 canonical label tests."""

from deskmate.core.enums import Approachability, DeskStatus, SystemStatus
from deskmate.ui.labels import (
    APPROACHABILITY_LABELS_JA,
    STATUS_LABELS_JA,
    SYSTEM_LABELS_JA,
    format_duration,
    resolve_label,
)


def test_format_seconds() -> None:
    assert format_duration(42) == "42秒"


def test_format_minutes() -> None:
    assert format_duration(312) == "5分12秒"


def test_format_hours() -> None:
    assert format_duration(3780) == "1時間03分"


def test_format_zero() -> None:
    assert format_duration(0) == "0秒"


def test_high_confidence_focus_label() -> None:
    assert resolve_label(DeskStatus.FOCUSED, 0.8) == "集中傾向"


def test_low_confidence_is_unknown() -> None:
    assert resolve_label(DeskStatus.FOCUSED, 0.3) == "状態不明"


def test_no_motion_is_not_downgraded() -> None:
    assert resolve_label(DeskStatus.NO_MOTION, 0.3) == "一定時間、動きを検出していません"


def test_long_no_motion_uses_quiet_variant() -> None:
    assert resolve_label(DeskStatus.NO_MOTION, 0.9, 200) == "静かな状態が続いています"


def test_all_statuses_have_labels() -> None:
    assert set(STATUS_LABELS_JA) == set(DeskStatus)


def test_all_secondary_and_system_states_have_labels() -> None:
    assert set(APPROACHABILITY_LABELS_JA) == set(Approachability)
    assert set(SYSTEM_LABELS_JA) == set(SystemStatus)


def test_labels_do_not_contain_forbidden_words() -> None:
    values = [
        *STATUS_LABELS_JA.values(),
        *APPROACHABILITY_LABELS_JA.values(),
        *SYSTEM_LABELS_JA.values(),
    ]
    assert not any(word in value for value in values for word in ("離席", "不在", "完全に安全", "匿名"))
