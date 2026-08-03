"""Privacy-gated UDP event sender."""

import socket

from deskmate.config.schema import UdpOutputConfig
from deskmate.core.types import EventBatch
from deskmate.privacy.guard import PrivacyGuard

from .udp_protocol import encode_batch


class UdpEventSender:
    """Send raw event batches to one validated LAN destination."""

    def __init__(self, config: UdpOutputConfig, guard: PrivacyGuard) -> None:
        self._config = config
        self._guard = guard
        self._socket: socket.socket | None = None

    @property
    def enabled(self) -> bool:
        """Return whether transport output is configured on."""
        return self._config.enabled

    def open(self) -> None:
        """Validate privacy permission and create the socket when enabled."""
        if not self.enabled or self._socket is not None:
            return
        self._guard.assert_can_send_external(self._config.destination_host)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, batch: EventBatch) -> None:
        """Send one batch; raise OSError for transport failure."""
        if not self.enabled:
            return
        if self._socket is None:
            self.open()
        assert self._socket is not None
        destination = (self._config.destination_host, self._config.destination_port)
        for packet in encode_batch(batch, self._config.stream_id, self._config.max_datagram_bytes):
            self._socket.sendto(packet, destination)

    def close(self) -> None:
        """Close the socket idempotently."""
        if self._socket is not None:
            self._socket.close()
            self._socket = None
