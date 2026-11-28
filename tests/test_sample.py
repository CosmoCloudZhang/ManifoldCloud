"""Check repeatable raw sampling and offline verification on fabricated catalogues."""

from shutil import copytree
from types import SimpleNamespace

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from manifoldcloud.acquisition import sample
from manifoldcloud.acquisition.fetch_diffsky import diffsky_folder
from manifoldcloud.acquisition.fetch_flagship import flagship_folder
from manifoldcloud.core.provenance import load_manifest, record_file
from manifoldcloud.core.sampling import uniform_from_id


FLAGSHIP_COLUMNS = ("galaxy_id", "random_index", "true_redshift_gal", "observed_redshift_gal")
DIFFSKY_COLUMNS = ("gal_id", "ra")
WITHHELD = ("true_redshift_gal", "observed_redshift_gal")
CONFIG = SimpleNamespace(
    flagship=SimpleNamespace(columns=FLAGSHIP_COLUMNS),
    diffsky=SimpleNamespace(catalogue="c_test", steps=[97, 487], columns=DIFFSKY_COLUMNS, area_deg2=34.3774),
)


def _store(folder, name, table):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    pq.write_table(table, path)
    record_file(folder / "manifest.json", path, source="fixture", command="test", row_count=table.num_rows)
    return path


@pytest.fixture
def raw_files(tmp_path):
    flagship = pa.table({
        "galaxy_id": [101, 102, 103, 104],
        "random_index": pa.array([0.0, 0.0099, 0.01, 0.5], type=pa.float32()),
        "true_redshift_gal": pa.nulls(4, type=pa.float32()),
        "observed_redshift_gal": pa.nulls(4, type=pa.float32()),
    }, metadata={b"comments": b"Someone <someone@example.org>"})
    files = {"flagship": _store(flagship_folder(tmp_path), "flagship.parquet", flagship)}
    diffsky = diffsky_folder(tmp_path, CONFIG)
    for step, identifiers in ((97, [2, 0, 1]), (487, [-1, 12345, 987654321012345])):
        shell = pa.table({
            "gal_id": identifiers,
            "ra": [230.1, 230.2, 230.3],
            "is_synthetic": [True, False, False],
            "step": pa.array([step] * 3, type=pa.int16()),
        }, metadata={b"fixture": b"raw shell"})
        files[f"shell_{step}"] = _store(diffsky, f"shell_{step}.parquet", shell)
    return files


def test_uniform_from_id_matches_known_hashes():
    identifiers = np.array([0, 1, 2, 12345, 987654321012345, -1], dtype=np.int64)
    result = uniform_from_id(identifiers)
    assert result.dtype == np.float32
    assert np.all((result >= 0) & (result < 1))
    np.testing.assert_array_equal(uniform_from_id(identifiers[::-1]), result[::-1])
    np.testing.assert_array_equal(
        np.rint(result.astype(np.float64) * 2**24),
        [14819496, 9505325, 9918517, 2232706, 5985647, 14997873],
    )


def test_flagship_sample_preserves_order_and_drops_comments(tmp_path, raw_files):
    path = raw_files["flagship"]
    table = sample.sample_flagship(path, 0.01)
    assert table.schema.equals(pq.read_schema(path).remove_metadata(), check_metadata=True)
    assert table["galaxy_id"].to_pylist() == [101, 102]

    sample.make(CONFIG, tmp_path, 0.01, "test")
    output = tmp_path / "sample" / sample.FLAGSHIP_NAME
    assert b"comments" not in pq.read_schema(output).metadata
    assert b"someone@example.org" not in output.read_bytes()


def test_diffsky_sample_preserves_order_and_columns(tmp_path, raw_files):
    table = sample.sample_diffsky(diffsky_folder(tmp_path, CONFIG), CONFIG.diffsky.steps, 0.6)
    expected = pa.concat_tables([
        pq.ParquetFile(raw_files["shell_97"]).read().take([0, 2]),
        pq.ParquetFile(raw_files["shell_487"]).read().take([1, 2]),
    ]).replace_schema_metadata(None)
    assert table.equals(expected, check_metadata=True)
    assert table["step"].to_pylist() == [97, 97, 487, 487]


def test_student_sample_withholds_columns_and_verifies_without_raw_files(tmp_path, raw_files):
    sample.make(CONFIG, tmp_path, 0.6, "test")
    sample.make(CONFIG, tmp_path, 0.6, "test", folder="sample_student", withhold=WITHHELD)
    full, student = tmp_path / "sample", tmp_path / "sample_student"
    columns = pq.read_schema(student / sample.FLAGSHIP_NAME).names
    assert columns == [name for name in FLAGSHIP_COLUMNS if name not in WITHHELD]
    assert pq.read_schema(full / sample.FLAGSHIP_NAME).names == list(FLAGSHIP_COLUMNS)
    assert (full / sample.DIFFSKY_NAME).read_bytes() == (student / sample.DIFFSKY_NAME).read_bytes()
    files = load_manifest(student / "manifest.json")["files"]
    assert files[sample.FLAGSHIP_NAME]["details"]["withheld"] == sorted(WITHHELD)
    assert files[sample.DIFFSKY_NAME]["details"]["withheld"] == []

    student_root = tmp_path / "student_root"
    copytree(student, student_root / "sample")
    assert sample.verify(CONFIG, student_root) is True


@pytest.mark.parametrize("column", ["unknown", "random_index", "gal_id"])
def test_make_rejects_unavailable_or_required_columns(tmp_path, raw_files, column):
    with pytest.raises(ValueError, match=column):
        sample.make(CONFIG, tmp_path, 0.6, "test", withhold=(column,))


def test_repeated_make_has_identical_parquet_digests(tmp_path, raw_files):
    manifest = tmp_path / "sample" / "manifest.json"
    sample.make(CONFIG, tmp_path, 0.6, "test")
    first = load_manifest(manifest)["files"]
    sample.make(CONFIG, tmp_path, 0.6, "test")
    second = load_manifest(manifest)["files"]
    for name in (sample.FLAGSHIP_NAME, sample.DIFFSKY_NAME):
        assert second[name]["sha256"] == first[name]["sha256"]


def test_verify_rejects_a_changed_byte(tmp_path, raw_files):
    sample.make(CONFIG, tmp_path, 0.6, "test")
    assert sample.verify(CONFIG, tmp_path) is True
    output = tmp_path / "sample" / sample.FLAGSHIP_NAME
    with output.open("r+b") as stream:
        stream.seek(4)
        byte = stream.read(1)
        stream.seek(4)
        stream.write(bytes([byte[0] ^ 1]))
    assert sample.verify(CONFIG, tmp_path) is False


@pytest.mark.parametrize("name, missing", [("flagship", True), ("shell_487", False)])
def test_make_rejects_raw_files_that_fail_manifest_verification(tmp_path, raw_files, name, missing):
    path = raw_files[name]
    if missing:
        path.unlink()
    else:
        path.write_bytes(b"changed after acquisition")
    with pytest.raises(ValueError, match=r"Run python scripts/acquisition_status\.py"):
        sample.make(CONFIG, tmp_path, 0.6, "test")


@pytest.mark.parametrize("options, message", [
    (["--fraction", "0"], "fraction"),
    (["--fraction", "1.5"], "fraction"),
    (["--folder", "raw"], "raw"),
])
def test_main_rejects_invalid_options(tmp_path, capsys, options, message):
    with pytest.raises(SystemExit) as error:
        sample.main(["--data-root", str(tmp_path), "--make", *options])
    assert error.value.code != 0
    captured = capsys.readouterr()
    assert message in captured.err + captured.out
