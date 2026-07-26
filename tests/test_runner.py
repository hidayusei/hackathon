"""Step 6 synchronous runner tests."""

import numpy as np

from conftest import FakeClock, make_window
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
    assert _run_scenario("keyboard_steady", 30)[-1].status is DeskStatus.FOCUSED


def test_wide_scenario_finishes_organizing() -> None:
    assert _run_scenario("desk_wide_active", 30)[-1].status is DeskStatus.ORGANIZING


def test_quiet_scenario_finishes_no_motion() -> None:
    assert _run_scenario("quiet", 40)[-1].status is DeskStatus.NO_MOTION


def test_decay_scenario_visits_short_break() -> None:
    assert DeskStatus.SHORT_BREAK in {s.status for s in _run_scenario("activity_decay", 20)}


def test_rapid_scenario_visits_transition() -> None:
    assert DeskStatus.TRANSITION in {s.status for s in _run_scenario("rapid_change", 15)}


def test_noise_scenario_has_uncertain_display() -> None:
    assert "状態不明" in {s.label for s in _run_scenario("noise_burst", 15)}
