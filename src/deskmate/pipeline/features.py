"""Vectorized per-window feature extraction."""

from collections import deque
from time import perf_counter

import numpy as np

from deskmate.config.schema import FeatureConfig, SensorConfig
from deskmate.core.enums import RegionId
from deskmate.core.errors import PipelineError
from deskmate.core.types import EventWindow, FeatureFrame, GlobalFeatures, RegionFeatures

from .regions import REGION_ORDER, RegionMap
from .voxel import voxel_features


class BackgroundEventFilter:
    """Learn a stationary event baseline and retain dense excess activity."""

    def __init__(
        self,
        sensor: SensorConfig,
        calibration_seconds: float,
        residual_eps: float,
    ) -> None:
        self._sensor = sensor
        self._calibration_seconds = calibration_seconds
        self._residual_eps = residual_eps
        self._pixels = sensor.width * sensor.height
        self.reset()

    def reset(self) -> None:
        """Clear the learned background and restart calibration."""
        self._elapsed = 0.0
        self._samples = 0
        self._total = np.zeros(self._pixels * 2, dtype=np.float64)
        self._baseline = np.zeros(self._pixels * 2, dtype=np.float64)
        self._credit = np.zeros(self._pixels * 2, dtype=np.float64)
        self._preview_window: EventWindow | None = None

    @property
    def remaining_seconds(self) -> float:
        """Return stationary calibration time still required."""
        return max(0.0, self._calibration_seconds - self._elapsed)

    @property
    def ready(self) -> bool:
        """Return whether the stationary background has been learned."""
        return self.remaining_seconds <= 0.0

    @property
    def preview_window(self) -> EventWindow | None:
        """Return the latest per-pixel-subtracted window before rate gating."""
        return self._preview_window

    @staticmethod
    def _empty_like(window: EventWindow) -> EventWindow:
        return EventWindow(
            np.empty(0, dtype=np.uint16),
            np.empty(0, dtype=np.uint16),
            np.empty(0, dtype=np.int64),
            np.empty(0, dtype=np.int8),
            window.window_index,
            window.t_start_us,
            window.t_end_us,
            window.duration_s,
            window.truncated,
        )

    @staticmethod
    def _select_counts(
        window: EventWindow,
        bins: np.ndarray,
        keep_counts: np.ndarray,
    ) -> EventWindow:
        """Select up to the requested count from every coordinate/polarity bin."""
        if bins.size == 0 or not np.any(keep_counts):
            return BackgroundEventFilter._empty_like(window)
        order = np.argsort(bins, kind="stable")
        sorted_bins = bins[order]
        new_group = np.r_[True, sorted_bins[1:] != sorted_bins[:-1]]
        group_starts = np.maximum.accumulate(
            np.where(new_group, np.arange(sorted_bins.size), 0)
        )
        ranks = np.arange(sorted_bins.size) - group_starts
        selected = np.sort(order[ranks < keep_counts[sorted_bins]])
        return EventWindow(
            window.x[selected].copy(),
            window.y[selected].copy(),
            window.t[selected].copy(),
            window.p[selected].copy(),
            window.window_index,
            window.t_start_us,
            window.t_end_us,
            window.duration_s,
            window.truncated,
        )

    def apply(self, window: EventWindow) -> EventWindow:
        """Return a background-subtracted window; calibration windows are empty."""
        spatial = (
            window.y.astype(np.int64) * self._sensor.width
            + window.x.astype(np.int64)
        )
        bins = window.p.astype(np.int64) * self._pixels + spatial
        counts = np.bincount(bins, minlength=self._pixels * 2).astype(np.float64)
        if not self.ready:
            self._total += counts
            self._samples += 1
            self._elapsed += window.duration_s
            if self.ready and self._samples:
                self._baseline = self._total / self._samples
            self._preview_window = self._empty_like(window)
            return self._preview_window

        available = counts - self._baseline + self._credit
        residual_counts = np.floor(np.maximum(available, 0.0)).astype(np.int64)
        self._credit = np.clip(available - residual_counts, 0.0, 1.0)
        self._preview_window = self._select_counts(window, bins, residual_counts)
        keep_total = max(
            0,
            int(residual_counts.sum() - self._residual_eps * window.duration_s),
        )
        if keep_total == 0 or bins.size == 0:
            return self._empty_like(window)

        active_bins = np.flatnonzero(residual_counts)
        density_order = active_bins[
            np.argsort(residual_counts[active_bins], kind="stable")[::-1]
        ]
        ordered_counts = residual_counts[density_order]
        before = np.cumsum(ordered_counts) - ordered_counts
        keep_by_density = np.minimum(
            ordered_counts,
            np.maximum(0, keep_total - before),
        )
        keep_counts = np.zeros_like(residual_counts)
        keep_counts[density_order] = keep_by_density

        return self._select_counts(window, bins, keep_counts)


class FeatureExtractor:
    """Convert EventWindow to global and region feature aggregates."""

    def __init__(
        self,
        config: FeatureConfig,
        sensor: SensorConfig,
        region_map: RegionMap,
        grid_cols: int = 16,
        grid_rows: int = 16,
        idle_eps: float = 100.0,
    ) -> None:
        self._config = config
        self._sensor = sensor
        self._regions = region_map
        self._grid_cols = grid_cols
        self._grid_rows = grid_rows
        self._idle_eps = idle_eps
        self._cell_count = grid_rows * grid_cols
        self._cells_per_region = self._count_cells_per_region()
        self.reset()

    def _count_cells_per_region(self) -> np.ndarray:
        """Return how many grid cells belong to each region, keyed by cell center.

        Used as the denominator of the per-region active-cell ratio so that a region
        covering a small part of the sensor is not penalised for its size.
        """
        col_centers = (np.arange(self._grid_cols) + 0.5) * self._sensor.width / self._grid_cols
        row_centers = (np.arange(self._grid_rows) + 0.5) * self._sensor.height / self._grid_rows
        xs = np.clip(col_centers.astype(np.int64), 0, self._sensor.width - 1)
        ys = np.clip(row_centers.astype(np.int64), 0, self._sensor.height - 1)
        grid_x, grid_y = np.meshgrid(xs, ys)
        cell_regions = self._regions.assign(grid_x.ravel(), grid_y.ravel())
        return np.bincount(cell_regions, minlength=len(REGION_ORDER))

    def reset(self) -> None:
        """Reset difference and activity state."""
        self._last_frame: FeatureFrame | None = None
        self._last_centroid = (self._sensor.width / 2, self._sensor.height / 2)
        self._last_count = 0
        self._last_rate = 0.0
        self._idle_seconds = 0.0
        self._active_seconds = 0.0
        self._activity: deque[tuple[float, bool]] = deque()
        self._activity_elapsed = 0.0

    @property
    def last_frame(self) -> FeatureFrame | None:
        """Return the most recently extracted frame."""
        return self._last_frame

    def set_idle_eps(self, idle_eps: float) -> None:
        """Set the source-profile activity boundary."""
        self._idle_eps = idle_eps

    def extract(self, window: EventWindow) -> FeatureFrame:
        """Extract all status-definition features; raise PipelineError on bad coordinates."""
        started = perf_counter()
        x, y, p = window.x, window.y, window.p
        if np.any(x >= self._sensor.width) or np.any(y >= self._sensor.height):
            raise PipelineError("window contains a coordinate outside the sensor")
        count = int(x.size)
        duration = window.duration_s
        rate = count / duration if duration > 0 else 0.0
        positive = int(np.count_nonzero(p == 1))
        if count:
            centroid_x, centroid_y = float(x.mean()), float(y.mean())
        else:
            centroid_x, centroid_y = self._last_centroid
        shift = float(np.hypot(centroid_x - self._last_centroid[0], centroid_y - self._last_centroid[1]))
        speed = shift / duration if duration > 0 else 0.0
        var_x = float(x.var()) if count >= 2 else 0.0
        var_y = float(y.var()) if count >= 2 else 0.0
        if count >= 10:
            q = self._config.bbox_percentile * 100
            low_x, high_x = np.percentile(x, [q, 100 - q])
            low_y, high_y = np.percentile(y, [q, 100 - q])
            bbox_width, bbox_height = float(high_x - low_x), float(high_y - low_y)
        else:
            bbox_width = bbox_height = 0.0
        cols = np.minimum(x.astype(np.int64) * self._grid_cols // self._sensor.width, self._grid_cols - 1)
        rows = np.minimum(y.astype(np.int64) * self._grid_rows // self._sensor.height, self._grid_rows - 1)
        flat_cells = rows * self._grid_cols + cols
        grid_counts = np.bincount(
            flat_cells, minlength=self._grid_rows * self._grid_cols
        ).reshape(self._grid_rows, self._grid_cols).astype(np.int32)
        active_cell_ratio = float(np.count_nonzero(grid_counts) / grid_counts.size)
        sorted_cells = np.sort(grid_counts.ravel())[::-1]
        top_count = max(1, int(np.ceil(np.count_nonzero(sorted_cells) * 0.1)))
        noise_ratio = (
            1.0 - float(sorted_cells[:top_count].sum() / count) if count else 0.0
        )
        active = rate >= self._idle_eps
        self._idle_seconds = 0.0 if active else self._idle_seconds + duration
        self._active_seconds = self._active_seconds + duration if active else 0.0
        self._activity_elapsed += duration
        self._activity.append((self._activity_elapsed, active))
        while self._activity and self._activity[0][0] < self._activity_elapsed - 10.0:
            self._activity.popleft()
        activity_ratio = float(np.mean([value for _, value in self._activity]))
        global_features = GlobalFeatures(
            count, positive, count - positive, positive / count if count else 0.5,
            rate, centroid_x, centroid_y, shift, speed, var_x, var_y,
            float(np.sqrt(var_x + var_y)), bbox_width, bbox_height,
            bbox_width * bbox_height / (self._sensor.width * self._sensor.height),
            active_cell_ratio, count - self._last_count, rate - self._last_rate,
            activity_ratio, self._idle_seconds, self._active_seconds, noise_ratio,
        )
        region_indexes = self._regions.assign(x, y) if count else np.empty(0, dtype=np.int8)
        region_counts = np.bincount(region_indexes, minlength=len(REGION_ORDER))
        sum_x = np.bincount(region_indexes, weights=x, minlength=len(REGION_ORDER))
        sum_y = np.bincount(region_indexes, weights=y, minlength=len(REGION_ORDER))
        # Active cells per region: cells holding at least one event from that region,
        # over the cells the region owns. Computed with one bincount over a combined index.
        combined = region_indexes.astype(np.int64) * self._cell_count + flat_cells
        per_region_cells = np.bincount(
            combined, minlength=len(REGION_ORDER) * self._cell_count
        ).reshape(len(REGION_ORDER), self._cell_count)
        region_active_cells = np.count_nonzero(per_region_cells, axis=1)
        region_features: dict[RegionId, RegionFeatures] = {}
        for index, region_id in enumerate(REGION_ORDER):
            region_count = int(region_counts[index])
            fallback_x, fallback_y = self._regions.center_px(region_id)
            owned_cells = int(self._cells_per_region[index])
            region_features[region_id] = RegionFeatures(
                region_id,
                region_count,
                region_count / duration if duration > 0 else 0.0,
                region_count / count if count else 0.0,
                float(sum_x[index] / region_count) if region_count else fallback_x,
                float(sum_y[index] / region_count) if region_count else fallback_y,
                float(region_active_cells[index] / owned_cells) if owned_cells else 0.0,
            )
        voxel = (
            voxel_features(window, self._config.voxel, self._sensor)
            if self._config.voxel.enabled
            else None
        )
        frame = FeatureFrame(
            window.window_index, window.t_start_us, window.t_end_us, duration,
            global_features, region_features, voxel, grid_counts,
            (perf_counter() - started) * 1000,
        )
        self._last_frame = frame
        self._last_centroid = (centroid_x, centroid_y)
        self._last_count, self._last_rate = count, rate
        return frame
