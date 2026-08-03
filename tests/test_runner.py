"""Step 6 synchronous runner tests."""

import numpy as np

from conftest import FakeClock, make_smoothed, make_window
from deskmate.config.loader import load_config
from deskmate.config.schema import DummyInputConfig
from deskmate.core.enums import DeskStatus
from deskmate.input.dummy_source import DummyEventSource
from deskmate.core.enums import SystemStatus
from deskmate.pipeline.runner import PipelineRunner


def test_processing_window_emits_snapshot() -> None:
    clock = FakeClock()
    runner = PipelineRunner(load_config(), clock)
    seen = []
    runner.snapshot_ready.connect(seen.append)
    runner._process_window(make_window(np.arange(100), np.arange(100)))
    assert len(seen) == 1


def test_duration_is_never_negative() -> None:
    clock = FakeClock()
    runner = PipelineRunner(load_config(), clock)
    for index in range(10):
        clock.advance(0.2)
        snapshot = runner._process_window(
            make_window(np.arange(100), np.arange(100), index=index)
        )
        assert snapshot.duration_seconds >= 0


def test_detail_is_not_emitted_without_subscription() -> None:
    runner = PipelineRunner(load_config(), FakeClock())
    seen = []
    runner.detail_ready.connect(seen.append)
    runner._process_window(make_window(np.arange(100), np.arange(100)))
    assert seen == []


def test_detail_is_emitted_with_subscription() -> None:
    runner = PipelineRunner(load_config(), FakeClock())
    seen = []
    runner.detail_ready.connect(seen.append)
    runner.set_detail_subscription(True)
    runner._process_window(make_window(np.arange(100), np.arange(100)))
    assert len(seen) == 1


def test_metavision_background_calibration_feeds_filtered_features() -> None:
    config = load_config(
        {
            "ui": {"detail": {"calibration_seconds": 0.4}},
            "estimation": {"background_residual_eps": 100.0},
        }
    )
    runner = PipelineRunner(config, FakeClock())
    runner._background_enabled = True
    seen = []
    runner.detail_ready.connect(seen.append)
    runner.set_detail_subscription(True)
    stationary_x = np.full(100, 10)
    stationary_y = np.full(100, 20)

    runner._process_window(make_window(stationary_x, stationary_y))
    runner._process_window(make_window(stationary_x, stationary_y, index=1))
    moving_x = np.r_[stationary_x, np.full(200, 30)]
    moving_y = np.r_[stationary_y, np.full(200, 40)]
    runner._process_window(make_window(moving_x, moving_y, index=2))

    assert seen[0].calibration_remaining_seconds > 0
    assert seen[1].calibration_remaining_seconds == 0
    assert seen[2].raw_event_count == 300
    assert seen[2].features.global_features.event_count == 180
    assert seen[2].preview_x.size == 200
    assert np.all(seen[2].preview_x == 30)


def test_metavision_profile_ignores_focus_position_but_dummy_does_not() -> None:
    runner = PipelineRunner(load_config(), FakeClock())
    measured = make_smoothed(
        rate_short=20_000,
        area_short=0.67,
        rate_cv_10s=2.0,
        active_seconds=10.0,
    )
    assert runner.estimator.estimate(None, measured).status is DeskStatus.IDLE

    runner._configure_source_profile("metavision(live)")

    assert runner.estimator.estimate(None, measured).status is DeskStatus.FOCUSED


def test_metavision_profile_does_not_focus_on_away_residual_rate() -> None:
    runner = PipelineRunner(load_config(), FakeClock())
    runner._configure_source_profile("metavision(live)")
    weak_residual = make_smoothed(
        rate_short=6_000,
        area_short=0.60,
        rate_cv_10s=1.0,
        active_seconds=20.0,
    )

    assert runner.estimator.estimate(None, weak_residual).status is DeskStatus.IDLE


def test_paused_snapshot_has_paused_system_status() -> None:
    runner = PipelineRunner(load_config(), FakeClock())
    seen = []
    runner.snapshot_ready.connect(seen.append)
    runner.set_paused(True)
    assert seen[-1].system_status is SystemStatus.PAUSED


def test_average_processing_is_under_budget() -> None:
    runner = PipelineRunner(load_config(), FakeClock())
    for index in range(20):
        runner._process_window(make_window(np.arange(100), np.arange(100), index=index))
    assert runner.stats.avg_compute_ms < 30


def _run_scenario(scenario: str, seconds: float):
    clock = FakeClock()
    runner = PipelineRunner(load_config(), clock)
    source = DummyEventSource(
        DummyInputConfig(mode="manual", scenario=scenario), runner.config.sensor, clock
    )
    source.open()
    seen = []
    runner.snapshot_ready.connect(seen.append)
    for _ in range(round(seconds / 0.02)):
        clock.advance(0.02)
        batch = source.read(0)
        if batch is not None:
            for window in runner.windower.push(batch):
                runner._process_window(window)
    return seen


def test_keyboard_scenario_finishes_focused() -> None:
    assert _run_scenario("keyboard_focus", 30)[-1].status is DeskStatus.FOCUSED


def test_wide_scenario_finishes_idle() -> None:
    assert _run_scenario("desk_wide", 30)[-1].status is DeskStatus.IDLE


def test_quiet_scenario_finishes_away() -> None:
    assert _run_scenario("quiet", 40)[-1].status is DeskStatus.AWAY


def test_mouse_scenario_stays_idle() -> None:
    assert _run_scenario("mouse_intermittent", 20)[-1].status is DeskStatus.IDLE
