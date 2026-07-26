"""Load and deeply merge DeskMate YAML configuration."""

import os
from copy import deepcopy
from pathlib import Path

import yaml
from pydantic import ValidationError

from deskmate.core.errors import ConfigError

from .schema import AppConfig


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "default.yaml"


def user_config_path() -> Path:
    """Return the per-user configuration path."""
    root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return root / "DeskMate" / "config.yaml"


def deep_merge(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    """Recursively merge mappings without mutating inputs."""
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)  # type: ignore[arg-type]
        else:
            result[key] = deepcopy(value)
    return result


def _read_yaml(path: Path, required: bool) -> dict[str, object]:
    if not path.exists():
        if required:
            raise ConfigError(f"configuration file does not exist: {path}")
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"failed to read configuration: {path}") from exc
    if not isinstance(data, dict):
        raise ConfigError("configuration root must be a mapping")
    return data


def load_config(
    cli_overrides: dict[str, object] | None = None,
    config_path: Path | None = None,
) -> AppConfig:
    """Load defaults, optional user file, and CLI overrides; raise ConfigError."""
    data = _read_yaml(DEFAULT_CONFIG_PATH, required=True)
    selected = config_path if config_path is not None else user_config_path()
    data = deep_merge(data, _read_yaml(selected, required=config_path is not None))
    if cli_overrides:
        data = deep_merge(data, cli_overrides)
    try:
        return AppConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc


def write_user_config_template(path: Path | None = None) -> Path:
    """Write the default YAML as a user-editable template."""
    destination = path or user_config_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return destination
