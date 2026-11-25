"""Check the science-only student projection and its Parquet hand-over."""

from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from manifoldcloud.core.config import load
from manifoldcloud.core.provenance import verified_entry
from scripts.make_year1_sample import STUDENT_COLUMNS, YEAR1_SCHEMA, select_student_sample


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "make_year1_sample.py"
EXPECTED_COLUMNS = [
    "gal_id", "ra", "dec", "z_true", "z_obs", "mag_i",
    *(f"mag_{band}_{suffix}" for band in "ugrizy" for suffix in ("obs", "err")),
    "a_hl", "b_hl", "random_index",
]


def _year1_table(fraction):
    table = pd.DataFrame({
        field.name: np.ones(5, dtype=field.type.to_pandas_dtype()) for field in YEAR1_SCHEMA
    }, index=[3, 4, 7, 9, 12])
    return table.assign(
        gal_id=[900, 901, 902, 903, 904],
        sample=[True, False, True, True, True],
        control_sample=[False, True, True, False, True],
        random_index=np.array([0.5 * fraction, 0.5 * fraction, fraction, 1.0, np.nan], dtype="float32"),
    )


def test_student_samples_keep_only_science_rows_and_the_approved_columns():
    assert list(STUDENT_COLUMNS) == EXPECTED_COLUMNS
    assert len(STUDENT_COLUMNS) == 21
    year1 = _year1_table(0.02)
    selected = select_student_sample(year1, fraction=0.02)
    pd.testing.assert_frame_equal(selected, year1.loc[[3], EXPECTED_COLUMNS])

    full_fraction = select_student_sample(year1, fraction=1)
    assert full_fraction["gal_id"].tolist() == [900, 902]
    empty = select_student_sample(year1, fraction=0)
    pd.testing.assert_frame_equal(empty, year1.iloc[:0][EXPECTED_COLUMNS])
    blank_input = select_student_sample(year1.iloc[:0], fraction=0.02)
    pd.testing.assert_frame_equal(blank_input, empty)


@pytest.mark.parametrize("fraction", [-0.01, 1.01, np.inf, -np.inf, np.nan])
def test_student_fraction_must_be_finite_and_within_zero_and_one(fraction):
    with pytest.raises(ValueError, match="fraction"):
        select_student_sample(_year1_table(0.02), fraction=fraction)


def test_student_cli_writes_readable_subset_and_verified_manifest(tmp_path):
    fraction = load().cuts.student_fraction
    year1 = _year1_table(fraction)
    folder = tmp_path / "processed" / "year1"
    folder.mkdir(parents=True)
    source = folder / "A.parquet"
    pq.write_table(pa.Table.from_pandas(year1, schema=YEAR1_SCHEMA, preserve_index=False), source)
    command = [sys.executable, "-B", str(SCRIPT), "--student-only", "--catalogue", "A",
               "--data-root", str(tmp_path)]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stdout + ran.stderr

    output = folder / "student_A.parquet"
    loaded = pd.read_parquet(output)
    expected = year1.loc[[3] if fraction > 0 else [], EXPECTED_COLUMNS].reset_index(drop=True)
    pd.testing.assert_frame_equal(loaded, expected)
    assert output.stat().st_size < 200_000_000
    manifest = verified_entry(folder / "manifest.json", output)
    assert manifest["row_count"] == len(expected)
    assert not (folder / "student_B.parquet").exists()
