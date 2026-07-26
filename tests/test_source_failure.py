"""Step 12 source failure behavior tests."""

from conftest import FakeClock
from deskmate.config.loader import load_config
from deskmate.config.schema import DummyInputConfig
from deskmate.core.enums import SourceStatus, SystemStatus
from deskmate.input.dummy_source import DummyEventSource
from deskmate.pipeline.runner import PipelineRunner


def test_none_transitions_to_stalled_then_no_signal() -> None:
    clock = FakeClock()
    runner = PipelineRunner(load_config(), clock)
    runner.source = DummyEventSource(
        DummyInputConfig(mode="manual", scenario="dropout"), runner.config.sensor, clock
    )
    runner.source.open()
    clock.advance(1.5)
    runner._poll_once()
    assert runner.stats.source_status is SourceStatus.STALLED
    clock.advance(3.5)
    runner._poll_once()
    assert runner._system_status is SystemStatus.NO_SIGNAL


def test_no_signal_does_not_process_empty_windows() -> None:
    clock = FakeClock()
    runner = PipelineRunner(load_config(), clock)
    runner.source = DummyEventSource(
        DummyInputConfig(mode="manual", scenario="dropout"), runner.config.sensor, clock
    )
    runner.source.open()
    clock.advance(5)
    runner._poll_once()
    before = runner.stats.windows_processed
    clock.advance(1)
    runner._poll_once()
    assert runner.stats.windows_processed == before


def test_pipeline_reset_returns_to_starting() -> None:
    runner = PipelineRunner(load_config(), FakeClock())
    runner._system_status = SystemStatus.RUNNING
    runner._reset_components()
    assert runner._system_status is SystemStatus.STARTING
