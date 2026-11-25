"""Check overrides and data-root resolution without touching local configuration."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from manifoldcloud.core.config import DATA_ROOT_ENV, DEFAULT_DATA_ROOT, REPOSITORY, load, resolve_data_root


def test_root_priority(tmp_path):
    cli, environment, local = (tmp_path / name for name in ("cli", "env", "local"))
    for path in (cli, environment, local):
        path.mkdir()
    config = SimpleNamespace(data_root=str(local))
    with patch.dict("os.environ", {DATA_ROOT_ENV: str(environment)}, clear=True):
        assert resolve_data_root(cli, config) == cli
        assert resolve_data_root(config=config) == environment
    with patch.dict("os.environ", {}, clear=True):
        assert resolve_data_root(config=config) == local
        with pytest.raises(ValueError, match="existing directory.*--data-root.*MANIFOLDCLOUD_DATA_ROOT.*config/local.toml"):
            resolve_data_root(tmp_path / "missing", config)


def test_default_root_is_outputs_data_and_is_created(tmp_path, monkeypatch):
    assert (REPOSITORY / "pyproject.toml").is_file()
    assert DEFAULT_DATA_ROOT == REPOSITORY / "outputs" / "data"
    default = tmp_path / "outputs" / "data"
    monkeypatch.setattr("manifoldcloud.core.config.DEFAULT_DATA_ROOT", default)
    with patch.dict("os.environ", {}, clear=True):
        assert resolve_data_root(config=SimpleNamespace()) == default
    assert default.is_dir()


def test_local_toml_merge(tmp_path):
    (tmp_path / "default.toml").write_text("[diffsky]\nlocation='remote'\nsteps=[487]\n")
    (tmp_path / "local.toml").write_text("data_root='/catalogues'\n[diffsky]\nlocation='local'\n")
    config = load(tmp_path)
    assert Path(config.data_root) == Path("/catalogues")
    assert config.diffsky.location == "local"
    assert config.diffsky.steps == [487]
