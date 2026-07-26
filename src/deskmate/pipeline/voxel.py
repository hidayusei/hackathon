"""Optional temporal voxel features implemented from the canonical equations."""

import numpy as np

from deskmate.config.schema import SensorConfig, VoxelConfig
from deskmate.core.types import EventWindow, VoxelFeatures


def events_to_voxel_grid(
    x: np.ndarray,
    y: np.ndarray,
    t: np.ndarray,
    p: np.ndarray,
    num_bins: int,
    height: int,
    width: int,
) -> np.ndarray:
    """Build a float32 bilinearly interpolated temporal voxel grid."""
    size = max(0, num_bins) * height * width
    if num_bins <= 0 or t.size == 0 or int(t[0]) == int(t[-1]):
        return np.zeros((max(0, num_bins), height, width), dtype=np.float32)
    normalized = (num_bins - 1) * (
        (t.astype(np.float64) - float(t[0])) / (float(t[-1]) - float(t[0]))
    )
    lower = np.floor(normalized).astype(np.int64)
    upper = np.ceil(normalized).astype(np.int64)
    polarity = p.astype(np.float32) * 2.0 - 1.0
    spatial = y.astype(np.int64) * width + x.astype(np.int64)
    plane = height * width
    lower_flat = lower * plane + spatial
    upper_flat = upper * plane + spatial
    lower_values = polarity * (1.0 - np.abs(lower - normalized))
    upper_values = polarity * (1.0 - np.abs(upper - normalized))
    upper_values = np.where(upper == lower, 0.0, upper_values)
    accumulated = np.bincount(lower_flat, weights=lower_values, minlength=size)
    accumulated += np.bincount(upper_flat, weights=upper_values, minlength=size)
    return accumulated.reshape(num_bins, height, width).astype(np.float32)


def compute_diff_voxels(voxel: np.ndarray) -> np.ndarray:
    """Return differences between consecutive temporal bins."""
    return np.diff(voxel, axis=0).astype(np.float32, copy=False)


def compute_centroid_trajectory(
    diff_voxels: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return normalized (cx, cy) sequences for absolute difference mass."""
    if diff_voxels.shape[0] == 0:
        empty = np.empty(0, dtype=np.float32)
        return empty, empty.copy()
    weights = np.abs(diff_voxels).astype(np.float64)
    mass = weights.sum(axis=(1, 2)) + 1e-9
    height, width = weights.shape[1:]
    x_axis = np.arange(width, dtype=np.float64)
    y_axis = np.arange(height, dtype=np.float64)
    cx = (weights.sum(axis=1) * x_axis).sum(axis=1) / mass / width
    cy = (weights.sum(axis=2) * y_axis).sum(axis=1) / mass / height
    return cx.astype(np.float32), cy.astype(np.float32)


def voxel_features(
    window: EventWindow,
    config: VoxelConfig,
    sensor: SensorConfig,
) -> VoxelFeatures:
    """Compute optional VoxelFeatures for one event window."""
    if config.time_bins < 2 or window.t.size == 0 or int(window.t[0]) == int(window.t[-1]):
        return VoxelFeatures(0.0, 0.0, 0.0, 0.0, 0.0)
    scale = config.spatial_scale
    width = max(1, sensor.width // scale)
    height = max(1, sensor.height // scale)
    voxel = events_to_voxel_grid(
        window.x // scale,
        window.y // scale,
        window.t,
        window.p,
        config.time_bins,
        height,
        width,
    )
    differences = compute_diff_voxels(voxel)
    if differences.shape[0] == 0:
        return VoxelFeatures(0.0, 0.0, 0.0, 0.0, 0.0)
    cx, cy = compute_centroid_trajectory(differences)
    shift = (
        float(np.hypot(np.diff(cx), np.diff(cy)).sum()) if cx.size > 1 else 0.0
    )
    return VoxelFeatures(
        float(np.abs(differences).mean(axis=(1, 2)).mean()),
        float(cx[-1]),
        float(cy[-1]),
        float(np.square(differences).sum()),
        shift,
    )
