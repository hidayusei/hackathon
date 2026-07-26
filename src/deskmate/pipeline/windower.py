"""Sensor-time event windowing."""

import numpy as np

from deskmate.core.errors import ConfigError, PipelineError
from deskmate.core.types import EventBatch, EventWindow


class EventWindower:
    """Split event batches into fixed or overlapping sensor-time windows."""

    def __init__(self, window_ms: int, stride_ms: int, max_events_per_window: int) -> None:
        if not 50 <= window_ms <= 2000:
            raise ConfigError("window_ms must be in [50, 2000]")
        if stride_ms <= 0 or stride_ms > window_ms:
            raise ConfigError("stride_ms must be positive and <= window_ms")
        self._window_us = window_ms * 1000
        self._stride_us = stride_ms * 1000
        self._limit = max_events_per_window
        self.reset()

    def reset(self) -> None:
        """Clear buffered events and reset the window counter."""
        self._x = np.empty(0, dtype=np.uint16)
        self._y = np.empty(0, dtype=np.uint16)
        self._t = np.empty(0, dtype=np.int64)
        self._p = np.empty(0, dtype=np.int8)
        self._origin_us: int | None = None
        self._next_start_us: int | None = None
        self._latest_end_us: int | None = None
        self._last_event_us: int | None = None
        self._window_index = 0

    @property
    def window_index(self) -> int:
        """Return the next output window index."""
        return self._window_index

    @property
    def buffered_events(self) -> int:
        """Return the number of currently retained events."""
        return int(self._t.size)

    @property
    def latest_end_us(self) -> int | None:
        """Return the newest observed sensor end time, or None before the first batch.

        Callers use this as the anchor when extrapolating sensor time for flush_idle().
        """
        return self._latest_end_us

    def _window(self, start: int) -> EventWindow:
        end = start + self._window_us
        mask = (self._t >= start) & (self._t < end)
        indexes = np.flatnonzero(mask)
        truncated = indexes.size > self._limit
        if truncated:
            indexes = indexes[np.linspace(0, indexes.size - 1, self._limit, dtype=np.int64)]
        window = EventWindow(
            self._x[indexes].copy(),
            self._y[indexes].copy(),
            self._t[indexes].copy(),
            self._p[indexes].copy(),
            self._window_index,
            start,
            end,
            self._window_us / 1_000_000.0,
            truncated,
        )
        self._window_index += 1
        return window

    def _emit_until(self, sensor_end_us: int) -> list[EventWindow]:
        windows: list[EventWindow] = []
        while (
            self._next_start_us is not None
            and self._next_start_us + self._window_us <= sensor_end_us
        ):
            windows.append(self._window(self._next_start_us))
            self._next_start_us += self._stride_us
            keep_from = self._next_start_us
            keep = self._t >= keep_from
            self._x, self._y, self._t, self._p = (
                self._x[keep],
                self._y[keep],
                self._t[keep],
                self._p[keep],
            )
        return windows

    def push(self, batch: EventBatch) -> list[EventWindow]:
        """Consume one batch and return all newly closed windows."""
        if batch.size and self._last_event_us is not None and int(batch.t[0]) < self._last_event_us:
            raise PipelineError("sensor timestamp moved backwards")
        if batch.size:
            self._last_event_us = int(batch.t[-1])
        if self._origin_us is None:
            self._origin_us = batch.t_start_us if batch.size == 0 else int(batch.t[0])
            self._next_start_us = self._origin_us
        if batch.size:
            self._x = np.concatenate((self._x, batch.x))
            self._y = np.concatenate((self._y, batch.y))
            self._t = np.concatenate((self._t, batch.t))
            self._p = np.concatenate((self._p, batch.p))
        self._latest_end_us = batch.t_end_us
        return self._emit_until(batch.t_end_us)

    def flush_idle(self, now_sensor_us: int) -> list[EventWindow]:
        """Close windows through an extrapolated sensor time."""
        if self._origin_us is None:
            self._origin_us = now_sensor_us
            self._next_start_us = now_sensor_us
            return []
        if self._latest_end_us is not None and now_sensor_us < self._latest_end_us:
            raise PipelineError("idle flush timestamp moved backwards")
        self._latest_end_us = now_sensor_us
        return self._emit_until(now_sensor_us)
