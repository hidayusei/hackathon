"""Time-constant feature smoothing and short aggregate history."""

from collections import deque
import math

import numpy as np

from deskmate.config.schema import EstimationConfig, FeatureConfig, SensorConfig
from deskmate.core.enums import RegionId
from deskmate.core.types import FeatureFrame, SmoothedFeatures

from .regions import REGION_ORDER


class FeatureHistory:
    """Maintain EMA values and derive the estimator's SmoothedFeatures."""

    def __init__(
        self,
        config: FeatureConfig,
        estimation: EstimationConfig,
        sensor: SensorConfig,
    ) -> None:
        self._config = config
        self._estimation = estimation
        self._sensor = sensor
        self.reset()

    def reset(self) -> None:
        """Clear all aggregate history."""
        self._elapsed = 0.0
        self._initialized = False
        self._rates: deque[tuple[float, float]] = deque()
        self._values: dict[str, float] = {}
        self._share_short = {region: 0.0 for region in REGION_ORDER}
        self._share_long = {region: 0.0 for region in REGION_ORDER}

    def _ema(self, key: str, value: float, duration: float, tau: float) -> float:
        if not self._initialized:
            result = value
        else:
            alpha = 1.0 - math.exp(-duration / tau)
            result = self._values[key] + alpha * (value - self._values[key])
        self._values[key] = result
        return result

    def update(self, frame: FeatureFrame) -> SmoothedFeatures:
        """Update EMA, coefficient of variation, and change score."""
        g = frame.global_features
        d = frame.duration_s
        self._elapsed += d
        short, long = self._config.ema_short_seconds, self._config.ema_long_seconds
        rate_short = self._ema("rate_short", g.event_rate_eps, d, short)
        rate_long = self._ema("rate_long", g.event_rate_eps, d, long)
        csx = self._ema("csx", g.centroid_x, d, short)
        csy = self._ema("csy", g.centroid_y, d, short)
        clx = self._ema("clx", g.centroid_x, d, long)
        cly = self._ema("cly", g.centroid_y, d, long)
        area_short = self._ema("area_short", g.bbox_area_ratio, d, short)
        area_long = self._ema("area_long", g.bbox_area_ratio, d, long)
        speed_short = self._ema("speed_short", g.centroid_speed, d, short)
        cell_short = self._ema("cell_short", g.active_cell_ratio, d, short)
        alpha_s, alpha_l = 1 - math.exp(-d / short), 1 - math.exp(-d / long)
        for region in REGION_ORDER:
            share = frame.regions[region].share
            if not self._initialized:
                self._share_short[region] = self._share_long[region] = share
            else:
                self._share_short[region] += alpha_s * (share - self._share_short[region])
                self._share_long[region] += alpha_l * (share - self._share_long[region])
        self._rates.append((self._elapsed, g.event_rate_eps))
        while self._rates and self._rates[0][0] < self._elapsed - 10.0:
            self._rates.popleft()
        rates = np.asarray([rate for _, rate in self._rates])
        rate_cv = float(rates.std() / rates.mean()) if rates.size and rates.mean() > 0 else 999.0
        c1 = np.clip(
            abs(rate_short - rate_long) / max(rate_long, self._estimation.idle_eps), 0, 1
        )
        diag = math.hypot(self._sensor.width, self._sensor.height)
        c2 = np.clip(math.hypot(csx - clx, csy - cly) / (0.25 * diag), 0, 1)
        c3 = np.clip(abs(area_short - area_long), 0, 1)
        c4 = np.clip(
            0.5 * sum(abs(self._share_short[r] - self._share_long[r]) for r in REGION_ORDER),
            0,
            1,
        )
        change_score = float(0.35 * c1 + 0.25 * c2 + 0.15 * c3 + 0.25 * c4)
        self._initialized = True
        return SmoothedFeatures(
            rate_short, rate_long, csx, csy, clx, cly, area_short, area_long,
            speed_short, cell_short, dict(self._share_short), dict(self._share_long),
            rate_cv, change_score, g.idle_seconds, g.active_seconds,
            g.activity_ratio_10s, g.noise_ratio, self._elapsed,
        )

    def rate_series(self, seconds: float) -> np.ndarray:
        """Return recent event rates as float32."""
        return np.asarray(
            [rate for stamp, rate in self._rates if stamp >= self._elapsed - seconds],
            dtype=np.float32,
        )

    @property
    def is_warm(self) -> bool:
        """Return whether estimator warmup time has elapsed."""
        return self._elapsed >= self._estimation.warmup_seconds
