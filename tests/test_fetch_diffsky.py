"""Exercise the Diffsky fetch command using an entirely local shell."""

from pathlib import Path
import subprocess
import sys

import h5py
import hdf5plugin
import numpy as np
import pandas as pd
import pytest

from manifoldcloud.config import load
from manifoldcloud.provenance import atomic_path, load_manifest, verified_entry


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_diffsky.py"


@pytest.fixture
def fetch_fixture(tmp_path):
    config = load()
    source = tmp_path / "source" / config.diffsky.catalogue
    source.mkdir(parents=True)
    path = source / "lc_cores-487.diffsky_gals.hdf5"
    compression = hdf5plugin.Blosc2(cname="lz4", filters=hdf5plugin.Blosc2.BITSHUFFLE)
    with h5py.File(path, "w") as shell:
        shell.create_group("header/lightcone").attrs["z_range"] = [0.0, 0.0245]
        shell["header"].attrs["catalogue"] = config.diffsky.catalogue
        groups = (
            ("cores", [1, 2, 3], [20.0, 26.5, 26.6]),
            ("synth_cores", [4, 5], [26.0, np.nan]),
        )
        for name, ids, magnitudes in groups:
            group = shell.create_group(f"{name}/data")
            values = {
                "gal_id": np.array(ids, dtype=np.int64),
                "lsst_i_unlensed": np.array(magnitudes, dtype=np.float32),
                "p_merge": np.zeros(len(ids), dtype=np.float32),
            }
            for column in config.diffsky.columns:
                data = values.get(column, np.ones(len(ids), dtype=np.float32))
                group.create_dataset(column, data=data, **compression)

    data_root = tmp_path / "data"
    data_root.mkdir()
    output = data_root / "raw" / "diffsky" / config.diffsky.catalogue / "shell_487.parquet"
    command = [sys.executable, "-B", str(SCRIPT), "--data-root", str(data_root),
               "--location", str(source), "--steps", "487"]
    return path, data_root, output, command


def _run(command, *options):
    result = subprocess.run([*command, *options], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout + result.stderr


def test_dry_run_leaves_data_root_empty(fetch_fixture):
    source, data_root, _, command = fetch_fixture
    text = _run(command, "--dry-run")
    assert "487" in text
    assert str(source.stat().st_size) in text.replace(",", "")
    assert not list(data_root.iterdir())


def test_fetch_filters_rows_and_repairs_a_corrupt_resume(fetch_fixture):
    _, _, output, command = fetch_fixture
    manifest = output.with_name("manifest.json")
    _run(command)

    table = pd.read_parquet(output)
    assert table["gal_id"].tolist() == [1, 4]
    assert table["is_synthetic"].tolist() == [False, True]
    assert table["step"].tolist() == [487, 487]
    assert table["lsst_i_unlensed"].tolist() == [20.0, 26.0]

    original = verified_entry(manifest, output)
    assert original is not None
    assert original["row_count"] == 2
    assert original["details"]["rows_before"] == 5
    assert original["details"]["rows_after"] == 2
    assert original["details"]["synthetic_before"] == 2
    assert original["details"]["synthetic_after"] == 1
    assert not output.stat().st_mode & 0o222
    original_stat = output.stat()

    _run(command)
    assert verified_entry(manifest, output) == original
    assert output.stat().st_ino == original_stat.st_ino
    assert output.stat().st_mtime_ns == original_stat.st_mtime_ns

    with atomic_path(output) as part:
        part.write_bytes(b"corrupt output")
    assert verified_entry(manifest, output) is None
    _run(command)
    assert verified_entry(manifest, output)["sha256"] == original["sha256"]
    pd.testing.assert_frame_equal(pd.read_parquet(output), table)
    assert set(load_manifest(manifest)["files"]) == {output.name}
    assert not output.stat().st_mode & 0o222
