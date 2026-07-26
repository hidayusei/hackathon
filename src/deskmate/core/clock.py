"""Replaceable wall and monotonic clocks."""

import time
from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Clock interface used by time-dependent components."""

    def monotonic(self) -> float:
        """Return monotonic seconds."""

    def now(self) -> datetime:
        """Return a timezone-aware local datetime."""


class SystemClock:
    """Clock backed by the operating system."""

    def monotonic(self) -> float:
        """Return monotonic seconds."""
        return time.monotonic()

    def now(self) -> datetime:
        """Return a timezone-aware local datetime."""
        return datetime.now().astimezone()


def us_to_seconds(us: int) -> float:
    """Convert integer microseconds to seconds."""
    return us / 1_000_000.0


def seconds_to_us(s: float) -> int:
    """Convert seconds to rounded integer microseconds."""
    return int(round(s * 1_000_000.0))
