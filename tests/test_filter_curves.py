"""Exercise comparison against installed Rubin curves with local HDF5 fixtures."""

import h5py
import numpy as np
import pytest
from speclite.filters import load_filters

from manifoldcloud.catalogue.validate import compare_filter_curves


@pytest.fixture
def transmission_file(tmp_path):
    path = tmp_path / "transmission_curves.hdf5"
    with h5py.File(path, "w") as handle:
        for reference in load_filters("lsst2023-*"):
            band = reference.meta["band_name"]
            group = handle.create_group(f"lsst_{band}")
            before = reference.wavelength[0] - np.arange(198, 0, -1)
            after = reference.wavelength[-1] + np.arange(1, 511)
            group["wave"] = np.concatenate([before, reference.wavelength, after])
            group["transmission"] = np.pad(reference.response, (len(before), len(after)))
    return path


def test_filter_curves_match_with_extra_zero_padding(transmission_file):
    result = compare_filter_curves(transmission_file)
    assert set(result) == set("ugrizy")
    for match in result.values():
        assert match["samples"] == 8500
        assert match["match"] is True
        assert match["max_absolute_difference"] <= 1e-12


@pytest.mark.parametrize("alteration", ["transmission", "shifted_grid", "truncated", "duplicate_wave"])
def test_filter_curve_changes_are_rejected(transmission_file, alteration):
    with h5py.File(transmission_file, "r+") as handle:
        group = handle["lsst_g"]
        if alteration == "transmission":
            values = group["transmission"]
            index = np.argmax(values[:])
            values[index] = values[index] - 0.001
        elif alteration == "shifted_grid":
            group["wave"][:] += 0.25
        elif alteration == "truncated":
            for name in ("wave", "transmission"):
                short = group[name][3500:]
                del group[name]
                group[name] = short
        else:
            group["wave"][100] = group["wave"][99]
    with pytest.raises(ValueError, match=r"\bg\b|lsst_g"):
        compare_filter_curves(transmission_file)
