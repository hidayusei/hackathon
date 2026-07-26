"""Application logging configuration."""

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

from deskmate.config.schema import LoggingConfig, PrivacyConfig


def setup_logging(config: LoggingConfig, privacy: PrivacyConfig) -> None:
    """Configure console and optional bounded rotating-file logging."""
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, config.level))
    formatter = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)
    if config.file_enabled:
        directory = config.dir or (
            Path(os.environ.get("LOCALAPPDATA", Path.cwd())) / "DeskMate" / "logs"
        )
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            directory / "deskmate.log",
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)
    if not config.log_features:
        logging.getLogger("deskmate.features").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced application logger."""
    return logging.getLogger(f"deskmate.{name}")
