"""Three-state estimation-rule tests."""

import pytest

from conftest import make_smoothed
from deskmate.config.loader import load_config
from deskmate.core.enums import DeskStatus, RegionId
from deskmate.pipeline.rule_estimator import RuleStatusEstimator, margin_confidence


def _estimate(smoothed):
    return RuleStatusEstimator(load_config().estimation).estimate(None, smoothed)  # type: ignore[arg-type]


def _focused(**values):
    defaults = {
        "rate_short": 1400,
        "area_short": 0.06,
        "rate_cv_10s": 0.2,
        "active_seconds": 10,
    }
    defaults.update(values)
    smoothed = make_smoothed(**defaults)
    smoothed.share_short[RegionId.KEYBOARD] = 0.9
    return smoothed


def test_away_rule_after_30_seconds() -> None:
    assert _estimate(make_smoothed(idle_seconds=30)).status is DeskStatus.AWAY


def test_focused_rule() -> None:
    assert _estimate(_focused()).status is DeskStatus.FOCUSED


@pytest.mark.parametrize(
    "smoothed",
    (
        _focused(active_seconds=2),
        _focused(area_short=0.4),
        _focused(rate_cv_10s=0.9),
    ),
)
def test_failed_focus_condition_falls_back_to_idle(smoothed) -> None:
    assert _estimate(smoothed).status is DeskStatus.IDLE


def test_focus_share_is_required() -> None:
    assert _estimate(
        make_smoothed(
            rate_short=1400, area_short=0.06, rate_cv_10s=0.2, active_seconds=10
        )
    ).status is DeskStatus.IDLE


def test_away_has_priority_over_focus() -> None:
    assert _estimate(_focused(idle_seconds=31)).status is DeskStatus.AWAY


def test_all_confidences_are_bounded() -> None:
    for smoothed in (make_smoothed(), _focused(), make_smoothed(idle_seconds=60)):
        assert 0.0 <= _estimate(smoothed).confidence <= 1.0


def test_margin_confidence_boundaries() -> None:
    assert margin_confidence(10, 10, 10) == pytest.approx(0.5)
    assert margin_confidence(20, 10, 10) == pytest.approx(0.95)
