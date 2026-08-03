"""UDP raw-event transport behavior and privacy boundaries."""

import socket

import numpy as np
import pytest

from deskmate.config.loader import load_config
from deskmate.config.schema import PrivacyConfig, UdpInputConfig, UdpOutputConfig
from deskmate.core.errors import DecodeError, PrivacyViolationError
from deskmate.core.types import EventBatch
from deskmate.network.udp_protocol import HEADER, UdpReassembler, encode_batch
from deskmate.network.udp_sender import UdpEventSender
from deskmate.privacy.guard import PrivacyGuard
from deskmate.input.udp_source import UdpEventSource


def _batch(count: int = 250, seq: int = 7) -> EventBatch:
    records = [
        {"x": index % 320, "y": (index * 3) % 320, "t": 1_000_000 + index, "p": index % 2}
        for index in range(count)
    ]
    return EventBatch.from_records(records, seq)


def test_udp_output_is_disabled_by_default() -> None:
    config = load_config()
    assert not config.udp.output.enabled
    assert not config.privacy.allow_external_send


def test_disabled_sender_does_not_create_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_socket(*args: object, **kwargs: object) -> None:
        raise AssertionError("socket must not be created")

    monkeypatch.setattr(socket, "socket", forbidden_socket)
    sender = UdpEventSender(UdpOutputConfig(), PrivacyGuard(PrivacyConfig()))
    sender.open()
    sender.send(_batch(1))


@pytest.mark.parametrize(
    "destination",
    ["example.test", "8.8.8.8", "0.0.0.0", "224.0.0.1", "255.255.255.255", "::1"],
)
def test_privacy_guard_rejects_non_lan_unicast(destination: str) -> None:
    guard = PrivacyGuard(PrivacyConfig(allow_external_send=True))
    with pytest.raises(PrivacyViolationError):
        guard.assert_can_send_external(destination)


@pytest.mark.parametrize("destination", ["127.0.0.1", "10.2.3.4", "172.16.1.2", "192.168.1.10"])
def test_privacy_guard_allows_private_ipv4(destination: str) -> None:
    PrivacyGuard(PrivacyConfig(allow_external_send=True)).assert_can_send_external(destination)


def test_permission_is_required_even_when_udp_is_enabled() -> None:
    sender = UdpEventSender(
        UdpOutputConfig(enabled=True, destination_host="127.0.0.1"),
        PrivacyGuard(PrivacyConfig()),
    )
    with pytest.raises(PrivacyViolationError):
        sender.open()


def test_fragmentation_respects_limit_and_reassembles_out_of_order() -> None:
    original = _batch()
    packets = encode_batch(original, stream_id=12, max_datagram_bytes=1200)
    assert len(packets) > 1
    assert all(len(packet) <= 1200 for packet in packets)
    reassembler = UdpReassembler(timeout_s=1.0, max_batch_events=1000)
    result = None
    for packet in reversed(packets):
        value = reassembler.push(packet, "192.168.1.2", now=1.0)
        result = value if value is not None else result
    assert result is not None
    assert result.seq == original.seq
    np.testing.assert_array_equal(result.x, original.x)
    np.testing.assert_array_equal(result.y, original.y)
    np.testing.assert_array_equal(result.t, original.t)
    np.testing.assert_array_equal(result.p, original.p)
    assert result.x.dtype == np.dtype("uint16")
    assert result.t.dtype == np.dtype("int64")
    assert result.p.dtype == np.dtype("int8")


def test_empty_batch_preserves_represented_interval() -> None:
    original = EventBatch.empty(10, 20, 3)
    packet = encode_batch(original, 1, 1200)[0]
    result = UdpReassembler(1.0, 10).push(packet, "127.0.0.1")
    assert result is not None
    assert (result.size, result.t_start_us, result.t_end_us, result.seq) == (0, 10, 20, 3)


def test_duplicate_fragment_is_ignored() -> None:
    packets = encode_batch(_batch(), stream_id=1, max_datagram_bytes=1200)
    reassembler = UdpReassembler(1.0, 1000)
    assert reassembler.push(packets[0], "127.0.0.1", now=1.0) is None
    assert reassembler.push(packets[0], "127.0.0.1", now=1.1) is None
    result = None
    for packet in packets[1:]:
        result = reassembler.push(packet, "127.0.0.1", now=1.2)
    assert result is not None


def test_missing_fragment_expires_without_output() -> None:
    packets = encode_batch(_batch(), stream_id=1, max_datagram_bytes=1200)
    reassembler = UdpReassembler(0.1, 1000)
    assert reassembler.push(packets[0], "127.0.0.1", now=1.0) is None
    reassembler.expire(now=1.2)
    for packet in packets[1:]:
        assert reassembler.push(packet, "127.0.0.1", now=1.2) is None


def test_invalid_header_is_rejected() -> None:
    packet = bytearray(encode_batch(_batch(1), 1, 1200)[0])
    packet[:4] = b"NOPE"
    with pytest.raises(DecodeError):
        UdpReassembler(1.0, 10).push(bytes(packet), "127.0.0.1")


def test_inconsistent_fragment_metadata_discards_batch() -> None:
    packets = encode_batch(_batch(), 1, 1200)
    fields = list(HEADER.unpack_from(packets[1]))
    fields[8] += 1
    changed = HEADER.pack(*fields) + packets[1][HEADER.size:]
    reassembler = UdpReassembler(1.0, 1000)
    assert reassembler.push(packets[0], "127.0.0.1") is None
    with pytest.raises(DecodeError):
        reassembler.push(changed, "127.0.0.1")


def test_udp_source_receives_allowed_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    packets = encode_batch(_batch(10), 1, 1200)

    class FakeSocket:
        def __init__(self) -> None:
            self.closed = False

        def bind(self, address: tuple[str, int]) -> None:
            assert address == ("127.0.0.1", 5005)

        def settimeout(self, timeout: float) -> None:
            assert 0 < timeout <= 0.5

        def recvfrom(self, size: int) -> tuple[bytes, tuple[str, int]]:
            assert size == 65_507
            return packets.pop(0), ("127.0.0.1", 41000)

        def close(self) -> None:
            self.closed = True

    fake_socket = FakeSocket()
    monkeypatch.setattr(socket, "socket", lambda *args: fake_socket)
    source = UdpEventSource(UdpInputConfig(bind_host="127.0.0.1"))
    source.open()
    result = source.read(0.5)
    assert result is not None
    assert result.size == 10
    source.close()
    assert fake_socket.closed
