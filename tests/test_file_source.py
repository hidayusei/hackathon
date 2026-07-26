"""Step 13 file playback tests."""

import json
from pathlib import Path

import numpy as np
import pytest

from deskmate.config.schema import FileInputConfig, SensorConfig
from deskmate.core.enums import SourceStatus
from deskmate.core.errors import SourceOpenError
from deskmate.core.types import EVENT_DTYPE
from deskmate.input.file_source import FileEventSource


def _events(count: int = 10) -> np.ndarray:
    events = np.empty(count, dtype=EVENT_DTYPE)
    events["x"] = np.arange(count)
    events["y"] = np.arange(count)
    events["t"] = np.arange(count) * 10_000
    events["p"] = np.arange(count) % 2
    return events


def _read_all(source: FileEventSource, limit: int = 100) -> int:
    total = 0
    for _ in range(limit):
        batch = source.read(0)
        if batch is None:
            break
        total += batch.size
    return total


def test_jsonl_event_count_matches(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text(
        "\n".join(json.dumps({name: int(row[name]) for name in EVENT_DTYPE.names}) for row in _events()),
        encoding="utf-8",
    )
    source = FileEventSource(FileInputConfig(path=path, loop=False), SensorConfig())
    source.open()
    assert _read_all(source) == 10


def test_npz_event_count_matches(tmp_path: Path) -> None:
    path = tmp_path / "events.npz"
    np.savez(path, events=_events())
    source = FileEventSource(FileInputConfig(path=path, loop=False), SensorConfig())
    source.open()
    assert _read_all(source) == 10


def test_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(SourceOpenError):
        FileEventSource(FileInputConfig(path=tmp_path / "missing.npz"), SensorConfig()).open()


def test_unsupported_extension_raises(tmp_path: Path) -> None:
    path = tmp_path / "events.txt"
    path.write_text("", encoding="utf-8")
    with pytest.raises(SourceOpenError):
        FileEventSource(FileInputConfig(path=path), SensorConfig()).open()


def test_bad_npz_schema_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.npz"
    np.savez(path, values=np.arange(3))
    with pytest.raises(SourceOpenError):
        FileEventSource(FileInputConfig(path=path), SensorConfig()).open()


def test_loop_returns_to_start(tmp_path: Path) -> None:
    path = tmp_path / "events.npz"
    np.savez(path, events=_events(2))
    source = FileEventSource(FileInputConfig(path=path, loop=True), SensorConfig())
    source.open()
    first = source.read(0)
    source.read(0)
    looped = source.read(0)
    assert first is not None and looped is not None
    assert looped.x[0] == first.x[0]


def test_nonlooping_source_closes(tmp_path: Path) -> None:
    path = tmp_path / "events.npz"
    np.savez(path, events=_events(1))
    source = FileEventSource(FileInputConfig(path=path, loop=False), SensorConfig())
    source.open()
    source.read(0)
    assert source.read(0) is None and source.status is SourceStatus.CLOSED


def test_speed_two_returns_more_events_per_read(tmp_path: Path) -> None:
    path = tmp_path / "events.npz"
    np.savez(path, events=_events(20))
    slow = FileEventSource(FileInputConfig(path=path, speed=1, loop=False), SensorConfig())
    fast = FileEventSource(FileInputConfig(path=path, speed=2, loop=False), SensorConfig())
    slow.open(); fast.open()
    assert fast.read(0).size > slow.read(0).size  # type: ignore[union-attr]


def test_seek_half_starts_near_middle(tmp_path: Path) -> None:
    path = tmp_path / "events.npz"
    np.savez(path, events=_events(10))
    source = FileEventSource(FileInputConfig(path=path), SensorConfig())
    source.open()
    source.seek(0.5)
    assert source.read(0).x[0] == 5  # type: ignore[union-attr]
