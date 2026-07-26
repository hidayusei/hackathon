"""Step 4 vectorized feature tests."""

import numpy as np
import pytest

from conftest import make_window
from deskmate.config.loader import load_config
from deskmate.core.enums import RegionId
from deskmate.core.errors import PipelineError
from deskmate.pipeline.features import FeatureExtractor
from deskmate.pipeline.regions import RegionMap, RegionRect


def _extractor() -> FeatureExtractor:
    config = load_config()
    rects = [RegionRect(item.id, *item.rect) for item in config.regions]
    return FeatureExtractor(config.features, config.sensor, RegionMap(rects, 320, 320))


def test_empty_window_defaults() -> None:
    g = _extractor().extract(make_window()).global_features
    assert g.event_count == 0 and g.positive_ratio == 0.5 and g.bbox_area_ratio == 0


def test_single_point_cluster() -> None:
    frame = _extractor().extract(make_window(np.full(1000, 100), np.full(1000, 120)))
    g = frame.global_features
    assert g.centroid_x == 100 and g.var_x == 0
    assert g.active_cell_ratio == pytest.approx(1 / 256)


def test_uniform_distribution_is_spatially_wide() -> None:
    yy, xx = np.mgrid[0:320:10, 0:320:10]
    g = _extractor().extract(make_window(xx.ravel(), yy.ravel())).global_features
    assert g.active_cell_ratio > 0.9 and g.bbox_area_ratio > 0.8


def test_polarity_counts_are_consistent() -> None:
    g = _extractor().extract(
        make_window(np.arange(4), np.arange(4), np.array([0, 1, 1, 1]))
    ).global_features
    assert g.positive_count + g.negative_count == 4
    assert g.positive_ratio == pytest.approx(0.75)


def test_centroid_shift_and_speed() -> None:
    extractor = _extractor()
    extractor.extract(make_window(np.array([10]), np.array([10])))
    g = extractor.extract(make_window(np.array([13]), np.array([14]), index=1)).global_features
    assert g.centroid_shift == pytest.approx(5)
    assert g.centroid_speed == pytest.approx(25)


def test_event_rate_is_count_over_duration() -> None:
    assert _extractor().extract(make_window(np.arange(20), np.arange(20))).global_features.event_rate_eps == 100


def test_region_shares_sum_to_one() -> None:
    frame = _extractor().extract(make_window(np.arange(20), np.arange(20)))
    assert sum(region.share for region in frame.regions.values()) == pytest.approx(1)


def test_all_six_regions_are_returned() -> None:
    assert set(_extractor().extract(make_window()).regions) == set(RegionId)


def test_idle_and_active_counters_reset() -> None:
    extractor = _extractor()
    assert extractor.extract(make_window()).global_features.idle_seconds == pytest.approx(0.2)
    active = make_window(np.arange(100), np.arange(100), index=1)
    assert extractor.extract(active).global_features.idle_seconds == 0


def test_large_window_completes(default_config) -> None:
    rng = np.random.default_rng(1)
    frame = _extractor().extract(
        make_window(rng.integers(0, 320, 100_000), rng.integers(0, 320, 100_000))
    )
    assert frame.compute_ms < 100


def test_out_of_sensor_coordinate_raises() -> None:
    window = make_window(np.array([400], dtype=np.uint16), np.array([1]))
    with pytest.raises(PipelineError):
        _extractor().extract(window)
