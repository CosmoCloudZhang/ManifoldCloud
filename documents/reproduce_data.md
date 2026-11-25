# Reproduce the ManifoldCloud Year 1 data

Catalogue A is Euclid Flagship 2, release 1.1. Catalogue B is Diffsky `c260710_09_02_2026`, patch 843. Both cover 34.3774 deg² and use the same Rubin Year 1 noise model. Diffsky is incomplete for a Year 1 sample below approximately z = 0.25. Its filter curves match Rubin `lsst2023` in `speclite`. The Flagship Rubin filter version remains unverified.

## Set up a fresh checkout

Run the commands from the repository root in a local checkout of the pipeline. Use the existing Python 3.12 mentor environment for catalogue preparation. Set `MENTOR_PYTHON` to its interpreter if your installation uses a different path.

```bash
MENTOR_PYTHON="$HOME/Software/minigorge3/envs/CosmoConda/bin/python"
"$MENTOR_PYTHON" -m venv --system-site-packages .venv
mkdir -p .venv/tmp
TMPDIR="$PWD/.venv/tmp" .venv/bin/python -m pip install --no-cache-dir \
  hdf5plugin==7.1.0 pytest==9.2.0 responses==0.26.3
TMPDIR="$PWD/.venv/tmp" .venv/bin/python -m pip install --no-cache-dir --no-deps --no-build-isolation -e .
.venv/bin/python scripts/check_data_env.py
```

The overnight environment check used `photerr` 1.6.0. It prints the installed versions and verifies HDF5 filter 32026 with a Blosc2 round trip.

Set the data root to an existing folder on the mounted catalogue disk. For an offline fixture run, an existing local `data/` directory also works. Scripts prefer `--data-root` over the environment variable and use `config/local.toml` if neither is supplied.

```bash
export MANIFOLDCLOUD_DATA_ROOT="/Volumes/Catalogues/ManifoldCloud"
test -d "$MANIFOLDCLOUD_DATA_ROOT"
```

## S08 and S09 Acquire Flagship 2

The mentor runs live CosmoHub steps. Confirm that CosmoHub permits scripted use before choosing API mode. The script prompts for the account e-mail and uses a hidden password prompt. Enter credentials at the prompts and keep them out of commands and config files.

### API mode

```bash
.venv/bin/python scripts/fetch_flagship.py --mode api --check-only
```

Review `raw/flagship2/mirror_843/catalog_metadata.json` under the data root. Verify the 26 requested columns, that `_el_model3_ext` fluxes include internal dust and emission lines, that `*_r50` is the major-axis half-light radius, and that `bulge_fraction` is a flux fraction. Record any correction in the decisions log and update the configuration before querying. If the API metadata route has changed, verify the descriptions in the catalogue page and use the manual workflow.

Run the count query first, then submit the data query in Parquet format.

```bash
.venv/bin/python scripts/fetch_flagship.py --mode api --count --submit
.venv/bin/python scripts/fetch_flagship.py --mode api --submit
```

If interrupted, use the query ID printed at submission time. Set `COUNT_QUERY_ID` or `DATA_QUERY_ID` to the corresponding numeric ID before running the matching command.

```bash
.venv/bin/python scripts/fetch_flagship.py --mode api --count --resume "$COUNT_QUERY_ID"
.venv/bin/python scripts/fetch_flagship.py --mode api --resume "$DATA_QUERY_ID"
```

### Manual mode

Inspect the catalogue column descriptions in the CosmoHub browser interface as in S08. Generate the two SQL files locally.

```bash
.venv/bin/python scripts/fetch_flagship.py --mode manual --count
.venv/bin/python scripts/fetch_flagship.py --mode manual
```

Open catalogue 353 in CosmoHub. In Expert Mode, paste `count_query.sql` from the data root's `raw/flagship2/mirror_843/` folder, submit it in Parquet format, and download the count result. Repeat with `query.sql` for the data result. Set `FLAGSHIP_COUNT_PARQUET` and `FLAGSHIP_DATA_PARQUET` to the two downloaded file paths. Ingest both files offline.

```bash
.venv/bin/python scripts/fetch_flagship.py --mode manual --count --input "$FLAGSHIP_COUNT_PARQUET"
.venv/bin/python scripts/fetch_flagship.py --mode manual --input "$FLAGSHIP_DATA_PARQUET"
```

Both workflows produce `counts.parquet`, `flagship.parquet`, the SQL files and `manifest.json` under the mirror-box directory.

### Verify the acquired Flagship rows offline

The check reads the 34.3774 deg² box in batches, compares with the count query and checks the reference density at i < 25.3.

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import os

import numpy as np
import pyarrow.parquet as pq

from manifoldcloud.config import load
from manifoldcloud.provenance import verified_entry

config = load()
box = config.flagship.box
folder = Path(os.environ["MANIFOLDCLOUD_DATA_ROOT"]) / "raw/flagship2/mirror_843"
manifest = folder / "manifest.json"
count_path = folder / "counts.parquet"
data_path = folder / "flagship.parquet"
assert verified_entry(manifest, count_path), "Count result checksum differs"
assert verified_entry(manifest, data_path), "Catalogue checksum differs"
count_row, = pq.read_table(count_path).to_pylist()
print(f"Count query {count_row}")

selected = 0
bright = 0
faintest = -np.inf
for batch in pq.ParquetFile(data_path).iter_batches(
    batch_size=250_000, columns=["ra_gal", "dec_gal", "kind", "lsst_i_el_model3_ext"],
):
    ra, dec, kind, flux = (column.to_numpy() for column in batch.columns)
    assert np.all((box.ra_min <= ra) & (ra < box.ra_max)), "RA outside the mirror box"
    assert np.all((box.dec_min <= dec) & (dec < box.dec_max)), "Dec outside the mirror box"
    assert np.isin(kind, (0, 1)).all(), "Unexpected galaxy kind"
    assert np.all(np.isfinite(flux) & (flux > 0)), "Invalid i-band flux"
    mag_i = -2.5 * np.log10(flux.astype(np.float64)) - 48.6
    assert np.all(mag_i < 26.5), "Row fails noiseless i < 26.5"
    selected += len(batch)
    bright += int(np.count_nonzero(mag_i < 25.3))
    faintest = max(faintest, mag_i.max())

assert selected == count_row["n_i265_kind_01"], "Row count differs from the count query"
assert faintest < 26.5, "Faintest i magnitude fails the selection"
density = bright / config.diffsky.area_deg2
print(f"Selected rows {selected:,}, faintest i {faintest:.8f}, density at i < 25.3 {density:,.1f} deg^-2")
assert abs(density - 192_700) <= 0.10 * 192_700, "Density differs from the reference by over 10%"
PY
```

## S05 Acquire all Diffsky shells

The four-shell pilot met the row and checksum checks. Its fastest measured run was 0.640 MB/s against the 2 MB/s performance gate. Use the local Globus workflow for the full extraction. The mentor copies the 67 `lc_cores-*.diffsky_gals.hdf5` files and the `diffsky_c260710_09_02_2026_transmission_curves.hdf5` support file to a catalogue directory on the mounted disk. Set `DIFFSKY_H5_DIR` to that directory.

```bash
export DIFFSKY_H5_DIR="/Volumes/Catalogues/c260710_09_02_2026"
.venv/bin/python scripts/fetch_diffsky.py --location "$DIFFSKY_H5_DIR" --dry-run --verify-full
.venv/bin/python scripts/fetch_diffsky.py --location "$DIFFSKY_H5_DIR" --verify-full
```

The dry-run total for the 67 source files is 116,531,444,695 bytes. Full verification checks the output SHA-256 values and reports any empty shells at the highest redshifts. Valid existing extractions are reused. If the mentor later accepts public HTTPS throughput, these commands use the configured public URL instead of a local directory. Supply the same transmission-curves support file locally for S11.

```bash
.venv/bin/python scripts/fetch_diffsky.py --dry-run --verify-full
.venv/bin/python scripts/fetch_diffsky.py --verify-full
```

## S10 to S13 Build, validate and hand over

With both raw catalogues ready, run the four pipeline commands in order. Set `DIFFSKY_H5_DIR` to the folder containing the support file, including if the shells were read over HTTPS.

```bash
.venv/bin/python scripts/harmonise.py
MPLCONFIGDIR="$PWD/.venv/tmp/matplotlib" .venv/bin/python scripts/validate.py \
  --curve-file "$DIFFSKY_H5_DIR/diffsky_c260710_09_02_2026_transmission_curves.hdf5"
.venv/bin/python scripts/make_year1_sample.py
.venv/bin/python scripts/make_year1_sample.py --student-only
```

Review `report/data_validation_summary.json`, `figures/data_validation/`, and `processed/year1/summary.json` under their respective repo or data roots. Full outputs are `processed/year1/A.parquet` and `processed/year1/B.parquet` under the data root. The `sample` flag selects finite noisy i < 24.1. The `control_sample` flag selects noiseless i < 24.1. Seeded noise uses fixed order and batches so rerunning the same inputs with the same packages reproduces the Parquet outputs.

The 21-column student files are `processed/year1/student_A.parquet` and `processed/year1/student_B.parquet` under the data root. The subset takes science rows with `random_index < 0.02`, controlled by `cuts.student_fraction` in `config/default.toml`.

In the `umapz` student environment from the Lecture 4 `output/environment.yml` recipe, open both files with pandas and confirm their byte and column limits.

```bash
conda activate umapz
python - <<'PY'
from pathlib import Path
import os

import pandas as pd

folder = Path(os.environ["MANIFOLDCLOUD_DATA_ROOT"]) / "processed/year1"
for name in ("student_A.parquet", "student_B.parquet"):
    path = folder / name
    size = path.stat().st_size
    assert size < 200_000_000, f"{name} exceeds the 200 MB limit"
    frame = pd.read_parquet(path)
    assert len(frame.columns) == 21
    print(f"{name} opened with pandas, {len(frame):,} rows, {len(frame.columns)} columns, {size:,} bytes")
PY
```

Flagship is distributed under CC BY-NC 3.0 IGO. Cite Castander, Fosalba et al. and CosmoHub. The mentor must decide whether either student subset can be redistributed. The project has yet to identify a Diffsky redistribution licence.
