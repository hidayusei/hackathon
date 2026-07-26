"""Shared test fixtures specified by the implementation plan."""

from datetime import datetime

import numpy as np
import pytest

from deskmate.config.loader import load_config
from deskmate.core.types import EventWindow
from deskmate.core.enums import RegionId
from deskmate.core.types import SmoothedFeatures

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class FakeClock:
    """Manually advanced Clock implementation."""

    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def now(self) -> datetime:
        return datetime.now().astimezone()

    def advance(self, seconds: float) -> None:
        self.value += seconds


@pytest.fixture
def default_config():
    return load_config()


@pytest.fixture(scope="session")
def qt_app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def make_window(
    x: np.ndarray | None = None,
    y: np.ndarray | None = None,
    p: np.ndarray | None = None,
    index: int = 0,
    start_us: int = 0,
    duration_s: float = 0.2,
) -> EventWindow:
    x = np.asarray([] if x is None else x, dtype=np.uint16)
    y = np.asarray([] if y is None else y, dtype=np.uint16)
    p = np.asarray(np.ones(x.size) if p is None else p, dtype=np.int8)
    end_us = start_us + round(duration_s * 1_000_000)
    t = np.linspace(start_us, max(start_us, end_us - 1), x.size, dtype=np.int64)
    return EventWindow(x, y, t, p, index, start_us, end_us, duration_s, False)


def make_smoothed(**overrides: float) -> SmoothedFeatures:
    """Build SmoothedFeatures with neutral defaults."""
    values = {
        "rate_short": 0.0,
        "rate_long": 0.0,
        "centroid_short_x": 160.0,
        "centroid_short_y": 160.0,
        "centroid_long_x": 160.0,
        "centroid_long_y": 160.0,
        "area_short": 0.0,
        "area_long": 0.0,
        "speed_short": 0.0,
        "cell_short": 0.0,
        "rate_cv_10s": 0.0,
        "change_score": 0.0,
        "idle_seconds": 0.0,
        "active_seconds": 0.0,
        "activity_ratio_10s": 0.0,
        "noise_ratio": 0.0,
        "elapsed_seconds": 10.0,
    }
    values.update(overrides)
    shares = {region: 0.0 for region in RegionId}
    return SmoothedFeatures(
        share_short=shares,
        share_long=shares.copy(),
        **values,
    )
