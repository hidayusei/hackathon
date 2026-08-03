"""Pi-contained configuration tests."""

from pathlib import Path

import pytest

from deskmate.config.loader import deep_merge, load_config, user_config_path
from deskmate.core.enums import SourceKind
from deskmate.core.errors import ConfigError


def test_load_defaults() -> None:
    assert load_config().version == 1


def test_default_source_is_auto() -> None:
    assert load_config().input.source is SourceKind.AUTO


def test_linux_user_config_uses_xdg_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert user_config_path() == tmp_path / "DeskMate" / "config.yaml"


def test_stride_cannot_exceed_window() -> None:
    with pytest.raises(ConfigError):
        load_config({"window": {"window_ms": 200, "stride_ms": 201}})


def test_unknown_yaml_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("unknown: true\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(config_path=path)


def test_removed_share_configuration_is_rejected() -> None:
    with pytest.raises(ConfigError):
        load_config({"share": {"enabled": True}})


def test_deep_merge_preserves_nested_siblings() -> None:
    assert deep_merge({"a": {"b": 1, "c": 2}}, {"a": {"b": 3}}) == {
        "a": {"b": 3, "c": 2}
    }


def test_privacy_sensitive_defaults_are_false() -> None:
    config = load_config()
    assert not config.privacy.save_raw_events
    assert not config.privacy.save_features
    assert not config.logging.log_features
    assert not config.debug.enabled
    assert not config.privacy.allow_external_send


def test_estimation_defaults_match_current_spec() -> None:
    estimation = load_config().estimation
    expected = {
        "idle_eps": 100.0,
        "away_seconds": 30.0,
        "focus_min_eps": 400.0,
        "high_activity_eps": 5000.0,
        "focus_region_share": 0.60,
        "focus_min_seconds": 5.0,
        "focus_max_bbox_area_ratio": 0.20,
        "focus_max_activity_cv": 0.60,
        "warmup_seconds": 3.0,
    }
    for key, value in expected.items():
        assert getattr(estimation, key) == pytest.approx(value)


def test_metavision_profile_ignores_position_and_accepts_measured_spread() -> None:
    profile = load_config().estimation.metavision
    assert profile.idle_eps == pytest.approx(10_000.0)
    assert profile.focus_min_eps == pytest.approx(15_000.0)
    assert profile.focus_region_share == pytest.approx(0.0)
    assert profile.focus_max_bbox_area_ratio == pytest.approx(0.75)
    assert profile.focus_max_activity_cv == pytest.approx(3.0)


def test_break_defaults_are_25_minutes_and_three_minute_reset() -> None:
    config = load_config().break_prompt
    assert config.after_seconds == pytest.approx(1500.0)
    assert config.reset_seconds == pytest.approx(180.0)
    assert config.snooze_seconds == pytest.approx(300.0)


def test_gif_renderer_and_integer_scale_are_defaults() -> None:
    config = load_config().character
    assert config.renderer == "gif"
    assert isinstance(config.scale, int)
