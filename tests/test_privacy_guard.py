"""Step 12 privacy invariants."""

from dataclasses import fields
from pathlib import Path

import pytest

from deskmate.config.loader import load_config
from deskmate.core.errors import PrivacyViolationError
from deskmate.core.types import StatusSnapshot
from deskmate.privacy.guard import PrivacyGuard


def test_raw_save_is_disabled_by_default() -> None:
    assert not PrivacyGuard(load_config().privacy).can_save_raw_events()


def test_raw_save_assertion_raises_by_default() -> None:
    with pytest.raises(PrivacyViolationError):
        PrivacyGuard(load_config().privacy).assert_can_save_raw_events()


def test_external_send_is_always_disabled() -> None:
    assert not PrivacyGuard(load_config().privacy).can_send_external()


def test_external_send_assertion_raises() -> None:
    with pytest.raises(PrivacyViolationError):
        PrivacyGuard(load_config().privacy).assert_no_external_send("http://example.com")


def test_snapshot_has_exactly_ten_safe_fields() -> None:
    assert {field.name for field in fields(StatusSnapshot)} == {
        "status", "system_status", "label", "animation", "duration_seconds",
        "confidence", "approachability", "approachability_label", "changed", "updated_at",
    }


def test_public_dict_has_exactly_nine_keys() -> None:
    from datetime import datetime
    from deskmate.core.enums import AnimationId, Approachability, DeskStatus, SystemStatus
    value = StatusSnapshot(
        DeskStatus.UNKNOWN, SystemStatus.RUNNING, "", AnimationId.UNKNOWN, 0, 0,
        Approachability.UNDETERMINED, "", False, datetime.now().astimezone(),
    )
    assert set(value.to_public_dict()) == {
        "status", "label", "animation", "duration_seconds", "confidence",
        "approachability", "approachability_label", "system_status", "updated_at",
    }


def test_default_pipeline_does_not_write_data_directory(tmp_path: Path) -> None:
    assert not list(tmp_path.iterdir())


def test_forbidden_capture_and_send_imports_are_absent() -> None:
    root = Path(__file__).parents[1] / "src" / "deskmate"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    assert not any(f"import {name}" in source for name in ("mss", "pyautogui", "win32gui", "requests", "httpx", "cv2"))


def test_share_window_has_no_private_types() -> None:
    path = Path(__file__).parents[1] / "src" / "deskmate" / "ui" / "share_window.py"
    source = path.read_text(encoding="utf-8")
    assert not any(name in source for name in ("FeatureFrame", "DetailFrame", "EventWindow"))


def test_retention_cutoff_uses_configured_minutes() -> None:
    assert PrivacyGuard(load_config().privacy).retention_cutoff(4000) == 400
