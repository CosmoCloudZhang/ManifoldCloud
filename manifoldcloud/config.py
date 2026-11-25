"""Load the catalogue settings and resolve an explicitly configured data root."""

import os
from pathlib import Path
import tomllib
from types import SimpleNamespace

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
DATA_ROOT_ENV = "MANIFOLDCLOUD_DATA_ROOT"
DATA_ROOT_HELP = "Set --data-root, MANIFOLDCLOUD_DATA_ROOT, or data_root in config/local.toml."


def _merge(defaults, overrides):
    result = dict(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            value = _merge(result[key], value)
        result[key] = value
    return result


def _namespace(settings):
    return SimpleNamespace(**{
        key: _namespace(value) if isinstance(value, dict) else value
        for key, value in settings.items()
    })


def load(config_dir=None):
    """Return defaults recursively overridden by local settings, if present."""
    directory = Path(config_dir) if config_dir is not None else CONFIG_DIR
    with (directory / "default.toml").open("rb") as stream:
        settings = tomllib.load(stream)
    local = directory / "local.toml"
    if local.is_file():
        with local.open("rb") as stream:
            settings = _merge(settings, tomllib.load(stream))
    return _namespace(settings)


def resolve_data_root(argument=None, config=None):
    """Require an existing directory, preferring CLI, environment, then TOML."""
    config = load() if config is None else config
    value = argument or os.environ.get(DATA_ROOT_ENV) or getattr(config, "data_root", None)
    if not value:
        raise ValueError(f"No data root was configured. {DATA_ROOT_HELP}")
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Data root is not an existing directory: {root}. {DATA_ROOT_HELP}")
    return root
