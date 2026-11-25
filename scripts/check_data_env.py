"""Print pipeline package versions and check the Diffsky HDF5 filter."""

from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

import h5py
import hdf5plugin
import numpy as np


def main():
    for package in ("numpy", "pandas", "astropy", "pyarrow", "h5py", "hdf5plugin",
                    "fsspec", "requests", "pytest", "responses", "photerr", "speclite"):
        print(f"{package} {version(package)}")
    available = h5py.h5z.filter_avail(32026)
    print(f"HDF5 filter 32026 available: {available}")
    if not available:
        raise SystemExit("Blosc2 is unavailable; see Appendix A of the pipeline plan.")
    with TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
        path = Path(folder) / "blosc2.hdf5"
        values = np.arange(1024, dtype=np.int64)
        with h5py.File(path, "w") as handle:
            dataset = handle.create_dataset("values", data=values, **hdf5plugin.Blosc2(
                cname="lz4", filters=hdf5plugin.Blosc2.BITSHUFFLE))
            filter_mask, _ = dataset.id.read_direct_chunk((0,))
            assert filter_mask == 0, "HDF5 skipped the Blosc2 filter"
        with h5py.File(path) as handle:
            np.testing.assert_array_equal(handle["values"][:], values)
    print(f"Blosc2 LZ4/bitshuffle round trip: {len(values)} exact values")


if __name__ == "__main__":
    main()
