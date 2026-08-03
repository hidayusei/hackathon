"""Qt signal-emitting pipeline integration."""

from __future__ import annotations

import logging
from dataclasses import replace
from time import perf_counter, sleep

import numpy as np
from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, Signal, Slot

from deskmate.config.schema import AppConfig
from deskmate.core.clock import Clock, SystemClock
from deskmate.core.enums import (
    AnimationId,
    DeskStatus,
    SourceStatus,
    SystemStatus,
)
from deskmate.core.errors import DecodeError, PipelineError, PrivacyViolationError, SourceError
from deskmate.core.types import (
    DetailFrame,
    EventWindow,
    PipelineStats,
    StatusEstimate,
    StatusSnapshot,
)
from deskmate.input.factory import create_event_source
from deskmate.network.udp_sender import UdpEventSender
from deskmate.privacy.guard import PrivacyGuard

from .break_tracker import BreakTracker
from .duration import DurationTracker
from .estimator import create_estimator
from .features import BackgroundEventFilter, FeatureExtractor
from .history import FeatureHistory
from .regions import RegionMap, RegionRect
from .smoother import StatusSmoother
from .windower import EventWindower

LOGGER = logging.getLogger("deskmate.pipeline.runner")


class PipelineRunner(QObject):
    """Own and execute the processing pipeline in a worker thread."""

    snapshot_ready = Signal(object)
    status_changed = Signal(object)
    detail_ready = Signal(object)
    stats_updated = Signal(object)
    source_state = Signal(str, str)
    error_occurred = Signal(str, str)

    def __init__(self, config: AppConfig, clock: Clock | None = None) -> None:
        super().__init__()
        self.config = config
        self.clock = clock or SystemClock()
        rects = [RegionRect(item.id, *item.rect) for item in config.regions]
        mapping = RegionMap(rects, config.sensor.width, config.sensor.height)
        self.windower = EventWindower(
            config.window.window_ms,
            config.window.stride_ms,
            config.window.max_events_per_window,
        )
        self.extractor = FeatureExtractor(
            config.features,
            config.sensor,
            mapping,
            config.window.grid_cols,
            config.window.grid_rows,
            config.estimation.idle_eps,
        )
        self.background_filter = BackgroundEventFilter(
            config.sensor,
            config.ui.detail.calibration_seconds,
            config.estimation.background_residual_eps,
        )
        self._background_enabled = False
        self.history = FeatureHistory(config.features, config.estimation, config.sensor)
        self.estimator = create_estimator(config.estimation)
        self.smoother = StatusSmoother(config.smoothing, self.clock)
        self.duration = DurationTracker(
            history_retention_minutes=config.privacy.history_retention_minutes
        )
        self.break_tracker = BreakTracker(config.break_prompt, self.clock)
        self.source = None
        self.udp_sender = UdpEventSender(config.udp.output, PrivacyGuard(config.privacy))
        self._running = False
        self._paused = False
        self._detail_subscription = False
        self._forced_status: DeskStatus | None = config.debug.force_status
        self._system_status = SystemStatus.STARTING
        self._last_snapshot: StatusSnapshot | None = None
        self._last_data_at = self.clock.monotonic()
        self._open_retries = 0
        self._last_stats_at: float | None = None
        self._unexpected_errors: list[float] = []
        self.stats = PipelineStats(0, 0, 0.0, 0.0, SourceStatus.IDLE, "", 0)

    def _reset_components(self) -> None:
        self.windower.reset()
        self.extractor.reset()
        self.background_filter.reset()
        self.history.reset()
        self.estimator.reset()
        self.smoother.reset()
        self.duration.reset()
        self.break_tracker.reset()
        self._system_status = SystemStatus.STARTING

    @Slot()
    def start(self) -> None:
        """Open the configured source and process until stopped."""
        if self._running:
            return
        self.source = create_event_source(self.config.input, self.config.sensor)
        self.udp_sender.open()
        self._configure_source_profile(self.source.name)
        self._running = True
        self.stats.source_name = self._source_display_name()
        try:
            self.source.open()
            self.stats.source_status = self.source.status
            self.source_state.emit(
                self.source.status.value, self.stats.source_name
            )
        except SourceError as exc:
            self._handle_source_error(exc)
        self._loop()

    def _configure_source_profile(self, source_name: str) -> None:
        """Select calibrated live-camera rules without changing dummy rules."""
        self._background_enabled = source_name.startswith("metavision")
        estimation = self.config.estimation
        if self._background_enabled:
            camera = estimation.metavision
            estimation = estimation.model_copy(
                update={
                    "idle_eps": camera.idle_eps,
                    "focus_min_eps": camera.focus_min_eps,
                    "focus_region_share": camera.focus_region_share,
                    "focus_max_bbox_area_ratio": camera.focus_max_bbox_area_ratio,
                    "focus_max_activity_cv": camera.focus_max_activity_cv,
                }
            )
        self.extractor.set_idle_eps(estimation.idle_eps)
        self.estimator = create_estimator(estimation)

    @Slot()
    def stop(self) -> None:
        """Stop processing and close the source idempotently."""
        self._running = False
        if self.source is not None:
            self.source.request_stop()
            self.source.close()
        self.udp_sender.close()

    @Slot(bool)
    def set_paused(self, paused: bool) -> None:
        """Pause or reset and resume processing.

        The acquisition loop keeps running while paused but stops reading the source,
        so resuming needs no restart. Resuming resets every stateful component so the
        pipeline warms up again instead of continuing from stale history.
        """
        if self._paused == paused:
            return
        self._paused = paused
        if paused:
            self._system_status = SystemStatus.PAUSED
            self._emit_system_snapshot(SystemStatus.PAUSED)
        else:
            self._reset_components()
            self._last_data_at = self.clock.monotonic()

    @Slot(bool)
    def set_detail_subscription(self, enabled: bool) -> None:
        """Enable private DetailFrame generation."""
        self._detail_subscription = enabled

    @Slot(str)
    def set_scenario(self, scenario_id: str) -> None:
        """Change a dummy scenario if the active source supports it."""
        if self.source is not None and hasattr(self.source, "set_scenario"):
            self.source.set_scenario(scenario_id)

    @Slot(str)
    def force_status(self, status_value: str) -> None:
        """Fix the state only when debug mode is enabled."""
        if not self.config.debug.enabled:
            return
        self._forced_status = DeskStatus(status_value) if status_value else None

    @Slot()
    def request_reconnect(self) -> None:
        """Reset and reopen the current source."""
        if self.source is not None:
            self.source.reset()
            self._reset_components()

    @Slot()
    def snooze_break(self) -> None:
        """Snooze an active break prompt."""

        self.break_tracker.snooze(self.clock.monotonic())

    @Slot()
    def acknowledge_break(self) -> None:
        """Acknowledge the prompt and reset focused time."""

        self.break_tracker.acknowledge(self.clock.monotonic())

    def _source_display_name(self) -> str:
        if self.source is None:
            return ""
        reason = getattr(self.source, "resolution_reason", "")
        return f"{self.source.name} - {reason}" if reason else self.source.name

    def _loop(self) -> None:
        idle_wait = self.config.input.poll_timeout_ms / 1000
        while self._running:
            # start() deliberately owns this worker thread with a blocking while
            # loop.  Process its Qt event queue between reads so UiBridge's queued
            # control calls can run on the same thread as EventSource operations.
            QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)
            if not self._running:
                break
            if self._paused:
                # Stay alive without touching the source.  The next iteration
                # processes the queued resume request before checking this flag.
                sleep(idle_wait)
                continue
            try:
                self._poll_once()
            except DecodeError as exc:
                LOGGER.warning("discarded invalid input batch: %s", exc)
            except PipelineError as exc:
                LOGGER.warning("resetting pipeline: %s", exc)
                self._reset_components()
            except PrivacyViolationError:
                raise
            except SourceError as exc:
                self._handle_source_error(exc)
            except Exception as exc:  # noqa: BLE001 - must not kill the worker thread
                self._handle_unexpected_error(exc)
            self._emit_stats_if_due()

    def _handle_unexpected_error(self, exc: Exception) -> None:
        """Log an unexpected error and stop only if they arrive too fast."""
        LOGGER.exception("unexpected pipeline error: %s", exc)
        self.error_occurred.emit(type(exc).__name__, str(exc))
        now = self.clock.monotonic()
        self._unexpected_errors = [at for at in self._unexpected_errors if now - at < 60.0]
        self._unexpected_errors.append(now)
        if len(self._unexpected_errors) > 3:
            LOGGER.error("too many unexpected errors in one minute; stopping pipeline")
            self._system_status = SystemStatus.ERROR
            self._emit_system_snapshot(SystemStatus.ERROR)
            self._running = False

    def _emit_stats_if_due(self) -> None:
        """Publish an immutable stats copy at most once per second."""
        now = self.clock.monotonic()
        if self._last_stats_at is not None and now - self._last_stats_at < 1.0:
            return
        self._last_stats_at = now
        self.stats_updated.emit(self._stats_copy())

    def _stats_copy(self) -> PipelineStats:
        """Return a detached copy so receivers never observe live mutation."""
        return replace(self.stats)

    def _poll_once(self) -> None:
        """Perform one acquisition poll for deterministic failure tests."""
        assert self.source is not None
        batch = self.source.read(self.config.input.poll_timeout_ms / 1000)
        now = self.clock.monotonic()
        if batch is None:
            elapsed_ms = (now - self._last_data_at) * 1000
            if elapsed_ms >= self.config.input.disconnect_timeout_ms:
                self._system_status = SystemStatus.NO_SIGNAL
                self.stats.source_status = SourceStatus.DISCONNECTED
                self._emit_system_snapshot(SystemStatus.NO_SIGNAL)
                return
            if elapsed_ms >= self.config.input.stall_timeout_ms:
                self.stats.source_status = SourceStatus.STALLED
                self.source_state.emit(SourceStatus.STALLED.value, self.source.name)
                sensor_now = (
                    self.windower.latest_end_us or 0
                ) + self.config.input.poll_timeout_ms * 1000
                for window in self.windower.flush_idle(sensor_now):
                    self._process_window(window)
            return
        self._last_data_at = now
        try:
            self.udp_sender.send(batch)
        except PrivacyViolationError:
            raise
        except OSError as exc:
            LOGGER.warning("UDP event send failed: %s", exc)
        self.stats.source_status = self.source.status
        self.stats.source_name = self._source_display_name()
        for window in self.windower.push(batch):
            self._process_window(window)

    def _status_label(
        self,
        status: DeskStatus,
        system: SystemStatus,
    ) -> str:
        try:
            from deskmate.ui.labels import resolve_label

            return resolve_label(status, system)
        except ImportError:
            return status.value if system is SystemStatus.RUNNING else system.value

    def _animation(
        self, status: DeskStatus, break_due: bool, system: SystemStatus
    ) -> AnimationId:
        try:
            from deskmate.character.mapping import resolve_animation

            return resolve_animation(status, break_due, system)
        except ImportError:
            return AnimationId.SITTING

    def _process_window(self, window: EventWindow) -> StatusSnapshot:
        """Synchronously process one window; exposed for deterministic tests."""
        started = perf_counter()
        raw_event_count = window.x.size
        processed_window = (
            self.background_filter.apply(window)
            if self._background_enabled
            else window
        )
        frame = self.extractor.extract(processed_window)
        smoothed = self.history.update(frame)
        estimate = self.estimator.estimate(frame, smoothed)
        if self._forced_status is not None:
            estimate = StatusEstimate(self._forced_status, 1.0, "debug_force", "forced")
        now = self.clock.monotonic()
        background_ready = (
            not self._background_enabled or self.background_filter.ready
        )
        if self.history.is_warm and background_ready:
            self._system_status = SystemStatus.RUNNING
        result = self.smoother.update(
            estimate,
            now,
            force_away=smoothed.idle_seconds >= self.config.estimation.away_seconds,
        )
        duration = self.duration.update(result.status, result.changed, result.confidence, now)
        break_state = self.break_tracker.update(
            result.status,
            self._system_status,
            processed_window.duration_s,
            now,
        )
        snapshot = StatusSnapshot(
            result.status,
            self._system_status,
            self._status_label(result.status, self._system_status),
            self._animation(result.status, break_state.break_due, self._system_status),
            duration,
            result.confidence,
            break_state.focus_streak_seconds,
            break_state.break_due,
            result.changed,
            self.clock.now(),
        )
        elapsed_ms = (perf_counter() - started) * 1000
        self.stats.windows_processed += 1
        self.stats.last_compute_ms = elapsed_ms
        count = self.stats.windows_processed
        self.stats.avg_compute_ms += (elapsed_ms - self.stats.avg_compute_ms) / count
        self._last_snapshot = snapshot
        self.snapshot_ready.emit(snapshot)
        if snapshot.changed:
            self.status_changed.emit(snapshot)
        if self._detail_subscription:
            preview_window = processed_window
            if self._background_enabled:
                preview_window = (
                    self.background_filter.preview_window or processed_window
                )
            step = self._preview_step(preview_window.x.size)
            detail = DetailFrame(
                snapshot,
                frame,
                smoothed,
                estimate,
                preview_window.x[::step].copy(),
                preview_window.y[::step].copy(),
                preview_window.p[::step].copy(),
                self.duration.history,
                self.history.rate_series(60),
                self._stats_copy(),
                int(raw_event_count),
                (
                    self.background_filter.remaining_seconds
                    if self._background_enabled
                    else 0.0
                ),
            )
            self.detail_ready.emit(detail)
        return snapshot

    def _preview_step(self, size: int) -> int:
        """Return a stride that decimates across the whole window.

        Slicing the first N events would show only the earliest part of the window,
        because events are ordered by sensor time.
        """
        limit = self.config.ui.detail.max_preview_points
        if size <= limit or limit <= 0:
            return 1
        return int(size // limit) + 1

    def _emit_system_snapshot(self, status: SystemStatus) -> None:
        base_status = DeskStatus.IDLE
        changed = self._last_snapshot is None or self._last_snapshot.system_status is not status
        snapshot = StatusSnapshot(
            base_status,
            status,
            self._status_label(base_status, status),
            self._animation(base_status, False, status),
            0.0,
            0.0,
            self.break_tracker.state.focus_streak_seconds,
            False,
            changed,
            self.clock.now(),
        )
        self._last_snapshot = snapshot
        self.snapshot_ready.emit(snapshot)

    def _handle_source_error(self, exc: Exception) -> None:
        LOGGER.error("input source error: %s", exc)
        self._system_status = SystemStatus.NO_SIGNAL
        self.error_occurred.emit(type(exc).__name__, str(exc))
        self.source_state.emit(
            SourceStatus.ERROR.value, self._source_display_name()
        )
        self._emit_system_snapshot(SystemStatus.NO_SIGNAL)
        if self.source is None:
            return
        # Wait before retrying so a persistently failing source cannot spin the loop.
        sleep(self.config.input.reconnect_interval_ms / 1000)
        try:
            self.source.reset()
            self._open_retries = 0
            self._reset_components()
            self._last_data_at = self.clock.monotonic()
        except SourceError as reconnect_error:
            self._open_retries += 1
            LOGGER.error("reconnect failed: %s", reconnect_error)
            if self._open_retries >= self.config.input.max_open_retries:
                # Stay in ERROR but keep retrying on the throttle so the pipeline
                # can recover on its own once the source comes back.
                self._system_status = SystemStatus.ERROR
                self._emit_system_snapshot(SystemStatus.ERROR)
