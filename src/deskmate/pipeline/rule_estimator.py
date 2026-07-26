"""Status-definition rule estimator."""

from dataclasses import replace

from deskmate.config.schema import EstimationConfig
from deskmate.core.enums import DeskStatus
from deskmate.core.types import FeatureFrame, SmoothedFeatures, StatusEstimate

from .estimator import StatusEstimator


def margin_confidence(value: float, threshold: float, span: float) -> float:
    """Map threshold margin to the specified 0.30–0.95 confidence interval."""
    margin = (value - threshold) / span if span > 0 else 0.0
    return float(min(0.95, max(0.30, 0.5 + 0.45 * min(1.0, max(0.0, margin)))))


class RuleStatusEstimator(StatusEstimator):
    """Evaluate status rules in their canonical priority order."""

    def __init__(self, config: EstimationConfig) -> None:
        self._config = config
        self._transition_started_at: float | None = None

    @property
    def name(self) -> str:
        """Return the implementation name."""
        return "rule"

    def reset(self) -> None:
        """Clear transition suppression state."""
        self._transition_started_at = None

    def _estimate(
        self, status: DeskStatus, confidence: float, rule_id: str, reason: str
    ) -> StatusEstimate:
        return StatusEstimate(status, min(1.0, max(0.0, confidence)), rule_id, reason)

    def _rule_no_motion(self, s: SmoothedFeatures) -> StatusEstimate | None:
        c = self._config
        if s.idle_seconds >= c.no_motion_seconds:
            return self._estimate(
                DeskStatus.NO_MOTION,
                margin_confidence(s.idle_seconds, c.no_motion_seconds, c.no_motion_seconds),
                "R1_no_motion",
                f"idle_seconds={s.idle_seconds:.3f}",
            )
        return None

    def _rule_transition(self, s: SmoothedFeatures) -> StatusEstimate | None:
        c = self._config
        matches = s.change_score >= c.transition_change_score and s.rate_short >= c.idle_eps
        if not matches:
            self._transition_started_at = None
            return None
        if self._transition_started_at is None:
            self._transition_started_at = s.elapsed_seconds
        if s.elapsed_seconds - self._transition_started_at > c.transition_max_seconds:
            return None
        return self._estimate(
            DeskStatus.TRANSITION,
            margin_confidence(
                s.change_score, c.transition_change_score, 1.0 - c.transition_change_score
            ),
            "R2_transition",
            f"change_score={s.change_score:.3f}",
        )

    def _rule_organizing(self, s: SmoothedFeatures) -> StatusEstimate | None:
        c = self._config
        if not (
            s.rate_short >= c.active_eps
            and s.area_short >= c.organizing_bbox_area_ratio
            and s.cell_short >= c.organizing_active_cell_ratio
            and s.speed_short >= c.organizing_centroid_speed
        ):
            return None
        confidence = min(
            margin_confidence(s.rate_short, c.active_eps, c.high_activity_eps - c.active_eps),
            margin_confidence(s.area_short, c.organizing_bbox_area_ratio, 1 - c.organizing_bbox_area_ratio),
            margin_confidence(s.cell_short, c.organizing_active_cell_ratio, 1 - c.organizing_active_cell_ratio),
            margin_confidence(s.speed_short, c.organizing_centroid_speed, c.organizing_centroid_speed),
        )
        return self._estimate(
            DeskStatus.ORGANIZING, confidence, "R3_organizing",
            f"rate_short={s.rate_short:.3f}, area={s.area_short:.3f}",
        )

    def _focus_share(self, s: SmoothedFeatures) -> float:
        return sum(s.share_short.get(region, 0.0) for region in self._config.focus_regions)

    def _rule_focused(self, s: SmoothedFeatures) -> StatusEstimate | None:
        c = self._config
        share = self._focus_share(s)
        if not (
            s.rate_short >= c.focus_min_eps
            and share >= c.focus_region_share
            and s.area_short <= c.focus_max_bbox_area_ratio
            and s.rate_cv_10s <= c.focus_max_activity_cv
            and s.active_seconds >= c.focus_min_seconds
        ):
            return None
        confidence = min(
            margin_confidence(share, c.focus_region_share, 1 - c.focus_region_share),
            margin_confidence(s.active_seconds, c.focus_min_seconds, c.focus_min_seconds),
        )
        return self._estimate(
            DeskStatus.FOCUSED, confidence, "R4_focused", f"focus_share={share:.3f}"
        )

    def _rule_short_break(self, s: SmoothedFeatures) -> StatusEstimate | None:
        c = self._config
        if not (
            s.rate_short <= c.break_max_eps
            and s.rate_short <= c.break_decay_ratio * s.rate_long
            and s.rate_short > c.idle_eps
        ):
            return None
        margin = c.break_decay_ratio * s.rate_long - s.rate_short
        return self._estimate(
            DeskStatus.SHORT_BREAK,
            margin_confidence(margin, 0.0, max(c.break_max_eps, 1.0)),
            "R5_short_break",
            f"decay_margin={margin:.3f}",
        )

    def _rule_working(self, s: SmoothedFeatures) -> StatusEstimate | None:
        c = self._config
        if s.rate_short < c.low_activity_eps:
            return None
        return self._estimate(
            DeskStatus.WORKING,
            margin_confidence(
                s.rate_short, c.low_activity_eps, c.high_activity_eps - c.low_activity_eps
            ),
            "R6_working",
            f"rate_short={s.rate_short:.3f}",
        )

    def _apply_noise_penalty(
        self, estimate: StatusEstimate, s: SmoothedFeatures
    ) -> StatusEstimate:
        if s.noise_ratio > self._config.noise_ratio_threshold:
            return replace(estimate, confidence=estimate.confidence * 0.6)
        return estimate

    def estimate(self, frame: FeatureFrame, smoothed: SmoothedFeatures) -> StatusEstimate:
        """Return the first matching canonical rule."""
        estimate = self._rule_no_motion(smoothed)
        if estimate is not None:
            # Rule 2 is skipped this window, so clear its suppression state here.
            # Otherwise a stale timer keeps suppressing the first transition that
            # follows a no-motion stretch.
            self._transition_started_at = None
        for rule in (
            self._rule_transition,
            self._rule_organizing,
            self._rule_focused,
            self._rule_short_break,
            self._rule_working,
        ):
            if estimate is None:
                estimate = rule(smoothed)
        if estimate is None:
            estimate = self._estimate(DeskStatus.UNKNOWN, 0.30, "R7_unknown", "no rule matched")
        return self._apply_noise_penalty(estimate, smoothed)
