"""EXT-6 machine-learning estimator skeleton and stable feature vector."""

from pathlib import Path

import numpy as np

from deskmate.config.schema import EstimationConfig
from deskmate.core.enums import RegionId
from deskmate.core.types import FeatureFrame, SmoothedFeatures, StatusEstimate

from .estimator import StatusEstimator


FEATURE_NAMES: tuple[str, ...] = (
    "event_rate_eps",
    "bbox_area_ratio",
    "active_cell_ratio",
    "centroid_speed",
    "noise_ratio",
    "rate_short",
    "rate_long",
    "area_short",
    "area_long",
    "speed_short",
    "cell_short",
    "rate_cv_10s",
    "idle_seconds",
    "active_seconds",
    "activity_ratio_10s",
    *(f"share_short_{region.value}" for region in RegionId),
    *(f"share_long_{region.value}" for region in RegionId),
)


class MlStatusEstimator(StatusEstimator):
    """Future learned estimator sharing all downstream smoothing and UI logic."""

    def __init__(self, model_path: Path, config: EstimationConfig) -> None:
        self._model_path = model_path
        self._config = config

    @property
    def name(self) -> str:
        """Return the implementation name."""
        return "ml"

    def load(self) -> None:
        """Raise because EXT-6 model loading is intentionally not implemented."""
        raise NotImplementedError("EXT-6")

    def estimate(self, frame: FeatureFrame, smoothed: SmoothedFeatures) -> StatusEstimate:
        """Raise because EXT-6 inference is intentionally not implemented."""
        raise NotImplementedError("EXT-6")

    def reset(self) -> None:
        """Reset no state in the skeleton."""

    @staticmethod
    def feature_vector(frame: FeatureFrame, smoothed: SmoothedFeatures) -> np.ndarray:
        """Return the stable training/inference vector matching FEATURE_NAMES."""
        g = frame.global_features
        values = [
            g.event_rate_eps,
            g.bbox_area_ratio,
            g.active_cell_ratio,
            g.centroid_speed,
            g.noise_ratio,
            smoothed.rate_short,
            smoothed.rate_long,
            smoothed.area_short,
            smoothed.area_long,
            smoothed.speed_short,
            smoothed.cell_short,
            smoothed.rate_cv_10s,
            smoothed.idle_seconds,
            smoothed.active_seconds,
            smoothed.activity_ratio_10s,
            *(smoothed.share_short.get(region, 0.0) for region in RegionId),
            *(smoothed.share_long.get(region, 0.0) for region in RegionId),
        ]
        return np.asarray(values, dtype=np.float32)
