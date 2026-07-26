"""JSONL and canonical NPZ event playback."""

import json

import numpy as np

from deskmate.config.schema import FileInputConfig, SensorConfig
from deskmate.core.enums import SourceStatus
from deskmate.core.errors import DecodeError, SourceOpenError
from deskmate.core.types import EVENT_DTYPE, EventBatch

from .base import EventSource


class FileEventSource(EventSource):
    """Replay validated event files with adjustable represented-time speed."""

    def __init__(self, config: FileInputConfig, sensor: SensorConfig) -> None:
        self._config = config
        self._sensor = sensor
        self._status = SourceStatus.IDLE
        self._events = np.empty(0, dtype=EVENT_DTYPE)
        self._cursor = 0
        self._seq = 0

    @property
    def name(self) -> str:
        """Return a path-independent source label."""
        return "file"

    @property
    def status(self) -> SourceStatus:
        """Return playback state."""
        return self._status

    @property
    def supports_seek(self) -> bool:
        """File playback supports seek."""
        return True

    def _load_jsonl(self) -> np.ndarray:
        assert self._config.path is not None
        records: list[dict[str, object]] = []
        try:
            with self._config.path.open("r", encoding="utf-8") as stream:
                for line in stream:
                    if line.strip():
                        value = json.loads(line)
                        if not isinstance(value, dict):
                            raise ValueError("event line must be an object")
                        records.append(value)
            batch = EventBatch.from_records(records, 0)
        except (OSError, json.JSONDecodeError, ValueError, DecodeError) as exc:
            raise SourceOpenError("invalid JSONL event file") from exc
        result = np.empty(batch.size, dtype=EVENT_DTYPE)
        for name in EVENT_DTYPE.names or ():
            result[name] = getattr(batch, name)
        return result

    def _load_npz(self) -> np.ndarray:
        assert self._config.path is not None
        try:
            with np.load(self._config.path, allow_pickle=False) as archive:
                if "events" not in archive:
                    raise SourceOpenError("NPZ requires an events array")
                batch = EventBatch.from_structured(archive["events"], 0)
                if "width" in archive and int(archive["width"]) != self._sensor.width:
                    raise SourceOpenError("NPZ sensor width does not match configuration")
                if "height" in archive and int(archive["height"]) != self._sensor.height:
                    raise SourceOpenError("NPZ sensor height does not match configuration")
        except (OSError, ValueError, DecodeError) as exc:
            raise SourceOpenError("invalid NPZ event file") from exc
        result = np.empty(batch.size, dtype=EVENT_DTYPE)
        for name in EVENT_DTYPE.names or ():
            result[name] = getattr(batch, name)
        return result

    def open(self) -> None:
        """Load and validate the configured event file."""
        if self._status is SourceStatus.STREAMING:
            return
        path = self._config.path
        if path is None or not path.exists():
            raise SourceOpenError("input file does not exist")
        if path.suffix.lower() == ".jsonl":
            self._events = self._load_jsonl()
        elif path.suffix.lower() == ".npz":
            self._events = self._load_npz()
        else:
            raise SourceOpenError("supported file extensions are .jsonl and .npz")
        if self._events.size and (
            np.any(self._events["x"] >= self._sensor.width)
            or np.any(self._events["y"] >= self._sensor.height)
        ):
            raise SourceOpenError("event coordinate is outside configured sensor")
        self._cursor = 0
        self._seq = 0
        self._status = SourceStatus.STREAMING

    def close(self) -> None:
        """Close playback without discarding validated memory."""
        self._status = SourceStatus.CLOSED

    def seek(self, position_ratio: float) -> None:
        """Seek to a clamped fractional event position."""
        ratio = min(1.0, max(0.0, position_ratio))
        self._cursor = min(int(self._events.size * ratio), max(0, self._events.size - 1))
        if self._events.size:
            self._status = SourceStatus.STREAMING

    def read(self, timeout_s: float) -> EventBatch | None:
        """Return the next represented-time slice."""
        if self._status is not SourceStatus.STREAMING:
            return None
        if self._cursor >= self._events.size:
            if self._config.loop and self._events.size:
                self._cursor = 0
            else:
                self._status = SourceStatus.CLOSED
                return None
        if not self._events.size:
            self._status = SourceStatus.CLOSED
            return None
        start = self._cursor
        start_t = int(self._events["t"][start])
        interval_us = max(1, int(20_000 * self._config.speed))
        end = int(np.searchsorted(self._events["t"], start_t + interval_us, side="left"))
        end = max(start + 1, min(end, self._events.size))
        batch = EventBatch.from_structured(self._events[start:end], self._seq)
        self._cursor = end
        self._seq += 1
        return batch
