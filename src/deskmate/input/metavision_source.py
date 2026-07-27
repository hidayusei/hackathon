"""Metavision live and RAW event input for Raspberry Pi."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Protocol

import numpy as np

from deskmate.config.schema import MetavisionInputConfig, SensorConfig
from deskmate.core.enums import SourceStatus
from deskmate.core.errors import SourceDisconnectedError, SourceOpenError
from deskmate.core.types import EventBatch

from .base import EventSource

LOGGER = logging.getLogger("deskmate.input.metavision")

_SETUP_HELP = (
    "Metavision input is unavailable. On Raspberry Pi run "
    "'sudo dtoverlay genx320,cam0', './rp5_setup_v4l.sh', and "
    "'export PSEE_VAR_V4L2_BSIZE=1' before starting DeskMate."
)


class _IteratorProtocol(Protocol):
    def __iter__(self) -> Iterator[np.ndarray]: ...

    def get_size(self) -> tuple[int, int]: ...


class MetavisionEventSource(EventSource):
    """Read live GenX320 events or a Metavision RAW recording."""

    def __init__(
        self, config: MetavisionInputConfig, sensor: SensorConfig
    ) -> None:
        self._config = config
        self._sensor = sensor
        self._status = SourceStatus.IDLE
        self._iterator: _IteratorProtocol | None = None
        self._stream: Iterator[np.ndarray] | None = None
        self._seq = 0
        self._last_end_us = 0
        self._sensor_size = (sensor.height, sensor.width)

    @property
    def name(self) -> str:
        """Return an explicit LIVE or RAW mode name."""

        if self._config.input_path:
            return "metavision(raw)"
        return "metavision(live)"

    @property
    def status(self) -> SourceStatus:
        """Return the source lifecycle state."""

        return self._status

    @property
    def sensor_size(self) -> tuple[int, int]:
        """Return the actual `(height, width)` reported by Metavision."""

        return self._sensor_size

    def open(self) -> None:
        """Open Metavision with a delayed platform-specific import."""

        if self._status is SourceStatus.STREAMING:
            return
        self._status = SourceStatus.CONNECTING
        try:
            from metavision_core.event_io import EventsIterator

            iterator = EventsIterator(
                input_path=self._config.input_path,
                delta_t=self._config.delta_t_us,
                relative_timestamps=False,
            )
            stream = iter(iterator)
            height, width = iterator.get_size()
        except Exception as exc:  # noqa: BLE001 - SDK raises platform-specific errors
            self._status = SourceStatus.ERROR
            raise SourceOpenError(_SETUP_HELP) from exc

        if (width, height) != (self._sensor.width, self._sensor.height):
            LOGGER.warning(
                "Metavision sensor resolution differs from config; using SDK size %sx%s",
                width,
                height,
            )
            self._sensor.width = int(width)
            self._sensor.height = int(height)
        self._sensor_size = (int(height), int(width))
        self._iterator = iterator
        self._stream = stream
        self._seq = 0
        self._last_end_us = 0
        self._status = SourceStatus.STREAMING

    def read(self, timeout_s: float) -> EventBatch | None:
        """Read one Metavision delta-t batch."""

        del timeout_s
        if self._stream is None or self._status is not SourceStatus.STREAMING:
            raise SourceDisconnectedError("Metavision source is not open")
        try:
            events = next(self._stream)
        except StopIteration as exc:
            self._status = SourceStatus.DISCONNECTED
            raise SourceDisconnectedError("Metavision event stream ended") from exc
        structured = np.asarray(events)
        if structured.size == 0:
            start_us = self._last_end_us
            batch = EventBatch.empty(
                start_us,
                start_us + self._config.delta_t_us,
                self._seq,
            )
        else:
            batch = EventBatch.from_structured(structured, self._seq)
        self._last_end_us = batch.t_end_us
        self._seq += 1
        return batch

    def close(self) -> None:
        """Release the SDK iterator without propagating cleanup errors."""

        try:
            self._stream = None
            self._iterator = None
        except Exception as exc:  # noqa: BLE001 - cleanup must remain idempotent
            LOGGER.warning("failed to release Metavision iterator: %s", exc)
        self._status = SourceStatus.CLOSED

    def request_stop(self) -> None:
        """Release the iterator to unblock acquisition when supported."""

        self.close()
