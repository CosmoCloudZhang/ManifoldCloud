"""Publish complete files atomically and record their provenance and SHA-256."""

from contextlib import contextmanager
from datetime import UTC, datetime
import fcntl
from functools import cache
from hashlib import file_digest
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import shlex
import sys
from tempfile import NamedTemporaryFile


@contextmanager
def atomic_path(destination):
    """Yield a sibling .part path and publish it only if the writer succeeds."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=destination.parent, prefix=f".{destination.name}.",
                            suffix=".part", delete=False) as file:
        part = Path(file.name)
    try:
        yield part
        part.replace(destination)
    finally:
        part.unlink(missing_ok=True)


def write_text(destination, content):
    """Publish UTF-8 text."""
    with atomic_path(destination) as part:
        part.write_text(content, encoding="utf-8")


def write_json(destination, data):
    """Publish consistently formatted, standards-compliant JSON."""
    write_text(destination, json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")


def sha256(path):
    """Return the SHA-256 hex digest without loading the whole file."""
    with Path(path).open("rb") as file:
        return file_digest(file, "sha256").hexdigest()


def command_line(program, arguments=None):
    """Describe a command by its script in the repository, however it was started."""
    return shlex.join(["python", program, *(sys.argv[1:] if arguments is None else arguments)])


@cache
def _versions():
    versions = {"python": platform.python_version()}
    for name in ("manifoldcloud", "numpy", "pandas", "pyarrow", "h5py", "hdf5plugin", "fsspec",
                 "aiohttp", "requests", "astropy", "speclite", "photerr", "matplotlib"):
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            continue
    return versions


def load_manifest(path):
    """Read an existing manifest or return an empty one."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"files": {}}


def _entry_key(manifest_path, output):
    return str(Path(output).resolve().relative_to(Path(manifest_path).parent.resolve()))


def _portable(source, folder):
    """Express local paths relative to the manifest folder; leave URLs and labels alone.

    A manifest then reads the same on every machine, and a data root can be
    moved without leaving absolute paths behind.
    """
    if isinstance(source, (list, tuple)):
        return [_portable(item, folder) for item in source]
    if isinstance(source, Path) or (isinstance(source, str) and os.path.isabs(source)):
        return Path(os.path.relpath(Path(source).resolve(), folder)).as_posix()
    return source


def verified_entry(manifest_path, output):
    """Return the entry if the output file exists and matches its recorded digest."""
    entry = load_manifest(manifest_path)["files"].get(_entry_key(manifest_path, output))
    if entry and Path(output).is_file() and sha256(output) == entry.get("sha256"):
        return entry
    return None


def record_file(manifest_path, output, *, source, command, row_count, details=None, raw=False):
    """Record one file using a safe source identifier and command supplied by the caller."""
    manifest_path = Path(manifest_path)
    output = Path(output)
    key = _entry_key(manifest_path, output)
    entry = {
        "source": _portable(source, manifest_path.parent.resolve()),
        "command": command,
        "row_count": row_count,
        "package_versions": _versions(),
        "sha256": sha256(output),
        "utc_time": datetime.now(UTC).isoformat(),
    }
    if details is not None:
        entry["details"] = details
    # Keep the lock inode stable across atomic manifest replacements.
    lock = manifest_path.with_name(f".{manifest_path.name}.lock.part")
    with lock.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        manifest = load_manifest(manifest_path)
        manifest["files"][key] = entry
        write_json(manifest_path, manifest)
    if raw:
        output.chmod(output.stat().st_mode & ~0o222)
    return entry
