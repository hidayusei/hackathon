"""Replaceable event input sources."""

from .base import EventSource
from .factory import create_event_source

__all__ = ["EventSource", "create_event_source"]
