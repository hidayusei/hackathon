"""Step 14 canonical voxel equation tests."""

from time import perf_counter
from dataclasses import fields

import numpy as np
import pytest

from conftest import make_smoothed, make_window
from deskmate.config.loader import load_config
from deskmate.config.schema import VoxelConfig
from deskmate.pipeline.features import FeatureExtractor
from deskmate.pipeline.ml_estimator import FEATURE_NAMES, MlStatusEstimator
from deskmate.pipeline.regions import RegionMap, RegionRect
from deskmate.pipeline.voxel import (
    compute_centroid_trajectory,
    compute_diff_voxels,
    events_to_voxel_grid,
    voxel_features,
)


def test_empty_events_return_zero_grid_and_features() -> None:
    grid = events_to_voxel_grid(*(np.empty(0, dtype=int) for _ in range(4)), 4, 10, 10)
    features = voxel_features(make_window(), VoxelConfig(), load_config().sensor)
    assert not grid.any()
    assert all(getattr(features, field.name) == 0.0 for field in fields(features))


def test_equal_timestamps_return_zero_grid() -> None:
    grid = events_to_voxel_grid(
        np.array([1, 2]), np.array([1, 2]), np.array([5, 5]), np.array([1, 0]), 4, 4, 4
    )
    assert not grid.any()


def test_polarity_maps_to_plus_and_minus_one() -> None:
    grid = events_to_voxel_grid(
        np.array([0, 1]), np.array([0, 0]), np.array([0, 10]), np.array([1, 0]), 2, 1, 2
    )
    assert grid[0, 0, 0] == pytest.approx(1)
    assert grid[1, 0, 1] == pytest.approx(-1)


def test_bilinear_temporal_kernel_splits_half() -> None:
    grid = events_to_voxel_grid(
        np.array([0, 0, 0]), np.array([0, 0, 0]), np.array([0, 5, 10]),
        np.array([1, 1, 1]), 4, 1, 1,
    )
    assert grid[1, 0, 0] >= 0.5 and grid[2, 0, 0] >= 0.5


def test_diff_shape() -> None:
    assert compute_diff_voxels(np.zeros((4, 3, 2))).shape == (3, 3, 2)


def test_centroid_at_image_center_is_half() -> None:
    diff = np.zeros((1, 10, 10), dtype=np.float32)
    diff[0, 5, 5] = 1
    cx, cy = compute_centroid_trajectory(diff)
    assert cx[0] == pytest.approx(0.5) and cy[0] == pytest.approx(0.5)


def test_centroid_return_order_is_x_then_y() -> None:
    diff = np.zeros((1, 10, 20), dtype=np.float32)
    diff[0, 2, 10] = 1
    cx, cy = compute_centroid_trajectory(diff)
    assert cx[0] == pytest.approx(0.5)
    assert cy[0] == pytest.approx(0.2)


def test_spatial_scale_preserves_normalized_centroid() -> None:
    config = load_config()
    window = make_window(np.array([160, 161]), np.array([160, 161]), start_us=0)
    # ensure non-equal timestamps from make_window
    full = voxel_features(window, VoxelConfig(time_bins=4, spatial_scale=1), config.sensor)
    down = voxel_features(window, VoxelConfig(time_bins=4, spatial_scale=4), config.sensor)
    assert full.diff_centroid_x == pytest.approx(down.diff_centroid_x, abs=0.05)


def test_one_bin_returns_zero_features() -> None:
    features = voxel_features(
        make_window(np.array([1, 2]), np.array([1, 2])),
        VoxelConfig(time_bins=1),
        load_config().sensor,
    )
    assert features.diff_l1 == features.diff_energy == features.diff_centroid_shift == 0


def test_moving_centroid_has_nonzero_shift() -> None:
    x = np.array([20, 50, 100, 150, 200], dtype=np.uint16)
    window = make_window(x, np.full(x.size, 160))
    features = voxel_features(window, VoxelConfig(time_bins=5, spatial_scale=1), load_config().sensor)
    assert features.diff_centroid_shift > 0


def test_voxel_performance_for_twenty_thousand_events() -> None:
    rng = np.random.default_rng(1)
    count = 20_000
    started = perf_counter()
    events_to_voxel_grid(
        rng.integers(0, 320, count), rng.integers(0, 320, count),
        np.arange(count, dtype=np.int64), rng.integers(0, 2, count), 10, 320, 320,
    )
    assert (perf_counter() - started) * 1000 < 100


def test_ml_vector_matches_feature_names() -> None:
    config = load_config()
    mapping = RegionMap([RegionRect(i.id, *i.rect) for i in config.regions], 320, 320)
    frame = FeatureExtractor(config.features, config.sensor, mapping).extract(
        make_window(np.arange(10), np.arange(10))
    )
    assert MlStatusEstimator.feature_vector(frame, make_smoothed()).size == len(FEATURE_NAMES)
