"""Check the two-group HDF5 reader with local and optional real shells."""

import os

import h5py
import hdf5plugin
import numpy as np
import pytest

from manifoldcloud.acquisition.diffsky import TransferBudget, open_shell, read_columns, shell_info


CATALOGUE = "c260710_09_02_2026"
BASE_URL = (
    "https://g-45a93.fd635.8443.data.globus.org/"
    f"Diffsky/synthetic_galaxies/{CATALOGUE}/"
)
live = pytest.mark.skipif(
    os.environ.get("MANIFOLDCLOUD_DIFFSKY_NETWORK") != "1",
    reason="Set MANIFOLDCLOUD_DIFFSKY_NETWORK=1 to use the Diffsky endpoint",
)


@pytest.fixture
def local_shell(tmp_path):
    target = tmp_path / "lc_cores-487.diffsky_gals.hdf5"
    compression = hdf5plugin.Blosc2(cname="lz4", filters=hdf5plugin.Blosc2.BITSHUFFLE)
    with h5py.File(target, "w") as shell:
        lightcone = shell.create_group("header/lightcone")
        lightcone.attrs["z_range"] = [0.0, 0.0245]
        shell["header"].attrs["catalogue"] = CATALOGUE
        for group_name, start, count in (("cores", 0, 64), ("synth_cores", 64, 16)):
            group = shell.create_group(f"{group_name}/data")
            ids = np.arange(start, start + count, dtype=np.int64)
            group.create_dataset("gal_id", data=ids, chunks=(8,), **compression)
            group.create_dataset("kappa", data=np.zeros(count, dtype=np.float32), chunks=(8,), **compression)
            group.create_dataset("ra", data=226.7 + ids / 100, chunks=(8,), **compression)
    return tmp_path


def test_local_groups_and_header(local_shell):
    with open_shell(local_shell, 487) as shell:
        assert shell["cores/data/ra"].id.get_create_plist().get_filter(0)[0] == 32026
        catalogue = read_columns(shell, ["ra", "gal_id", "kappa"])
        info = shell_info(shell)

    assert list(catalogue.columns) == ["ra", "gal_id", "kappa", "is_synthetic"]
    np.testing.assert_array_equal(catalogue["gal_id"], np.arange(80))
    np.testing.assert_allclose(catalogue["ra"], 226.7 + np.arange(80) / 100)
    np.testing.assert_array_equal(catalogue["kappa"], np.zeros(80))
    np.testing.assert_array_equal(catalogue["is_synthetic"], np.arange(80) >= 64)
    assert info["catalogue"] == CATALOGUE
    assert tuple(info["z_range"]) == (0.0, 0.0245)
    assert info["rows"] == {"cores": 64, "synth_cores": 16}


def test_missing_column_names_the_column(local_shell):
    with open_shell(local_shell, 487) as shell:
        with pytest.raises(KeyError, match="missing_column"):
            read_columns(shell, ["gal_id", "missing_column"])


@pytest.mark.network
@live
def test_real_shell_487():
    budget = TransferBudget(limit=10_000_000)
    with open_shell(BASE_URL, 487, budget=budget) as shell:
        info = shell_info(shell)
        assert len(shell["cores/data"]) == len(shell["synth_cores/data"]) == 327
        catalogue = read_columns(shell, ["lc_patch", "ra", "kappa"])

    assert info["catalogue"] == CATALOGUE
    assert info["rows"] == {"cores": 697, "synth_cores": 183}
    assert catalogue["lc_patch"].eq(843).all()
    assert catalogue["ra"].between(226.6, 233.4).all()
    assert catalogue["kappa"].eq(0).all()
    print(f"Step 487: {info['catalogue']}, rows {info['rows']}, 327 columns per group")


@pytest.mark.network
@live
def test_real_shell_300_transfers_only_requested_ranges():
    budget = TransferBudget(limit=30_000_000)
    with open_shell(BASE_URL, 300, budget=budget) as shell:
        catalogue = read_columns(shell, ["lsst_i_unlensed", "redshift_true"])

    assert len(catalogue) == 339_890
    assert 0 < budget.bytes_received < 30_000_000
    print(f"Step 300: {len(catalogue):,} rows, {budget.bytes_received:,} payload bytes")
