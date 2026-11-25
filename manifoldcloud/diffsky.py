"""Read selected columns from local or HTTPS Diffsky HDF5 shells."""

import asyncio
from bisect import bisect_right
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp
from fsspec.asyn import sync
from fsspec.implementations.http import HTTPFile, HTTPFileSystem
import h5py
import hdf5plugin  # Registers the Blosc2 filter with h5py.
import pandas as pd

GROUPS = ("cores", "synth_cores")
BLOCK_BYTES = 64 * 1024
COALESCE_GAP = 16 * 1024
MAX_RANGE_BYTES = 8 * 1024 * 1024
CONNECTIONS = 4
HEADERS = {"User-Agent": "ManifoldCloud/0.1", "Accept-Encoding": "identity"}


class TransferBudget:
    """Cap requested bytes across shells, reserving separately for each retry."""

    def __init__(self, limit=None):
        self.limit = limit
        self.bytes_reserved = 0
        self.bytes_received = 0
        self.requests = 0

    def reserve(self, size):
        if self.limit is not None and self.bytes_reserved + size > self.limit:
            raise ValueError(f"Diffsky byte budget exhausted ({self.limit:,} bytes)")
        self.bytes_reserved += size
        self.requests += 1


def shell_location(location, step):
    """Return the path or URL of a shell in a catalogue directory."""
    name = f"lc_cores-{int(step)}.diffsky_gals.hdf5"
    location = str(location)
    if "://" not in location:
        return Path(location) / name
    parsed = urlsplit(location)
    if parsed.scheme != "https" or not parsed.hostname or any((
        parsed.username, parsed.password, parsed.query, parsed.fragment,
    )):
        raise ValueError("Diffsky requires a credential-free HTTPS base URL")
    return f"{location.rstrip('/')}/{name}"


async def _client(**options):
    return aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=CONNECTIONS),
        timeout=aiohttp.ClientTimeout(total=45), auto_decompress=False, **options,
    )


@contextmanager
def _filesystem():
    fs = HTTPFileSystem(get_client=_client, skip_instance_cache=True)
    session = sync(fs.loop, fs.set_session)
    try:
        yield fs, session
    finally:
        sync(fs.loop, session.close)


async def _head(session, url):
    for attempt in range(3):
        try:
            async with session.head(url, headers=HEADERS, allow_redirects=False) as response:
                response.raise_for_status()
                if response.status != 200 or "Content-Length" not in response.headers:
                    raise OSError(f"Expected a successful Diffsky HEAD with Content-Length: {url}")
                return int(response.headers["Content-Length"])
        except (aiohttp.ClientError, TimeoutError):
            if attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)


def resource_sizes(locations):
    """Yield HEAD sizes for HTTPS URLs and filesystem sizes for local paths."""
    locations = list(locations)
    if all(isinstance(path, Path) for path in locations):
        return [path.stat().st_size for path in locations]
    with _filesystem() as (fs, session):
        return [path.stat().st_size if isinstance(path, Path) else sync(fs.loop, _head, session, path)
                for path in locations]


def _coalesce(ranges):
    merged = []
    for start, end in sorted(set(ranges)):
        if merged and start <= merged[-1][1] + COALESCE_GAP and end <= merged[-1][0] + MAX_RANGE_BYTES:
            left, right = merged[-1]
            merged[-1] = (left, max(right, end))
        else:
            merged.append((start, end))
    return merged


class _RangeFile(HTTPFile):
    """Use fsspec's file interface with strict ranges and bounded prefetch."""

    def __init__(self, fs, url, session, size, budget):
        self.budget = budget
        self._parts = {}
        self._starts = []
        self._block = lru_cache(maxsize=128)(self._load_block)
        super().__init__(fs, url, session=session, size=size, cache_type="none", loop=fs.loop)

    async def _request(self, start, end):
        if start == 0 and end == self.size:
            raise OSError("Refusing a whole-file download for a Diffsky shell")
        expected = end - start
        headers = {**HEADERS, "Range": f"bytes={start}-{end - 1}"}
        for attempt in range(3):
            self.budget.reserve(expected)
            try:
                async with self.session.get(self.url, headers=headers, allow_redirects=False) as response:
                    response.raise_for_status()
                    content_range = response.headers.get("Content-Range")
                    requested_range = f"bytes {start}-{end - 1}/"
                    if (response.status != 206
                            or content_range not in (f"{requested_range}{self.size}", f"{requested_range}*")
                            or response.content_length not in (None, expected)):
                        raise OSError(
                            f"Expected Diffsky range {start}-{end - 1}/{self.size}; got HTTP "
                            f"{response.status}, Content-Range {content_range!r}, "
                            f"Content-Length {response.content_length!r}"
                        )
                    value = bytearray()
                    async for block in response.content.iter_chunked(1024 * 1024):
                        self.budget.bytes_received += len(block)
                        value.extend(block)
                        if len(value) > expected:
                            raise OSError("Diffsky returned more payload than the requested range")
                    if len(value) != expected:
                        raise aiohttp.ClientPayloadError("Incomplete Diffsky range")
                    return bytes(value)
            except (aiohttp.ClientError, TimeoutError):
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)

    def _load_block(self, start):
        return sync(self.loop, self._request, start, min(start + BLOCK_BYTES, self.size))

    def _fetch_range(self, start, end):
        end = min(end, self.size)
        if start >= end:
            return b""
        idx = bisect_right(self._starts, start) - 1
        if idx >= 0:
            left = self._starts[idx]
            data = self._parts[left]
            if end <= left + len(data):
                return data[start - left:end - left]
        if end - start >= BLOCK_BYTES:
            return sync(self.loop, self._request, start, end)
        first = start // BLOCK_BYTES * BLOCK_BYTES
        parts = [self._block(left)[max(0, start - left):end - left]
                 for left in range(first, end, BLOCK_BYTES)]
        return b"".join(parts)

    async def _load_ranges(self, ranges):
        for index in range(0, len(ranges), CONNECTIONS):
            group = ranges[index:index + CONNECTIONS]
            results = await asyncio.gather(*(self._request(*pair) for pair in group),
                                           return_exceptions=True)
            for (start, _), result in zip(group, results, strict=True):
                if isinstance(result, BaseException):
                    raise result
                self._parts[start] = result

    @contextmanager
    def prefetch(self, datasets):
        ranges = []
        for dataset in datasets:
            if dataset.chunks:
                for index in range(dataset.id.get_num_chunks()):
                    chunk = dataset.id.get_chunk_info(index)
                    ranges.append((chunk.byte_offset, chunk.byte_offset + chunk.size))
            elif dataset.size and dataset.id.get_offset() is not None:
                offset = dataset.id.get_offset()
                ranges.append((offset, offset + dataset.nbytes))
        try:
            sync(self.loop, self._load_ranges, _coalesce(ranges))
            self._starts = sorted(self._parts)
            yield
        finally:
            self._parts.clear()
            self._starts.clear()


@contextmanager
def open_shell(location, step, *, budget=None):
    """Open one shell, using only bounded HTTP byte ranges for a remote file."""
    path = shell_location(location, step)
    if isinstance(path, Path):
        with h5py.File(path, "r") as handle:
            handle._catalogue_folder = path.parent.name
            yield handle
        return
    budget = TransferBudget() if budget is None else budget
    with _filesystem() as (fs, session):
        size = sync(fs.loop, _head, session, path)
        with _RangeFile(fs, path, session, size, budget) as remote, h5py.File(remote, "r") as handle:
            handle._catalogue_folder = Path(urlsplit(path).path).parent.name
            handle._range_file = remote
            yield handle


def read_columns(file, columns):
    """Return the requested columns, with simulated rows before synthetic rows."""
    columns = list(columns)
    if len(set(columns)) != len(columns) or "is_synthetic" in columns:
        raise ValueError("Requested Diffsky columns must be unique and exclude is_synthetic")
    groups = [file[f"{name}/data"] for name in GROUPS]
    datasets = []
    for group in groups:
        try:
            datasets.append([group[column] for column in columns])
        except KeyError as error:
            missing = next(column for column in columns if column not in group)
            raise KeyError(f"Missing Diffsky column {missing!r} in {group.name}") from error
    row_counts = [len(next(iter(group.values()))) for group in groups]
    remote = getattr(file, "_range_file", None)

    def frames():
        return [pd.DataFrame({**{column: dataset[:] for column, dataset in zip(columns, group)},
                              "is_synthetic": synthetic}, index=range(count))
                for group, count, synthetic in zip(datasets, row_counts, (False, True))]

    if remote is None:
        parts = frames()
    else:
        with remote.prefetch(dataset for group in datasets for dataset in group):
            parts = frames()
    return pd.concat(parts, ignore_index=True)


def shell_info(file):
    """Return the redshift bounds, row and column counts, and catalogue label."""
    header = file["header"]
    groups = {name: file[f"{name}/data"] for name in GROUPS}
    catalogue = header.attrs.get("catalogue", header.attrs.get("catalog_name"))
    if catalogue is None:
        catalogue = getattr(file, "_catalogue_folder", "")
    if isinstance(catalogue, bytes):
        catalogue = catalogue.decode()
    return {
        "catalogue": str(catalogue),
        "z_range": tuple(float(value) for value in header["lightcone"].attrs["z_range"]),
        "rows": {name: len(next(iter(group.values()))) for name, group in groups.items()},
        "columns": {name: len(group) for name, group in groups.items()},
    }
