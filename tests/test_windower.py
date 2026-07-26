"""Step 4 windowing tests."""

import numpy as np
import pytest

from deskmate.core.errors import ConfigError, PipelineError
from deskmate.core.types import EventBatch
from deskmate.pipeline.windower import EventWindower


def _batch(start: int, end: int, count: int, seq: int = 0) -> EventBatch:
    t = np.linspace(start, end - 1, count, dtype=np.int64)
    return EventBatch(
        np.zeros(count, np.uint16), np.zeros(count, np.uint16), t,
        np.ones(count, np.int8), start, end, seq, 0.0,
    )


def test_one_second_produces_five_windows() -> None:
    assert len(EventWindower(200, 200, 10_000).push(_batch(0, 1_000_000, 100))) == 5


def test_batch_boundary_preserves_all_events() -> None:
    windower = EventWindower(200, 200, 10_000)
    windows = windower.push(_batch(0, 150_000, 15))
    windows += windower.push(_batch(150_000, 400_000, 25, 1))
    assert sum(window.x.size for window in windows) == 40


def test_overlapping_windows_increase_count() -> None:
    assert len(EventWindower(200, 100, 10_000).push(_batch(0, 1_000_000, 100))) == 9


def test_flush_idle_generates_empty_window() -> None:
    windower = EventWindower(200, 200, 10_000)
    windower.push(EventBatch.empty(0, 1, 0))
    assert windower.flush_idle(400_000)[0].x.size == 0


def test_timestamp_reversal_raises() -> None:
    windower = EventWindower(200, 200, 10_000)
    windower.push(_batch(100, 200, 2))
    with pytest.raises(PipelineError):
        windower.push(_batch(50, 300_000, 2, 1))


def test_window_is_truncated_to_limit() -> None:
    window = EventWindower(200, 200, 10).push(_batch(0, 200_000, 100))[0]
    assert window.truncated and window.x.size <= 10


def test_too_short_window_is_rejected() -> None:
    with pytest.raises(ConfigError):
        EventWindower(49, 20, 1000)


def test_reset_resets_window_index() -> None:
    windower = EventWindower(200, 200, 1000)
    windower.push(_batch(0, 200_000, 10))
    windower.reset()
    assert windower.window_index == 0
