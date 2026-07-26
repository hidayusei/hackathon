"""Step 5 canonical rule tests."""

import pytest

from conftest import make_smoothed
from deskmate.config.loader import load_config
from deskmate.core.enums import DeskStatus, RegionId
from deskmate.pipeline.rule_estimator import RuleStatusEstimator, margin_confidence


def _estimate(smoothed):
    return RuleStatusEstimator(load_config().estimation).estimate(None, smoothed)  # type: ignore[arg-type]


def test_no_motion_rule() -> None:
    assert _estimate(make_smoothed(idle_seconds=25)).status is DeskStatus.NO_MOTION


def test_transition_rule() -> None:
    assert _estimate(make_smoothed(change_score=0.7, rate_short=5000)).status is DeskStatus.TRANSITION


def test_organizing_rule() -> None:
    s = make_smoothed(rate_short=4000, area_short=0.5, cell_short=0.4, speed_short=70)
    assert _estimate(s).status is DeskStatus.ORGANIZING


def test_focused_rule() -> None:
    s = make_smoothed(rate_short=1400, area_short=0.05, rate_cv_10s=0.2, active_seconds=10)
    s.share_short[RegionId.KEYBOARD] = 0.9
    assert _estimate(s).status is DeskStatus.FOCUSED


def test_short_break_rule() -> None:
    assert _estimate(make_smoothed(rate_short=300, rate_long=3000)).status is DeskStatus.SHORT_BREAK


def test_working_rule() -> None:
    assert _estimate(make_smoothed(rate_short=1200, area_short=0.3)).status is DeskStatus.WORKING


def test_unknown_fallback() -> None:
    assert _estimate(make_smoothed(rate_short=200, rate_long=250)).status is DeskStatus.UNKNOWN


def test_no_motion_has_priority() -> None:
    s = make_smoothed(idle_seconds=25, change_score=0.9, rate_short=5000)
    assert _estimate(s).status is DeskStatus.NO_MOTION


def test_organizing_has_priority_over_focused() -> None:
    s = make_smoothed(
        rate_short=4000, area_short=0.4, cell_short=0.4, speed_short=70,
        active_seconds=10,
    )
    s.share_short[RegionId.KEYBOARD] = 0.9
    assert _estimate(s).status is DeskStatus.ORGANIZING


def test_focus_requires_minimum_active_seconds() -> None:
    s = make_smoothed(rate_short=1400, area_short=0.05, active_seconds=2)
    s.share_short[RegionId.KEYBOARD] = 0.9
    assert _estimate(s).status is DeskStatus.WORKING


def test_noise_penalty_multiplies_confidence() -> None:
    clean = _estimate(make_smoothed(rate_short=4000, area_short=0.5, cell_short=0.4, speed_short=70))
    noisy = _estimate(make_smoothed(
        rate_short=4000, area_short=0.5, cell_short=0.4, speed_short=70, noise_ratio=0.95
    ))
    assert noisy.confidence == pytest.approx(clean.confidence * 0.6)


def test_margin_confidence_boundaries() -> None:
    assert margin_confidence(10, 10, 10) == pytest.approx(0.5)
    assert margin_confidence(20, 10, 10) == pytest.approx(0.95)
    assert margin_confidence(0, 10, 10) == pytest.approx(0.5)


def test_confidence_is_bounded() -> None:
    assert 0 <= _estimate(make_smoothed(rate_short=1000)).confidence <= 1


def test_rule_ids_are_nonempty_and_unique() -> None:
    estimates = [
        _estimate(make_smoothed(idle_seconds=25)),
        _estimate(make_smoothed(change_score=0.7, rate_short=5000)),
        _estimate(make_smoothed(rate_short=200, rate_long=250)),
    ]
    assert len({item.rule_id for item in estimates}) == len(estimates)
    assert all(item.rule_id for item in estimates)
