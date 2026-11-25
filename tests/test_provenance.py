"""Verify atomic publication, streaming SHA-256 and resumable manifest entries."""

import hashlib

import pytest

from manifoldcloud.provenance import atomic_path, load_manifest, record_file, verified_entry


def test_atomic_file_and_manifest(tmp_path):
    output = tmp_path / "rows.parquet"
    manifest = tmp_path / "manifest.json"
    payload = b"test catalogue data"
    with atomic_path(output) as part:
        assert part.name.endswith(".part")
        assert not output.exists()
        part.write_bytes(payload)
    assert output.read_bytes() == payload
    assert not part.exists()
    assert verified_entry(manifest, output) is None
    record_file(manifest, output, source="fixture", command="test", row_count=7, raw=True)
    entry = load_manifest(manifest)["files"][output.name]
    assert entry["sha256"] == hashlib.sha256(payload).hexdigest()
    assert entry["row_count"] == 7
    assert entry["utc_time"].endswith("+00:00")
    assert entry["package_versions"]["python"]
    assert not output.stat().st_mode & 0o222
    assert verified_entry(manifest, output) == entry
    with atomic_path(output) as part:
        part.write_bytes(b"different bytes")
    assert verified_entry(manifest, output) is None


def test_write_failure_preserves_previous_file(tmp_path):
    output = tmp_path / "summary.json"
    output.write_text("original")
    with pytest.raises(RuntimeError, match="interrupted"):
        with atomic_path(output) as part:
            part.write_text("unfinished")
            raise RuntimeError("interrupted")
    assert output.read_text() == "original"
    assert list(tmp_path.iterdir()) == [output]
