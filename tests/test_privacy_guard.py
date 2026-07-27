"""Privacy invariants for local-only processing."""

from dataclasses import fields
from datetime import datetime
from pathlib import Path

import pytest

from deskmate.config.loader import load_config
from deskmate.core.enums import AnimationId, DeskStatus, SystemStatus
from deskmate.core.errors import PrivacyViolationError
from deskmate.core.types import StatusSnapshot
from deskmate.privacy.guard import PrivacyGuard


def test_raw_save_is_disabled_by_default() -> None:
    assert not PrivacyGuard(load_config().privacy).can_save_raw_events()


def test_raw_save_assertion_raises_by_default() -> None:
    with pytest.raises(PrivacyViolationError):
        PrivacyGuard(load_config().privacy).assert_can_save_raw_events()


def test_external_send_is_always_disabled() -> None:
    guard = PrivacyGuard(load_config().privacy)
    assert not guard.can_send_external()
    with pytest.raises(PrivacyViolationError):
        guard.assert_no_external_send("external")


def test_snapshot_has_exactly_ten_safe_fields() -> None:
    assert len(fields(StatusSnapshot)) == 10


def test_public_dict_has_exactly_eight_safe_keys() -> None:
    value = StatusSnapshot(
        DeskStatus.IDLE,
        SystemStatus.RUNNING,
        "",
        AnimationId.SITTING,
        0,
        0,
        0,
        False,
        False,
        datetime.now().astimezone(),
    )
    assert set(value.to_public_dict()) == {
        "status",
        "label",
        "animation",
        "duration_seconds",
        "focus_streak_seconds",
        "break_due",
        "system_status",
        "updated_at",
    }


def test_forbidden_capture_and_send_imports_are_absent() -> None:
    root = Path(__file__).parents[1] / "src" / "deskmate"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    assert not any(
        f"import {name}" in source
        for name in ("mss", "pyautogui", "win32gui", "requests", "httpx", "cv2")
    )


def test_removed_share_window_is_absent() -> None:
    path = Path(__file__).parents[1] / "src" / "deskmate" / "ui" / "share_window.py"
    assert not path.exists()


def test_retention_cutoff_uses_configured_minutes() -> None:
    assert PrivacyGuard(load_config().privacy).retention_cutoff(4000) == 400
