"""Three-state rule estimator."""

from deskmate.config.schema import EstimationConfig
from deskmate.core.enums import DeskStatus
from deskmate.core.types import FeatureFrame, SmoothedFeatures, StatusEstimate

from .estimator import StatusEstimator


def margin_confidence(value: float, threshold: float, span: float) -> float:
    """Map threshold margin to the canonical confidence interval."""

    margin = (value - threshold) / span if span > 0 else 0.0
    return float(min(0.95, max(0.30, 0.5 + 0.45 * min(1.0, max(0.0, margin)))))


class RuleStatusEstimator(StatusEstimator):
    """Evaluate no-motion, focused, then idle fallback rules."""

    def __init__(self, config: EstimationConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        """Return the implementation name."""

        return "rule"

    def reset(self) -> None:
        """Reset stateless rule evaluation."""

    def _focus_share(self, smoothed: SmoothedFeatures) -> float:
        return sum(
            smoothed.share_short.get(region, 0.0)
            for region in self._config.focus_regions
        )

    def estimate(
        self, frame: FeatureFrame, smoothed: SmoothedFeatures
    ) -> StatusEstimate:
        """Return exactly one of the three supported states."""

        del frame
        config = self._config
        if smoothed.idle_seconds >= config.away_seconds:
            return StatusEstimate(
                DeskStatus.AWAY,
                margin_confidence(
                    smoothed.idle_seconds,
                    config.away_seconds,
                    config.away_seconds,
                ),
                "R1_away",
                f"idle_seconds={smoothed.idle_seconds:.3f}",
            )

        focus_share = self._focus_share(smoothed)
        if (
            smoothed.rate_short >= config.focus_min_eps
            and focus_share >= config.focus_region_share
            and smoothed.area_short <= config.focus_max_bbox_area_ratio
            and smoothed.rate_cv_10s <= config.focus_max_activity_cv
            and smoothed.active_seconds >= config.focus_min_seconds
        ):
            confidence = min(
                margin_confidence(
                    focus_share,
                    config.focus_region_share,
                    1.0 - config.focus_region_share,
                ),
                margin_confidence(
                    smoothed.active_seconds,
                    config.focus_min_seconds,
                    config.focus_min_seconds,
                ),
            )
            return StatusEstimate(
                DeskStatus.FOCUSED,
                confidence,
                "R2_focused",
                (
                    f"rate_short={smoothed.rate_short:.3f}, "
                    f"focus_share={focus_share:.3f}, "
                    f"area={smoothed.area_short:.3f}, "
                    f"rate_cv={smoothed.rate_cv_10s:.3f}"
                ),
            )

        return StatusEstimate(
            DeskStatus.IDLE,
            margin_confidence(
                smoothed.rate_short,
                config.idle_eps,
                config.high_activity_eps - config.idle_eps,
            ),
            "R3_idle",
            (
                f"rate_short={smoothed.rate_short:.3f}, "
                f"focus_share={focus_share:.3f}, "
                f"area={smoothed.area_short:.3f}, "
                f"rate_cv={smoothed.rate_cv_10s:.3f}, "
                f"active_seconds={smoothed.active_seconds:.3f}"
            ),
        )
