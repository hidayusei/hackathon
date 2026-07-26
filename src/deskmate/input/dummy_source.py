"""Synthetic event source used for tests and camera-free demonstrations."""

import time

import numpy as np

from deskmate.config.schema import DummyInputConfig, SensorConfig
from deskmate.core.clock import Clock, SystemClock
from deskmate.core.enums import SourceStatus
from deskmate.core.types import EventBatch

from .base import EventSource
from .scenarios import DEMO_SEQUENCE, SCENARIOS, ScenarioSpec


class DummyEventSource(EventSource):
    """Generate vectorized synthetic events from a ScenarioSpec."""

    def __init__(
        self,
        config: DummyInputConfig,
        sensor: SensorConfig,
        clock: Clock | None = None,
    ) -> None:
        self._config = config
        self._sensor = sensor
        self._clock = clock or SystemClock()
        self._rng = np.random.default_rng(config.seed)
        self._status = SourceStatus.IDLE
        self._seq = 0
        self._sensor_us = 0
        self._elapsed_s = 0.0
        self._scenario_elapsed_s = 0.0
        self._scenario = config.scenario
        self._demo_index = 0
        self._next_emit = 0.0

    @property
    def name(self) -> str:
        """Return the current synthetic source name."""
        return f"dummy({self._scenario})"

    @property
    def status(self) -> SourceStatus:
        """Return the lifecycle state."""
        return self._status

    @property
    def current_scenario(self) -> str:
        """Return the active scenario identifier."""
        return self._scenario

    @property
    def elapsed_seconds(self) -> float:
        """Return represented sensor time since opening."""
        return self._elapsed_s

    def open(self) -> None:
        """Open the source idempotently."""
        self._status = SourceStatus.STREAMING
        self._next_emit = self._clock.monotonic()

    def close(self) -> None:
        """Close the source."""
        self._status = SourceStatus.CLOSED

    def set_scenario(self, scenario_id: str) -> None:
        """Fix the active scenario; raise ValueError for unknown ids."""
        if scenario_id not in SCENARIOS:
            raise ValueError(f"unknown scenario: {scenario_id}")
        self._scenario = scenario_id
        self._scenario_elapsed_s = 0.0

    def _advance_demo(self) -> None:
        if self._config.mode != "demo":
            return
        step = DEMO_SEQUENCE[self._demo_index]
        while self._scenario_elapsed_s >= step.duration_s:
            self._scenario_elapsed_s -= step.duration_s
            self._demo_index += 1
            if self._demo_index >= len(DEMO_SEQUENCE):
                self._demo_index = 0 if self._config.loop else len(DEMO_SEQUENCE) - 1
            step = DEMO_SEQUENCE[self._demo_index]
        self._scenario = step.scenario_id

    def _event_count(self, spec: ScenarioSpec, interval_s: float) -> int:
        jitter = 1.0 + self._rng.uniform(-spec.rate_jitter, spec.rate_jitter)
        decay = spec.rate_decay_per_s ** self._scenario_elapsed_s
        rate = spec.base_rate_eps * self._config.rate_scale * jitter * decay
        if spec.burst_period_s is not None:
            phase = (self._scenario_elapsed_s % spec.burst_period_s) / spec.burst_period_s
            if phase >= spec.burst_duty:
                rate *= 0.05
        return int(self._rng.poisson(max(0.0, rate * interval_s)))

    def _coordinates(self, spec: ScenarioSpec, count: int) -> tuple[np.ndarray, np.ndarray]:
        noise = self._rng.random(count) < spec.uniform_noise_ratio
        if spec.uniform_noise_ratio >= 0.9:
            noise = np.ones(count, dtype=bool)
        if spec.center_switch_s > 0:
            center_index = int(self._scenario_elapsed_s / spec.center_switch_s) % len(spec.centers)
        else:
            center_index = 0
        cx, cy = spec.centers[center_index]
        raw_drift = spec.drift_px_per_s * self._scenario_elapsed_s
        drift = (
            raw_drift
            if 0 < spec.center_switch_s < 1.0
            else min(raw_drift, min(self._sensor.width, self._sensor.height) * 0.25)
        )
        center_x = cx * self._sensor.width + np.sin(self._scenario_elapsed_s) * drift
        center_y = cy * self._sensor.height + np.cos(self._scenario_elapsed_s) * drift
        gaussian_x = self._rng.normal(center_x, spec.sigma_px, count)
        gaussian_y = self._rng.normal(center_y, spec.sigma_px, count)
        cell_indexes = np.arange(count, dtype=np.int64) % 256
        self._rng.shuffle(cell_indexes)
        cell_width = max(1, self._sensor.width // 16)
        cell_height = max(1, self._sensor.height // 16)
        uniform_x = (
            (cell_indexes % 16) * cell_width
            + self._rng.integers(0, cell_width, count)
        )
        uniform_y = (
            (cell_indexes // 16) * cell_height
            + self._rng.integers(0, cell_height, count)
        )
        x = np.where(noise, uniform_x, gaussian_x)
        y = np.where(noise, uniform_y, gaussian_y)
        return (
            np.clip(x, 0, self._sensor.width - 1).astype(np.uint16),
            np.clip(y, 0, self._sensor.height - 1).astype(np.uint16),
        )

    def read(self, timeout_s: float) -> EventBatch | None:
        """Return the next represented-time batch or None for dropout."""
        if self._status is not SourceStatus.STREAMING:
            return None
        interval_s = self._config.batch_interval_ms / 1000.0
        if timeout_s > 0:
            now = self._clock.monotonic()
            wait = max(0.0, self._next_emit - now)
            if wait > timeout_s:
                time.sleep(timeout_s)
                return None
            if wait > 0:
                time.sleep(wait)
            self._next_emit = max(self._next_emit + interval_s, self._clock.monotonic())
        self._advance_demo()
        spec = SCENARIOS[self._scenario]
        start_us = self._sensor_us
        end_us = start_us + int(self._config.batch_interval_ms * 1000)
        self._sensor_us = end_us
        self._elapsed_s += interval_s
        self._scenario_elapsed_s += interval_s
        if spec.dropout:
            return None
        count = self._event_count(spec, interval_s)
        x, y = self._coordinates(spec, count)
        t = np.sort(
            self._rng.integers(start_us, max(start_us + 1, end_us), count, dtype=np.int64)
        )
        p = (self._rng.random(count) < spec.positive_ratio).astype(np.int8)
        batch = EventBatch(
            x=x,
            y=y,
            t=t,
            p=p,
            t_start_us=start_us,
            t_end_us=end_us,
            seq=self._seq,
            received_monotonic=self._clock.monotonic(),
        )
        self._seq += 1
        return batch

    def request_stop(self) -> None:
        """Close immediately because reads do not block indefinitely."""
        self.close()
