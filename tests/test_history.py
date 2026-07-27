"""Step 4 feature history tests."""

import numpy as np
import pytest

from conftest import make_window
from deskmate.config.loader import load_config
from deskmate.pipeline.features import FeatureExtractor
from deskmate.pipeline.history import FeatureHistory
from deskmate.pipeline.regions import RegionMap, RegionRect


def _parts():
    config = load_config()
    mapping = RegionMap([RegionRect(i.id, *i.rect) for i in config.regions], 320, 320)
    return config, FeatureExtractor(config.features, config.sensor, mapping), FeatureHistory(config.features, config.estimation, config.sensor)


def test_constant_rate_converges() -> None:
    _, extractor, history = _parts()
    smoothed = None
    for index in range(100):
        smoothed = history.update(extractor.extract(make_window(np.arange(200), np.arange(200), index=index)))
    assert smoothed.rate_short == pytest.approx(1000)
    assert smoothed.rate_long == pytest.approx(1000)


def test_short_ema_tracks_step_faster() -> None:
    _, extractor, history = _parts()
    for index in range(20):
        history.update(extractor.extract(make_window(np.arange(20), np.arange(20), index=index)))
    coordinates = np.arange(400) % 320
    result = history.update(
        extractor.extract(make_window(coordinates, coordinates, index=20))
    )
    assert abs(result.rate_short - 2000) < abs(result.rate_long - 2000)


def test_rate_cv_is_zero_for_constant_input() -> None:
    _, extractor, history = _parts()
    for index in range(20):
        result = history.update(extractor.extract(make_window(np.arange(100), np.arange(100), index=index)))
    assert result.rate_cv_10s == pytest.approx(0)


def test_warmup_flag() -> None:
    _, extractor, history = _parts()
    history.update(extractor.extract(make_window(np.arange(10), np.arange(10))))
    assert not history.is_warm


def test_rate_series_is_float32() -> None:
    _, extractor, history = _parts()
    history.update(extractor.extract(make_window(np.arange(10), np.arange(10))))
    assert history.rate_series(60).dtype == np.float32
