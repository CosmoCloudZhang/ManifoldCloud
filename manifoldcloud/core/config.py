"""Locate the repository folders, load the catalogue settings and resolve the data root."""

import os
from pathlib import Path
import tomllib
from types import SimpleNamespace

# The package is installed in editable mode, so these folders sit beside it.
REPOSITORY = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPOSITORY / "config"
OUTPUTS = REPOSITORY / "outputs"
DEFAULT_DATA_ROOT = OUTPUTS / "data"
DATA_ROOT_ENV = "MANIFOLDCLOUD_DATA_ROOT"
DATA_ROOT_HELP = "Choose another folder with --data-root, MANIFOLDCLOUD_DATA_ROOT, or data_root in config/local.toml."


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
    """Prefer the CLI, the environment, then TOML; otherwise use outputs/data.

    A folder that was chosen explicitly must already exist, which catches a
    mistyped path or an unmounted disk. The default folder is created on first use.
    """
    config = load() if config is None else config
    value = argument or os.environ.get(DATA_ROOT_ENV) or getattr(config, "data_root", None)
    if not value:
        DEFAULT_DATA_ROOT.mkdir(parents=True, exist_ok=True)
        return DEFAULT_DATA_ROOT
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Data root is not an existing directory: {root}. {DATA_ROOT_HELP}")
    return root
