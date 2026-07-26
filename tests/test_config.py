"""Step 2 configuration tests."""

from pathlib import Path

import pytest

from deskmate.config.loader import deep_merge, load_config
from deskmate.core.errors import ConfigError


def test_load_defaults() -> None:
    assert load_config().version == 1


def test_stride_cannot_exceed_window() -> None:
    with pytest.raises(ConfigError):
        load_config({"window": {"window_ms": 200, "stride_ms": 201}})


def test_window_below_range_is_rejected() -> None:
    with pytest.raises(ConfigError):
        load_config({"window": {"window_ms": 50}})


def test_unknown_yaml_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("unknown: true\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(config_path=path)


def test_other_region_is_rejected() -> None:
    with pytest.raises(ConfigError):
        load_config({"regions": [{"id": "other", "rect": [0, 0, 1, 1]}]})


@pytest.mark.parametrize("rect", ([-0.1, 0, 1, 1], [0.5, 0, 0.5, 1]))
def test_invalid_region_rect_is_rejected(rect: list[float]) -> None:
    with pytest.raises(ConfigError):
        load_config({"regions": [{"id": "keyboard", "rect": rect}]})


def test_duplicate_region_id_is_rejected() -> None:
    with pytest.raises(ConfigError):
        load_config(
            {"regions": [
                {"id": "keyboard", "rect": [0, 0, 0.5, 1]},
                {"id": "keyboard", "rect": [0.5, 0, 1, 1]},
            ]}
        )


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


def test_estimation_defaults_match_status_definition() -> None:
    estimation = load_config().estimation
    expected = {
        "idle_eps": 100.0,
        "low_activity_eps": 400.0,
        "focus_min_eps": 400.0,
        "active_eps": 2000.0,
        "high_activity_eps": 5000.0,
        "no_motion_seconds": 20.0,
        "focus_region_share": 0.60,
        "focus_min_seconds": 5.0,
        "focus_max_bbox_area_ratio": 0.20,
        "focus_max_activity_cv": 0.60,
        "organizing_bbox_area_ratio": 0.25,
        "organizing_active_cell_ratio": 0.25,
        "organizing_centroid_speed": 35.0,
        "break_max_eps": 600.0,
        "break_decay_ratio": 0.40,
        "transition_change_score": 0.55,
        "transition_max_seconds": 6.0,
        "noise_ratio_threshold": 0.79,
        "warmup_seconds": 3.0,
    }
    for key, value in expected.items():
        assert getattr(estimation, key) == pytest.approx(value)


def test_feature_defaults_match_status_definition() -> None:
    """bbox_percentile is tuned in status-definition.md 5.4; keep both in step."""
    assert load_config().features.bbox_percentile == pytest.approx(0.05)
