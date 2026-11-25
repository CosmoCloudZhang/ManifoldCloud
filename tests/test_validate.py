"""Check exact validation statistics, null handling and Diffsky depth gates."""

import numpy as np
import pandas as pd
import pytest

from manifoldcloud.validate import diffsky_depth, summarise_catalogue


@pytest.fixture
def catalogue_paths(tmp_path):
    frame = pd.DataFrame({
        "z_true": [0.09, 0.15, 0.15, 0.25, 0.25, np.nan],
        "mag_u": [28.0, 29.0, 31.0, np.inf, 28.0, 29.0],
        "mag_g": [26.0, 27.0, 28.0, 27.0, np.nan, 27.0],
        "mag_r": [25.0, 26.0, 25.0, 26.0, 26.0, 26.0],
        "mag_i": [23.75, 24.0, 24.1, 25.3, np.nan, -np.inf],
        "mag_z": [23.25, 23.5, 23.6, 24.8, 24.8, 24.8],
        "mag_y": [23.0, 23.0, 23.1, 24.3, 24.5, 24.5],
        "a_hl": [0.2, 0.4, 0.6, np.nan, 0.8, 0.8],
    }, dtype="float32")
    paths = [tmp_path / "first.parquet", tmp_path / "second.parquet"]
    frame.iloc[:3].to_parquet(paths[0], index=False)
    frame.iloc[3:].to_parquet(paths[1], index=False)
    return paths


def test_catalogue_summary_matches_counts_colours_and_sizes(tmp_path, catalogue_paths):
    result = summarise_catalogue(catalogue_paths, area_deg2=2, temp_directory=tmp_path)
    assert result["rows"] == 6
    assert result["totals"] == {"i_lt_24_1": 2, "i_lt_25_3": 3}
    assert result["number_counts"] == [
        {"mag_lo": 23.5, "count": 1, "per_deg2": 0.5},
        {"mag_lo": 24.0, "count": 2, "per_deg2": 1.0},
        {"mag_lo": 25.0, "count": 1, "per_deg2": 0.5},
    ]
    assert result["redshift_distribution"] == [{"z_lo": 0.0, "count": 1}, {"z_lo": 0.1, "count": 1}]
    assert result["colours"][0] == {
        "z_lo": 0.0, "u-g": 2.0, "g-r": 1.0, "r-i": 1.25, "i-z": 0.5, "z-y": 0.25,
    }
    redshift_middle = result["colours"][1]
    assert redshift_middle == pytest.approx({
        "z_lo": 0.1, "u-g": 2.5, "g-r": 2.0, "r-i": 1.45, "i-z": 0.5, "z-y": 0.5,
    })
    assert result["colours"][2]["z_lo"] == 0.2
    assert result["colours"][2]["u-g"] is None
    assert [row["mag_lo"] for row in result["sizes"]] == [23.5, 24.0]
    assert [row["median_a_hl"] for row in result["sizes"]] == pytest.approx([0.2, 0.5])
    assert not list(tmp_path.glob(".validation-*"))


def test_catalogue_summary_allows_empty_shell_but_rejects_invalid_area(tmp_path, catalogue_paths):
    empty = tmp_path / "empty.parquet"
    pd.read_parquet(catalogue_paths[0]).iloc[:0].to_parquet(empty, index=False)
    result = summarise_catalogue([empty], area_deg2=1)
    assert result == {"rows": 0, "totals": {"i_lt_24_1": 0, "i_lt_25_3": 0},
                      "number_counts": [], "redshift_distribution": [], "colours": [], "sizes": []}
    with pytest.raises(ValueError, match="area"):
        summarise_catalogue([empty], area_deg2=0)
    with pytest.raises(ValueError, match="Parquet"):
        summarise_catalogue([], area_deg2=1)


def _depth_entry(mag_lo, floor, bright):
    return {"details": {"depth": {"mag_bin_peak": [mag_lo, mag_lo + 0.5],
                                  "floor_halo_rows": floor, "floor_halo_bright_rows": bright}}}


def test_diffsky_depth_enforces_peak_and_percentage_point_tolerance():
    manifest = {"files": {
        "shell_442.parquet": _depth_entry(22.0, 100, 65),
        "shell_392.parquet": _depth_entry(24.5, 1000, 14),
        "shell_300.parquet": _depth_entry(26.5, 100, 0),
    }}
    matches = diffsky_depth(manifest)
    assert matches["passed"]
    assert [row["floor_halo_bright_percent"] for row in matches["rows"]] == [65.0, 1.4, 0.0]
    assert matches["rows"][0]["difference_percentage_points"] == 2.0

    manifest["files"]["shell_442.parquet"] = _depth_entry(22.0, 100, 66)
    manifest["files"]["shell_392.parquet"] = _depth_entry(24.0, 1000, 14)
    del manifest["files"]["shell_300.parquet"]
    different = diffsky_depth(manifest)
    assert not different["passed"]
    assert [(row["step"], row["status"]) for row in different["rows"]] == [
        (442, "failed"), (392, "failed"), (300, "missing"),
    ]
