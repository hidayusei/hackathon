"""Automatic three-state demo checks."""

from functools import lru_cache

from conftest import FakeClock
from deskmate.config.loader import load_config
from deskmate.config.schema import DummyInputConfig
from deskmate.core.enums import DeskStatus
from deskmate.input.dummy_source import DummyEventSource
from deskmate.input.scenarios import DEMO_SEQUENCE, SCENARIOS
from deskmate.pipeline.runner import PipelineRunner


def test_demo_total_is_210_seconds() -> None:
    assert sum(step.duration_s for step in DEMO_SEQUENCE) == 210


def test_all_demo_scenarios_exist_and_are_long_enough() -> None:
    assert all(step.scenario_id in SCENARIOS for step in DEMO_SEQUENCE)
    assert all(step.duration_s >= 15 for step in DEMO_SEQUENCE)


@lru_cache(maxsize=1)
def _run_complete_demo():
    clock = FakeClock()
    config = load_config({"input": {"source": "dummy"}})
    runner = PipelineRunner(config, clock)
    runner.source = DummyEventSource(
        DummyInputConfig(mode="demo"), config.sensor, clock
    )
    runner.source.open()
    runner._running = True
    snapshots = []
    runner.snapshot_ready.connect(snapshots.append)
    for _ in range(round(210 / 0.02)):
        clock.advance(0.02)
        runner._poll_once()
    return snapshots


def test_complete_demo_confirms_all_three_statuses() -> None:
    assert {snapshot.status for snapshot in _run_complete_demo()} == set(DeskStatus)


def test_demo_break_prompt_can_be_accelerated() -> None:
    clock = FakeClock()
    config = load_config(
        {
            "input": {"source": "dummy"},
            "break": {"demo_scale": 0.02},
        }
    )
    runner = PipelineRunner(config, clock)
    source = DummyEventSource(
        DummyInputConfig(mode="manual", scenario="keyboard_focus"),
        config.sensor,
        clock,
    )
    source.open()
    due = False
    for _ in range(round(50 / 0.02)):
        clock.advance(0.02)
        batch = source.read(0)
        if batch is not None:
            for window in runner.windower.push(batch):
                due = runner._process_window(window).break_due or due
    assert due
