"""Central privacy permission checks."""

import ipaddress

from deskmate.config.schema import PrivacyConfig
from deskmate.core.errors import PrivacyViolationError


class PrivacyGuard:
    """Authorize local saving and tightly scoped LAN transmission."""

    def __init__(self, config: PrivacyConfig) -> None:
        self._config = config

    def can_save_raw_events(self) -> bool:
        """Return whether explicit raw-event saving is enabled."""
        return self._config.save_raw_events

    def can_save_features(self) -> bool:
        """Return whether explicit aggregate-feature saving is enabled."""
        return self._config.save_features

    def can_send_external(self) -> bool:
        """Return whether the user explicitly enabled external sending."""
        return self._config.allow_external_send

    def assert_can_save_raw_events(self) -> None:
        """Raise PrivacyViolationError unless raw saving is explicitly enabled."""
        if not self.can_save_raw_events():
            raise PrivacyViolationError("raw event saving is disabled")

    def assert_no_external_send(self, destination: str) -> None:
        """Reject a call site that must never perform external sending."""
        raise PrivacyViolationError(f"external sending is forbidden here: {destination}")

    def assert_can_send_external(self, destination: str) -> None:
        """Authorize one private or loopback unicast IPv4 destination."""
        if not self.can_send_external():
            raise PrivacyViolationError("external sending is disabled")
        try:
            address = ipaddress.ip_address(destination)
        except ValueError as exc:
            raise PrivacyViolationError("UDP destination must be a numeric IPv4 address") from exc
        if address.version != 4:
            raise PrivacyViolationError("UDP destination must use IPv4")
        if not (address.is_private or address.is_loopback):
            raise PrivacyViolationError("UDP destination must be private or loopback")
        if address.is_multicast or address.is_unspecified or destination == "255.255.255.255":
            raise PrivacyViolationError("UDP destination must be unicast")

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
