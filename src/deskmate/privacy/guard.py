"""Central privacy permission checks."""

from deskmate.config.schema import PrivacyConfig
from deskmate.core.errors import PrivacyViolationError


class PrivacyGuard:
    """Authorize local saving and permanently reject external transmission."""

    def __init__(self, config: PrivacyConfig) -> None:
        self._config = config

    def can_save_raw_events(self) -> bool:
        """Return whether explicit raw-event saving is enabled."""
        return self._config.save_raw_events

    def can_save_features(self) -> bool:
        """Return whether explicit aggregate-feature saving is enabled."""
        return self._config.save_features

    def can_send_external(self) -> bool:
        """Return False because MVP has no external-send capability."""
        return False

    def assert_can_save_raw_events(self) -> None:
        """Raise PrivacyViolationError unless raw saving is explicitly enabled."""
        if not self.can_save_raw_events():
            raise PrivacyViolationError("raw event saving is disabled")

    def assert_no_external_send(self, destination: str) -> None:
        """Always reject an external destination."""
        raise PrivacyViolationError(f"external sending is forbidden: {destination}")

    def retention_cutoff(self, now: float) -> float:
        """Return the oldest retained monotonic timestamp."""
        return now - self._config.history_retention_minutes * 60

    @property
    def notice_text(self) -> str:
        """Return the canonical privacy notice."""
        from deskmate.ui.labels import PRIVACY_NOTICE_JA

        return PRIVACY_NOTICE_JA

    @property
    def caveat_text(self) -> str:
        """Return the canonical privacy caveat."""
        from deskmate.ui.labels import PRIVACY_CAVEAT_JA

        return PRIVACY_CAVEAT_JA
