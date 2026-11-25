"""Check that the ManifoldConda environment can run every part of the project.

Run it from the repository root after creating or updating the environment:

    python scripts/check_environment.py

Each line reports one check. The script compares the installed versions with
the pins in environment.yml and then runs a small real task with each group of
packages, so a pass means more than "the imports work".
"""

from contextlib import redirect_stderr, redirect_stdout
from importlib.metadata import PackageNotFoundError, version
import io
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
import time
import warnings

REPOSITORY = Path(__file__).resolve().parents[1]
# Conda package names that differ from the name Python reports.
INSTALLED_AS = {"python-duckdb": "duckdb"}


def pinned_versions():
    """Read the `name=version` and `name==version` pins from environment.yml."""
    pins = {}
    for line in (REPOSITORY / "environment.yml").read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*- ([A-Za-z0-9_.-]+)==?([0-9][0-9.]*)", line)
        if match:
            pins[match.group(1)] = match.group(2)
    return pins


def check_versions():
    pins = pinned_versions()
    wrong = []
    for name, pin in pins.items():
        if name == "python":
            found = ".".join(map(str, sys.version_info[:3]))
        else:
            try:
                found = version(INSTALLED_AS.get(name, name))
            except PackageNotFoundError:
                found = "missing"
        if found != pin and not found.startswith(pin + "."):
            wrong.append(f"{name} is {found}, the recipe pins {pin}")
    if wrong:
        raise RuntimeError("; ".join(wrong) + ". Run `conda env update -n ManifoldConda -f environment.yml --prune`.")
    return f"{len(pins)} pinned packages match environment.yml"


def check_package():
    from manifoldcloud.core.config import REPOSITORY as installed, load

    if installed != REPOSITORY:
        raise RuntimeError(f"manifoldcloud is installed from {installed}, not from this folder")
    config = load()
    return f"manifoldcloud {version('manifoldcloud')} from this folder, {len(config.diffsky.steps)} Diffsky shells configured"


def check_catalogue_files(folder):
    import duckdb
    import h5py
    import hdf5plugin
    import numpy as np
    import pandas as pd

    if not h5py.h5z.filter_avail(32026):
        raise RuntimeError("HDF5 filter 32026 (Blosc2) is unavailable, so Diffsky shells cannot be read")
    values = np.arange(1024, dtype=np.int64)
    path = folder / "blosc2.hdf5"
    with h5py.File(path, "w") as handle:
        dataset = handle.create_dataset("values", data=values, **hdf5plugin.Blosc2(
            cname="lz4", filters=hdf5plugin.Blosc2.BITSHUFFLE))
        filter_mask, _ = dataset.id.read_direct_chunk((0,))
        if filter_mask != 0:
            raise RuntimeError("HDF5 skipped the Blosc2 filter")
    with h5py.File(path) as handle:
        np.testing.assert_array_equal(handle["values"][:], values)
    table = folder / "table.parquet"
    pd.DataFrame({"values": values}).to_parquet(table, index=False)
    answer = duckdb.sql(f"SELECT COUNT(*) FROM read_parquet('{table}') WHERE \"values\" >= 512").fetchall()
    if answer != [(512,)]:
        raise RuntimeError("DuckDB read the Parquet test table incorrectly")
    return "Blosc2 HDF5 and Parquet round trips, DuckDB query"


def check_remote_access():
    import aiohttp
    import fsspec
    import requests
    import responses

    return f"fsspec {fsspec.__version__}, aiohttp {aiohttp.__version__}, requests {requests.__version__} (no network used)"


def check_photometry():
    import numpy as np
    import pandas as pd
    from photerr import LsstErrorModel
    from speclite.filters import load_filters

    bands = [curve.meta["band_name"] for curve in load_filters("lsst2023-*")]
    if bands != list("ugrizy"):
        raise RuntimeError(f"speclite returned Rubin bands {bands}")
    catalogue = pd.DataFrame({band: np.full(200, 24.0) for band in bands})
    noisy = LsstErrorModel(nYrObs=1)(catalogue, random_state=1)
    scatter = float(np.nanstd(noisy["i"]))
    if not 0.01 < scatter < 0.5:
        raise RuntimeError(f"photerr gave an i-band scatter of {scatter:.3f} mag at i = 24")
    return f"Rubin filter curves, Year 1 noise ({scatter:.3f} mag scatter at i = 24)"


def _colour_sample(rows, seed):
    """Fabricate magnitudes that depend smoothly on redshift, as real colours do."""
    import numpy as np

    rng = np.random.default_rng(seed)
    redshift = rng.uniform(0.05, 1.5, rows)
    table = {f"mag_{band}_lsst": 24 - 0.5 * index + (1.5 - 0.3 * index) * redshift + rng.normal(0, 0.05, rows)
             for index, band in enumerate("ugrizy")}
    return {**table, "redshift": redshift}


def check_manifold_learning():
    import numpy as np
    from minisom import MiniSom
    from openTSNE import TSNE
    from sklearn.decomposition import PCA
    import umap

    sample = _colour_sample(600, seed=2)
    features = np.column_stack([sample[f"mag_{band}_lsst"] for band in "ugrizy"])
    explained = PCA(n_components=2).fit(features).explained_variance_ratio_.sum()
    reducer = umap.UMAP(n_neighbors=15, random_state=3).fit(features[:500])
    placed = reducer.transform(features[500:])
    som = MiniSom(5, 5, features.shape[1], random_seed=4)
    som.train(features, 500)
    embedding = TSNE(n_iter=100, early_exaggeration_iter=50, random_state=5).fit(features[:300])
    if placed.shape != (100, 2) or not np.isfinite(placed).all() or embedding.shape != (300, 2):
        raise RuntimeError("An embedding returned the wrong shape or non-finite values")
    return f"PCA ({explained:.0%} in two components), UMAP with new points placed on a fitted map, MiniSom, openTSNE"


def check_rail(folder):
    import numpy as np
    from rail.interactive.estimation.algos import somoclu_som

    train, target = _colour_sample(1500, seed=6), _colour_sample(1500, seed=7)
    grid = np.linspace(0.0, 2.0, 401)
    here = Path.cwd()
    os.chdir(folder)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            trained = somoclu_som.somoclu_informer(training_data=train, hdf5_groupname="", n_rows=8, n_columns=8)
            result = somoclu_som.somoclu_summarizer(
                input_data=target, spec_data=train, model=trained["model"], hdf5_groupname="",
                spec_groupname="", zmin=0.0, zmax=2.0, nzbins=40, n_samples=5)
    finally:
        os.chdir(here)
    density = np.atleast_2d(result["single_NZ"].pdf(grid))[0]
    mean = float(np.trapezoid(grid * density, grid) / np.trapezoid(density, grid))
    truth = float(target["redshift"].mean())
    if abs(mean - truth) > 0.1:
        raise RuntimeError(f"RAIL's SOM gave a mean redshift of {mean:.3f}; the test sample has {truth:.3f}")
    return (f"RAIL SOM trained on one sample and calibrated another: mean z {mean:.3f} "
            f"against {truth:.3f} (pz-rail-base {version('pz-rail-base')}, qp {version('qp-prob')})")


def main():
    warnings.filterwarnings("ignore")
    print(f"Python {sys.version.split()[0]} at {sys.prefix}")
    failures = 0
    with TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        checks = (
            ("versions", check_versions),
            ("package", check_package),
            ("catalogue files", lambda: check_catalogue_files(scratch)),
            ("remote access", check_remote_access),
            ("photometry", check_photometry),
            ("manifold learning", check_manifold_learning),
            ("RAIL", lambda: check_rail(scratch)),
        )
        for name, check in checks:
            started = time.perf_counter()
            try:
                detail = check()
            except Exception as error:   # report every failing check, then exit non-zero
                failures += 1
                print(f"FAIL  {name}: {type(error).__name__}: {error}")
            else:
                print(f"ok    {name}: {detail} [{time.perf_counter() - started:.1f} s]")
    if failures:
        raise SystemExit(f"{failures} of {len(checks)} checks failed.")
    print("The environment is ready.")


if __name__ == "__main__":
    main()
