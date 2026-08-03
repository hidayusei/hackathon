"""UDP EventSource for a single explicitly allowed LAN sender."""

import ipaddress
import socket
import time

from deskmate.config.schema import UdpInputConfig
from deskmate.core.enums import SourceStatus
from deskmate.core.errors import ConfigError, DecodeError, SourceOpenError
from deskmate.core.types import EventBatch
from deskmate.network.udp_protocol import UdpReassembler

from .base import EventSource


class UdpEventSource(EventSource):
    """Receive and reassemble raw event batches from one IPv4 host."""

    def __init__(self, config: UdpInputConfig) -> None:
        self._config = config
        self._status = SourceStatus.IDLE
        self._socket: socket.socket | None = None
        self._reassembler = UdpReassembler(
            config.reassembly_timeout_ms / 1000,
            config.max_batch_events,
            config.max_pending_batches,
        )
        try:
            allowed = ipaddress.IPv4Address(config.allowed_host)
        except ipaddress.AddressValueError as exc:
            raise ConfigError("input.udp.allowed_host must be a numeric IPv4 address") from exc
        if not (allowed.is_private or allowed.is_loopback) or allowed.is_multicast or allowed.is_unspecified:
            raise ConfigError("input.udp.allowed_host must be private or loopback unicast")
        self._allowed_host = str(allowed)

    @property
    def name(self) -> str:
        """Return the network source name without exposing event data."""
        return "udp(lan)"

    @property
    def status(self) -> SourceStatus:
        """Return the receiver lifecycle state."""
        return self._status

    def open(self) -> None:
        """Bind the UDP socket idempotently."""
        if self._socket is not None:
            return
        self._status = SourceStatus.CONNECTING
        try:
            receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            receiver.bind((self._config.bind_host, self._config.port))
        except OSError as exc:
            self._status = SourceStatus.ERROR
            raise SourceOpenError("UDP receiver could not bind") from exc
        self._socket = receiver
        self._status = SourceStatus.STREAMING

    def read(self, timeout_s: float) -> EventBatch | None:
        """Return the next complete batch, ignoring non-allowed senders."""
        if self._socket is None:
            raise SourceOpenError("UDP receiver is not open")
        deadline = time.monotonic() + max(0.0, timeout_s)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            self._socket.settimeout(remaining)
            try:
                packet, sender = self._socket.recvfrom(65_507)
            except TimeoutError:
                return None
            except OSError as exc:
                if self._status is SourceStatus.CLOSED:
                    return None
                raise SourceOpenError("UDP receive failed") from exc
            if sender[0] != self._allowed_host:
                continue
            try:
                batch = self._reassembler.push(packet, sender[0])
            except DecodeError:
                raise
            if batch is not None:
                return batch

    def request_stop(self) -> None:
        """Interrupt a blocking read by closing the socket."""
        self.close()

    def close(self) -> None:
        """Close the receiver idempotently."""
        self._status = SourceStatus.CLOSED
        if self._socket is not None:
            self._socket.close()
            self._socket = None
