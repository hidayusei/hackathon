"""Versioned binary UDP event protocol and bounded reassembly."""

from dataclasses import dataclass, field
import struct
import time

import numpy as np

from deskmate.core.errors import DecodeError
from deskmate.core.types import EventBatch

MAGIC = b"DMEV"
VERSION = 1
HEADER = struct.Struct("!4sBBHIIHHqq")
WIRE_EVENT_DTYPE = np.dtype([("x", ">u2"), ("y", ">u2"), ("t", ">i8"), ("p", "i1")])


def encode_batch(batch: EventBatch, stream_id: int, max_datagram_bytes: int) -> list[bytes]:
    """Encode a batch into event-aligned datagrams."""
    capacity = (max_datagram_bytes - HEADER.size) // WIRE_EVENT_DTYPE.itemsize
    if capacity < 1:
        raise ValueError("max_datagram_bytes cannot hold one event")
    wire = np.empty(batch.size, dtype=WIRE_EVENT_DTYPE)
    wire["x"] = batch.x
    wire["y"] = batch.y
    wire["t"] = batch.t
    wire["p"] = batch.p
    fragment_count = max(1, (batch.size + capacity - 1) // capacity)
    if fragment_count > 65_535:
        raise ValueError("batch requires too many UDP fragments")
    packets: list[bytes] = []
    for index in range(fragment_count):
        payload = wire[index * capacity : (index + 1) * capacity].tobytes()
        header = HEADER.pack(
            MAGIC, VERSION, 0, HEADER.size, stream_id, batch.seq & 0xFFFFFFFF,
            index, fragment_count, batch.t_start_us, batch.t_end_us,
        )
        packets.append(header + payload)
    return packets


@dataclass(slots=True)
class _PendingBatch:
    """Fragments retained for one bounded reassembly interval."""

    created_at: float
    fragment_count: int
    t_start_us: int
    t_end_us: int
    fragments: dict[int, bytes] = field(default_factory=dict)


class UdpReassembler:
    """Reassemble complete batches and discard incomplete or inconsistent input."""

    def __init__(
        self,
        timeout_s: float,
        max_batch_events: int,
        max_pending_batches: int = 64,
    ) -> None:
        self._timeout_s = timeout_s
        self._max_batch_events = max_batch_events
        self._max_pending_batches = max_pending_batches
        self._pending: dict[tuple[str, int, int], _PendingBatch] = {}

    def expire(self, now: float | None = None) -> None:
        """Discard incomplete batches older than the configured timeout."""
        current = time.monotonic() if now is None else now
        self._pending = {
            key: value
            for key, value in self._pending.items()
            if current - value.created_at < self._timeout_s
        }

    def push(self, packet: bytes, sender_host: str, now: float | None = None) -> EventBatch | None:
        """Consume one datagram and return a batch only when it is complete."""
        current = time.monotonic() if now is None else now
        self.expire(current)
        if len(packet) < HEADER.size:
            raise DecodeError("UDP datagram is shorter than its header")
        magic, version, flags, header_size, stream_id, batch_seq, index, count, start, end = HEADER.unpack_from(packet)
        if magic != MAGIC or version != VERSION or flags != 0 or header_size != HEADER.size:
            raise DecodeError("UDP header is invalid or unsupported")
        payload = packet[HEADER.size:]
        if count < 1 or index >= count or len(payload) % WIRE_EVENT_DTYPE.itemsize:
            raise DecodeError("UDP fragment metadata or payload size is invalid")
        key = (sender_host, stream_id, batch_seq)
        pending = self._pending.get(key)
        if pending is None:
            if len(self._pending) >= self._max_pending_batches:
                oldest = min(self._pending, key=lambda item: self._pending[item].created_at)
                self._pending.pop(oldest)
            pending = _PendingBatch(current, count, start, end)
            self._pending[key] = pending
        if (pending.fragment_count, pending.t_start_us, pending.t_end_us) != (count, start, end):
            self._pending.pop(key, None)
            raise DecodeError("UDP fragments disagree on batch metadata")
        pending.fragments.setdefault(index, payload)
        event_count = sum(len(value) for value in pending.fragments.values()) // WIRE_EVENT_DTYPE.itemsize
        if event_count > self._max_batch_events:
            self._pending.pop(key, None)
            raise DecodeError("UDP batch exceeds configured event limit")
        if len(pending.fragments) != count:
            return None
        joined = b"".join(pending.fragments[item] for item in range(count))
        self._pending.pop(key, None)
        if not joined:
            return EventBatch.empty(start, end, batch_seq)
        wire = np.frombuffer(joined, dtype=WIRE_EVENT_DTYPE)
        return EventBatch.from_structured(wire, batch_seq)
