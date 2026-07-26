"""DeskMate exception hierarchy."""


class DeskMateError(Exception):
    """Base class for application errors."""


class ConfigError(DeskMateError):
    """Configuration loading or validation failed."""


class SourceError(DeskMateError):
    """An input source failed."""


class SourceOpenError(SourceError):
    """An input source could not be opened."""


class SourceDisconnectedError(SourceError):
    """An input source disconnected."""


class DecodeError(SourceError):
    """Input data did not satisfy the event schema."""


class PipelineError(DeskMateError):
    """Windowing or feature processing failed."""


class PrivacyViolationError(DeskMateError):
    """A forbidden privacy-sensitive operation was requested."""
