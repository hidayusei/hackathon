"""Dependency-free DeskMate enumerations."""

from enum import Enum


class DeskStatus(str, Enum):
    """Desk activity inferred from event-camera motion."""

    AWAY = "away"
    FOCUSED = "focused"
    IDLE = "idle"


class SystemStatus(str, Enum):
    """Application operating state, independent of activity."""

    STARTING = "starting"
    RUNNING = "running"
    NO_SIGNAL = "no_signal"
    PAUSED = "paused"
    ERROR = "error"


class RegionId(str, Enum):
    """Configured desk region."""

    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"
    OTHER = "other"


class AnimationId(str, Enum):
    """Character GIF identifier."""

    RUNNING = "running"
    SITTING = "sitting"
    SLEEPING = "sleeping"
    BREAK = "break"


class SourceStatus(str, Enum):
    """Input source lifecycle state."""

    IDLE = "idle"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    STALLED = "stalled"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    CLOSED = "closed"


class SourceKind(str, Enum):
    """Configured input source implementation."""

    AUTO = "auto"
    METAVISION = "metavision"
    REPLAY = "replay"
    DUMMY = "dummy"
    FILE = "file"
    HDF5 = "hdf5"
