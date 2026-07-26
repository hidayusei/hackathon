"""Step 13 automatic demo definition checks."""

from functools import lru_cache

from conftest import FakeClock
from deskmate.config.loader import load_config
from deskmate.config.schema import DummyInputConfig
from deskmate.core.enums import Approachability, DeskStatus
from deskmate.input.dummy_source import DummyEventSource
from deskmate.input.scenarios import DEMO_SEQUENCE, SCENARIOS
from deskmate.pipeline.runner import PipelineRunner


def test_demo_total_is_340_seconds() -> None:
    assert sum(step.duration_s for step in DEMO_SEQUENCE) == 340


def test_all_demo_scenarios_exist() -> None:
    assert all(step.scenario_id in SCENARIOS for step in DEMO_SEQUENCE)


def test_every_demo_step_exceeds_five_dwell_periods() -> None:
    assert all(step.duration_s >= 15 for step in DEMO_SEQUENCE)


def test_demo_contains_patterns_for_all_states() -> None:
    required = {
        "keyboard_steady", "desk_wide_active", "activity_decay", "quiet",
        "rapid_change", "noise_burst", "dropout",
    }
    assert required <= {step.scenario_id for step in DEMO_SEQUENCE}


@lru_cache(maxsize=1)
def _run_complete_demo():
    clock = FakeClock()
    runner = PipelineRunner(load_config(), clock)
    runner.source = DummyEventSource(
        DummyInputConfig(mode="demo"), runner.config.sensor, clock
    )
    runner.source.open()
    snapshots = []
    runner.snapshot_ready.connect(snapshots.append)
    for _ in range(round(340 / 0.02)):
        clock.advance(0.02)
        runner._poll_once()
    return snapshots


def test_complete_demo_confirms_all_seven_statuses() -> None:
    assert {snapshot.status for snapshot in _run_complete_demo()} == set(DeskStatus)


def test_complete_demo_changes_obey_configured_dwell() -> None:
    snapshots = _run_complete_demo()
    changes = [
        (index * 0.2, snapshot.status)
        for index, snapshot in enumerate(snapshots)
        if snapshot.changed and snapshot.system_status.value != "no_signal"
    ]
    assert all(
        later[0] - earlier[0] >= 2.0
        for earlier, later in zip(changes, changes[1:])
    )


def test_complete_demo_shows_all_approachability_values() -> None:
    assert {
        snapshot.approachability for snapshot in _run_complete_demo()
    } == set(Approachability)
