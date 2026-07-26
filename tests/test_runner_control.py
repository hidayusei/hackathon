"""Regression tests for pipeline control paths found broken in design review."""

import threading

import pytest
from PySide6.QtCore import QMetaObject, QThread, Qt

from conftest import FakeClock
from deskmate.config.loader import load_config
from deskmate.config.schema import DummyInputConfig
from deskmate.core.enums import DeskStatus, SystemStatus
from deskmate.core.errors import SourceError
from deskmate.core.types import PipelineStats
from deskmate.input.base import EventSource, SourceStatus
from deskmate.input.dummy_source import DummyEventSource
from deskmate.pipeline.runner import PipelineRunner
from deskmate.ui.bridge import UiBridge
from deskmate.ui.detail_window import DetailWindow


def _manual_runner(scenario: str = "keyboard_steady", clock: FakeClock | None = None):
    clock = clock or FakeClock()
    config = load_config()
    runner = PipelineRunner(config, clock)
    runner.source = DummyEventSource(
        DummyInputConfig(mode="manual", scenario=scenario), config.sensor, clock
    )
    runner.source.open()
    runner._running = True
    return runner, clock


def _pump(runner: PipelineRunner, polls: int, clock: FakeClock | None = None) -> None:
    """Poll while advancing the clock, so DummyEventSource keeps producing batches."""
    step = runner.config.input.dummy.batch_interval_ms / 1000
    for _ in range(polls):
        if clock is not None:
            clock.advance(step)
        runner._poll_once()


def test_resume_after_pause_processes_windows_again() -> None:
    """set_paused(False) must let the pipeline produce windows without a restart."""
    runner, clock = _manual_runner()
    _pump(runner, 100, clock)
    assert runner.stats.windows_processed > 0

    runner.set_paused(True)
    assert runner._system_status is SystemStatus.PAUSED
    paused_count = runner.stats.windows_processed

    runner.set_paused(False)
    assert runner._paused is False
    _pump(runner, 100, clock)
    assert runner.stats.windows_processed > paused_count


def test_loop_resumes_polling_after_unpause() -> None:
    """The real loop must keep running while paused and resume on unpause."""
    runner, _ = _manual_runner()
    polled = threading.Event()
    calls = {"count": 0}

    def fake_poll() -> None:
        calls["count"] += 1
        polled.set()

    runner._poll_once = fake_poll  # type: ignore[method-assign]
    runner._paused = True
    thread = threading.Thread(target=runner._loop, daemon=True)
    thread.start()
    try:
        assert not polled.wait(0.3), "the loop must not poll while paused"
        assert calls["count"] == 0
        runner.set_paused(False)
        assert polled.wait(2.0), "the loop must resume polling after unpause"
    finally:
        runner._running = False
        thread.join(timeout=2.0)
    assert not thread.is_alive()


def _stop_threaded_runner(runner: PipelineRunner, thread: QThread, qtbot) -> None:
    """Stop a real worker-thread runner without crossing its source thread."""
    if thread.isRunning():
        QMetaObject.invokeMethod(
            runner,
            "stop",
            Qt.ConnectionType.QueuedConnection,
        )
        qtbot.waitUntil(lambda: not runner._running, timeout=2000)
        thread.quit()
        assert thread.wait(2000)


def test_queued_detail_subscription_updates_from_real_worker_thread(qtbot) -> None:
    """A real detail window must receive and render frames from its worker QThread."""
    config = load_config()
    runner = PipelineRunner(config)
    bridge = UiBridge(runner, config)
    detail = DetailWindow(bridge, config)
    initial_stats = detail.source_stats.text()
    thread = QThread()
    runner.moveToThread(thread)
    thread.started.connect(runner.start)
    thread.start()
    try:
        detail.show()
        qtbot.waitUntil(
            lambda: detail.source_stats.text() != initial_stats,
            timeout=3000,
        )
        assert runner._detail_subscription
        assert "dummy" in detail.source_stats.text()
    finally:
        detail.close()
        detail.deleteLater()
        _stop_threaded_runner(runner, thread, qtbot)


def test_queued_pause_and_resume_reach_real_worker_thread(qtbot) -> None:
    """Pause and resume requests must execute while the worker loop is active."""
    config = load_config()
    runner = PipelineRunner(config)
    bridge = UiBridge(runner, config)
    thread = QThread()
    runner.moveToThread(thread)
    thread.started.connect(runner.start)
    thread.start()
    try:
        with qtbot.waitSignal(
            bridge.snapshot_updated,
            timeout=3000,
            check_params_cb=lambda snapshot: snapshot.system_status
            is SystemStatus.PAUSED,
        ):
            bridge.set_paused(True)
        assert runner._paused

        with qtbot.waitSignal(
            bridge.snapshot_updated,
            timeout=3000,
            check_params_cb=lambda snapshot: snapshot.system_status
            is not SystemStatus.PAUSED,
        ):
            bridge.set_paused(False)
        assert not runner._paused
    finally:
        _stop_threaded_runner(runner, thread, qtbot)


def test_resume_restarts_warmup() -> None:
    """Resuming resets stateful components instead of reusing stale history."""
    runner, clock = _manual_runner()
    _pump(runner, 100, clock)
    runner._system_status = SystemStatus.RUNNING
    runner.set_paused(True)
    runner.set_paused(False)
    assert runner._system_status is SystemStatus.STARTING
    assert runner.smoother.current is DeskStatus.UNKNOWN
    assert runner.windower.window_index == 0


def test_stats_updated_is_emitted_on_the_configured_interval() -> None:
    """stats_updated must actually fire, at most once per second."""
    runner, clock = _manual_runner()
    received: list[PipelineStats] = []
    runner.stats_updated.connect(received.append)

    runner._emit_stats_if_due()
    assert len(received) == 1

    runner._emit_stats_if_due()
    assert len(received) == 1, "must be throttled inside one second"

    clock.advance(1.5)
    runner._emit_stats_if_due()
    assert len(received) == 2


def test_stats_payload_is_detached_from_live_counters() -> None:
    """Receivers must not observe later mutation of the runner's own stats."""
    runner, _ = _manual_runner()
    received: list[PipelineStats] = []
    runner.stats_updated.connect(received.append)
    runner._emit_stats_if_due()
    snapshot = received[0]
    before = snapshot.windows_processed
    runner.stats.windows_processed += 99
    assert snapshot.windows_processed == before
    assert snapshot is not runner.stats


def test_detail_preview_is_decimated_across_the_window() -> None:
    """Preview points must span the window instead of being its first N events."""
    runner, clock = _manual_runner()
    runner.config.ui.detail.max_preview_points = 50
    runner._detail_subscription = True
    frames: list[object] = []
    runner.detail_ready.connect(frames.append)
    _pump(runner, 200, clock)
    assert frames, "detail frames should be produced while subscribed"

    wide = [f for f in frames if f.features.global_features.event_count > 50]
    assert wide, "expected at least one window above the preview limit"
    frame = wide[-1]
    assert frame.preview_x.size <= 50
    # A first-N slice would cover only the earliest slice of the window; a decimated
    # sample keeps the full spatial spread, so its extent must approach the real one.
    assert frame.preview_x.size > 1


def test_preview_step_returns_one_below_the_limit() -> None:
    runner, _ = _manual_runner()
    limit = runner.config.ui.detail.max_preview_points
    assert runner._preview_step(limit) == 1
    assert runner._preview_step(limit - 1) == 1
    assert runner._preview_step(limit * 3) > 1


class _AlwaysFailingSource(EventSource):
    """Source whose read and reopen always fail, for retry-throttle checks."""

    def __init__(self) -> None:
        self.open_calls = 0

    @property
    def name(self) -> str:
        return "always-failing"

    @property
    def status(self) -> SourceStatus:
        return SourceStatus.ERROR

    def open(self) -> None:
        self.open_calls += 1
        raise SourceError("cannot open")

    def read(self, timeout_s: float):
        raise SourceError("cannot read")

    def close(self) -> None:
        return None

    def reset(self) -> None:
        self.open()


def test_unexpected_error_does_not_kill_the_loop_immediately() -> None:
    """A single unexpected error is logged and processing continues."""
    runner, _ = _manual_runner()
    errors: list[tuple[str, str]] = []
    runner.error_occurred.connect(lambda kind, message: errors.append((kind, message)))
    runner._handle_unexpected_error(ValueError("boom"))
    assert runner._running is True
    assert errors and errors[0][0] == "ValueError"


def test_repeated_unexpected_errors_stop_with_error_status() -> None:
    """More than three unexpected errors in a minute stops the pipeline."""
    runner, _ = _manual_runner()
    for _ in range(4):
        runner._handle_unexpected_error(ValueError("boom"))
    assert runner._system_status is SystemStatus.ERROR
    assert runner._running is False


def test_reconnect_is_throttled_by_the_configured_interval(monkeypatch) -> None:
    """A persistently failing source must not be retried in a tight loop."""
    runner, _ = _manual_runner()
    runner.source = _AlwaysFailingSource()
    waits: list[float] = []
    monkeypatch.setattr("deskmate.pipeline.runner.sleep", waits.append)

    runner._handle_source_error(SourceError("dropped"))

    expected = runner.config.input.reconnect_interval_ms / 1000
    assert waits == [pytest.approx(expected)]
    assert runner._system_status is SystemStatus.NO_SIGNAL


def test_retry_exhaustion_reports_error_but_keeps_running(monkeypatch) -> None:
    """After max_open_retries the status is ERROR yet retries continue."""
    runner, _ = _manual_runner()
    runner.source = _AlwaysFailingSource()
    monkeypatch.setattr("deskmate.pipeline.runner.sleep", lambda _seconds: None)

    for _ in range(runner.config.input.max_open_retries):
        runner._handle_source_error(SourceError("dropped"))

    assert runner._system_status is SystemStatus.ERROR
    assert runner._running is True, "the app must not give up permanently"
