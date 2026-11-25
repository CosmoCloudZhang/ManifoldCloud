"""Check the offline acquisition report against small fabricated data roots."""

from types import SimpleNamespace

import pytest

from manifoldcloud.acquisition import status
from manifoldcloud.acquisition.fetch_diffsky import diffsky_folder
from manifoldcloud.acquisition.fetch_flagship import flagship_folder
from manifoldcloud.core.provenance import record_file

CONFIG = SimpleNamespace(diffsky=SimpleNamespace(catalogue="c_test", steps=[300, 487]))


def _store(folder, name, rows):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(name.encode())
    record_file(folder / "manifest.json", path, source="fixture", command="test", row_count=rows)
    return path


def test_empty_root_is_incomplete(tmp_path, capsys):
    assert status.report(tmp_path, CONFIG) is False
    text = capsys.readouterr().out
    assert "0 of 2 shells verified" in text and "missing or changed steps: 300, 487" in text
    assert "Acquisition incomplete." in text


def test_complete_root_and_a_changed_file(tmp_path, capsys):
    diffsky, flagship = diffsky_folder(tmp_path, CONFIG), flagship_folder(tmp_path)
    shell = _store(diffsky, "shell_300.parquet", 7)
    _store(diffsky, "shell_487.parquet", 5)
    _store(diffsky, "diffsky_c_test_transmission_curves.hdf5", None)
    for name in status.FLAGSHIP_FILES.values():
        _store(flagship, name, 11 if name == "flagship.parquet" else None)
    assert status.report(tmp_path, CONFIG) is True
    text = capsys.readouterr().out
    assert "2 of 2 shells verified, 12 rows" in text and "4 of 4 files verified, 11 rows" in text

    shell.write_bytes(b"changed after acquisition")
    assert status.diffsky_status(tmp_path, CONFIG)["missing"] == [300]
    with pytest.raises(SystemExit) as error:
        status.main(["--data-root", str(tmp_path)])
    assert error.value.code == 1
