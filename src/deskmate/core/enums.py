"""Dependency-free DeskMate enumerations."""

from enum import Enum


class DeskStatus(str, Enum):
    """An abstract desk activity state."""

    FOCUSED = "focused"
    WORKING = "working"
    ORGANIZING = "organizing"
    SHORT_BREAK = "short_break"
    TRANSITION = "transition"
    NO_MOTION = "no_motion"
    UNKNOWN = "unknown"


class SystemStatus(str, Enum):
    """Application operating state, independent of activity."""

    STARTING = "starting"
    RUNNING = "running"
    NO_SIGNAL = "no_signal"
    PAUSED = "paused"
    SHARING_OFF = "sharing_off"
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
    """Character animation identifier."""

    WORKING_AT_DESK = "working_at_desk"
    TYPING = "typing"
    ORGANIZING_DESK = "organizing_desk"
    DRINKING_TEA = "drinking_tea"
    RESTING = "resting"
    LOOKING_AROUND = "looking_around"
    SLEEPING = "sleeping"
    TRANSITIONING = "transitioning"
    UNKNOWN = "unknown"


class Approachability(str, Enum):
    """Secondary, deliberately uncertain approachability indicator."""

    LIKELY_OK = "likely_ok"
    PREFER_LATER = "prefer_later"
    UNDETERMINED = "undetermined"


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

    DUMMY = "dummy"
    FILE = "file"
    HDF5 = "hdf5"
    WEBSOCKET = "websocket"
    TCP = "tcp"
    UDP = "udp"
    HTTP = "http"
