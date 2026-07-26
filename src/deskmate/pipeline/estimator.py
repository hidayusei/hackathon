"""State estimator abstraction and factory."""

import abc

from deskmate.config.schema import EstimationConfig
from deskmate.core.errors import ConfigError
from deskmate.core.types import FeatureFrame, SmoothedFeatures, StatusEstimate


class StatusEstimator(abc.ABC):
    """Convert feature aggregates into an unsmoothed state estimate."""

    @abc.abstractmethod
    def estimate(self, frame: FeatureFrame, smoothed: SmoothedFeatures) -> StatusEstimate:
        """Estimate one window."""

    @abc.abstractmethod
    def reset(self) -> None:
        """Reset estimator state."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Return the implementation name."""


def create_estimator(config: EstimationConfig) -> StatusEstimator:
    """Create the configured estimator."""
    if config.estimator == "rule":
        from .rule_estimator import RuleStatusEstimator

        return RuleStatusEstimator(config)
    if config.estimator == "ml":
        if config.model_path is None:
            raise ConfigError("estimation.model_path is required for ml")
        try:
            from .ml_estimator import MlStatusEstimator
        except ImportError as exc:
            raise ConfigError("ml estimator is unavailable") from exc
        estimator = MlStatusEstimator(config.model_path, config)
        estimator.load()
        return estimator
    raise ConfigError(f"unsupported estimator: {config.estimator}")
