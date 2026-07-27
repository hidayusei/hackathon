"""Dummy and replay-independent source tests."""

import numpy as np
import pytest

from deskmate.config.schema import DummyInputConfig, SensorConfig
from deskmate.core.errors import DecodeError
from deskmate.core.types import EventBatch
from deskmate.input.dummy_source import DummyEventSource
from deskmate.input.scenarios import DEMO_SEQUENCE


def _collect(scenario: str, seconds: float, seed: int = 3):
    source = DummyEventSource(
        DummyInputConfig(mode="manual", scenario=scenario, seed=seed),
        SensorConfig(),
    )
    source.open()
    actual = [
        batch
        for batch in (source.read(0) for _ in range(round(seconds / 0.02)))
        if batch is not None
    ]
    if not actual:
        return np.empty(0, dtype=np.uint16), np.empty(0, dtype=np.uint16)
    return (
        np.concatenate([batch.x for batch in actual]),
        np.concatenate([batch.y for batch in actual]),
    )


def test_same_seed_is_reproducible() -> None:
    assert all(
        np.array_equal(a, b)
        for a, b in zip(_collect("keyboard_focus", 1), _collect("keyboard_focus", 1))
    )


def test_keyboard_rate_is_close_to_spec() -> None:
    x, _ = _collect("keyboard_focus", 5)
    assert x.size / 5 == pytest.approx(1400, rel=0.20)


def test_keyboard_events_are_mostly_inside_region() -> None:
    x, y = _collect("keyboard_focus", 5)
    inside = (x >= 80) & (x < 240) & (y >= 198) & (y < 320)
    assert np.mean(inside) >= 0.80


def test_wide_scenario_has_larger_spread() -> None:
    kx, ky = _collect("keyboard_focus", 5)
    wx, wy = _collect("desk_wide", 5)
    assert np.hypot(wx.std(), wy.std()) >= 2 * np.hypot(kx.std(), ky.std())


def test_dropout_always_returns_none() -> None:
    source = DummyEventSource(
        DummyInputConfig(mode="manual", scenario="dropout"), SensorConfig()
    )
    source.open()
    assert all(source.read(0) is None for _ in range(10))


def test_generated_batch_schema_is_valid() -> None:
    source = DummyEventSource(
        DummyInputConfig(mode="manual", scenario="keyboard_focus"), SensorConfig()
    )
    source.open()
    batch = source.read(0)
    assert batch is not None
    assert np.all(np.diff(batch.t) >= 0)
    assert np.all(batch.x < 320) and np.all(batch.y < 320)
    assert set(np.unique(batch.p)) <= {0, 1}


def test_unknown_scenario_is_rejected() -> None:
    source = DummyEventSource(DummyInputConfig(), SensorConfig())
    with pytest.raises(ValueError):
        source.set_scenario("missing")


def test_demo_is_210_seconds() -> None:
    assert len(DEMO_SEQUENCE) == 6
    assert sum(step.duration_s for step in DEMO_SEQUENCE) == pytest.approx(210.0)


def test_invalid_records_raise_decode_error() -> None:
    with pytest.raises(DecodeError):
        EventBatch.from_records(
            [{"x": 1, "y": 1, "t": 2, "p": 1}, {"x": 1, "y": 1, "t": 1, "p": 0}],
            0,
        )
