# ManifoldCloud overnight pipeline report

25 November 2026

The run used the repository’s `.venv` and ignored `data/` directory. The Flagship workflow was exercised with synthetic files and mocked HTTP. The live Diffsky checks used the public endpoint from the plan. Diffsky is incomplete for a Year 1 sample below approximately z = 0.25.

## Step status

| Step | Status | Evidence and remaining acceptance checks |
| --- | --- | --- |
| S00 Repository scaffolding | DONE | Baseline and scaffolding committed. Editable import and ignore rules passed. |
| S01 Environment | DONE | Blosc2 filter 32026 registered. The LZ4 and bitshuffle HDF5 round trip was exact. |
| S02 Configuration | DONE | CLI, environment and local TOML precedence checked. Flagship mirror bounds match the plan. |
| S03 Logging and provenance | DONE | Fake-secret redaction, atomic publication, SHA-256 verification and failure recovery checked. |
| S04 Diffsky reader | DONE | Synthetic Blosc2 fixture passed. The two opt-in live tests passed after validating the server’s wildcard total in the Content-Range header. Step 300 used 5,341,357 payload bytes for two columns. |
| S05 Diffsky pilot | BLOCKED | All prescribed counts and the four output checksums passed. The best measured end-to-end throughput was 0.640 MB/s, below the required >2.0 MB/s. The fetch code and verified pilot files are available. |
| S05 Full Diffsky acquisition | PENDING | Mentor run on the mounted disk. Verify all 67 files, the source-size sum and the manifest. |
| S06 Flagship SQL | DONE | Both queries matched their golden files byte for byte. Executable fixtures checked the 26-column selection, footprints and counts. |
| S07 CosmoHub client | DONE | Mocked sign-in, token rotation, polling, terminal states, download redirects and absence of fake credentials from logs, errors and files passed. Manual mode was exercised offline. |
| S08 Flagship column verification | PENDING | Mentor verifies CosmoHub permission and the catalogue descriptions. |
| S09 Flagship acquisition | PENDING | Mentor obtains and verifies the count and data query results. |
| S10 Harmonisation | DONE | Exact schema, finite rows, ordered axes and disk-axis round trips passed on the Diffsky pilot. Both synthetic raw schemas passed. Real Flagship checks and the cross-catalogue size comparison are PENDING (needs S09). |
| S11 Validation | DONE | Diffsky pilot plots and statistics are available. Depth peaks, depth fractions and filter curves passed. Real Flagship distributions and the two-catalogue comparison are PENDING (needs S09). |
| S12 Year 1 noise | DONE | Numerical gates and byte-for-byte reruns passed for Diffsky and the synthetic Flagship fixture. Gates on real Flagship are PENDING (needs S09). |
| S13 Student hand-over | DONE | The pilot B and synthetic A subsets passed the size and pandas readback checks in `.venv`. The guide’s manual flow passed in a clean local clone. Real Flagship hand-over is PENDING (needs S09). Readback in the named `umapz` environment is PENDING (interpreter unavailable). |

## Diffsky pilot measurements

| Step | Rows before selection | Synthetic rows before selection | Rows after noiseless i < 26.5 |
| --- | ---: | ---: | ---: |
| 487 | 880 | 183 | 622 |
| 442 | 14,724 | 11,362 | 13,844 |
| 392 | 51,476 | 40,019 | 46,182 |
| 300 | 339,890 | 280,356 | 197,334 |

Step 300 had 124,057 rows with noiseless i < 25.3 and p_merge < 0.5. The four harmonised files contain 257,982 rows. The pooled median half-light major axis at 23.5 < i < 24.5 was 0.369845 arcsec.

| Transport run | Payload bytes | Range requests | Wall time (s) | MB/s |
| --- | ---: | ---: | ---: | ---: |
| Initial coalesced ranges | 82,069,525 | 416 | 175.31 | 0.468 |
| Batched object headers and persistent range workers | 81,807,381 | 412 | 163.44 | 0.501 |
| 128 KiB metadata blocks and 64 KiB coalescing gap | 94,927,303 | 353 | 148.28 | 0.640 |

The three S05 runs reserved 258,804,209 bytes combined. Adding the complete reservation limits for all S04 and S11 attempts gives a conservative bound of 398,804,209 response-body bytes. The range reader limited concurrency to four.

The three floor-halo bright fractions were 63.3134%, 1.3783% and 0.0000%. Each reference magnitude peak matched, and the largest fraction difference was 0.3134 percentage points. Across the six Rubin curves, the largest absolute interpolation difference was 6.12 × 10⁻¹⁴. The [validation summary](../report/data_validation_summary.json) and [figures](../figures/data_validation/) use the four pilot shells.

The Year 1 science sample contains 116,460 pilot rows, with 116,097 in the noiseless control sample. The median i-band error was 0.127557 mag in the required magnitude window. Four science rows had noiseless i > 25.5 (0.00343%), and 2,912 had noiseless i > 24.1 (2.50043%). The student B file has 2,366 science rows, 21 columns and 299,599 bytes.

## Deviations and decisions

- The approved overnight prompt superseded the plan on Git, conda updates, the data root, and the split between the pilot and mentor acquisition. The repository uses `main` and has no Git remote.
- The initial editable install used pip’s default ephemeral wheel cache outside the repository. Subsequent installs and tests directed temporary work inside `.venv/` or `data/`. Dependency installation required approved outbound access after restricted DNS failed. The three selected distributions also resolved pytest’s `iniconfig` and `pluggy` dependencies. The mentor conda environment was left intact.
- S04 used fsspec with a strict range reader and coalescing. The server’s valid range replies reported a wildcard total. The reader used HEAD for file size and checked exact offsets and streaming lengths. The S11 support-file GET omitted Content-Length, so its retry used the size from HEAD and checked the received length.
- S05 retained pre-selection depth counts in its manifest so S11 could validate the faint magnitude peaks without reading the shells again. The fetch implementation was committed with the failed throughput gate recorded explicitly.
- S07 omitted optional keyring storage, which would require a dependency outside the overnight allowance. The real API envelopes and token behaviour remain mentor checks.
- S11 used exact DuckDB aggregates from projected local Parquet scans and a set 1 GB memory limit. The filter comparison allowed 1e-12 absolute error for aligning the differing 1 Å grids.
- S12 used seeds 42 and 43 for Flagship and Diffsky, fixed numerical shell order and fixed batch sizes. `sample` and `control_sample` are independent booleans. Provenance timestamps change on rerun. Output Parquet and summary JSON were byte-identical.
- S13 used the configured 0.02 fraction and 21 columns. The clean-clone check followed the local manual preparation and ingestion commands using synthetic equivalents for the two browser downloads. The named student environment was unavailable. See the [decisions log](decisions_log.md) for the recorded choices.

## Open mentor questions

- Does CosmoHub permit scripted use for catalogue 353, and does the first live result require the API token? If the API body shapes differ, which schema should the client accept?
- Do the catalogue descriptions confirm the emission-line flux variant, major-axis half-light radii and flux-based `bulge_fraction`? Which Rubin filter version did Flagship use?
- After the first real cross-catalogue comparison, are the Diffsky size units consistent with physical kpc?
- Which existing data-disk paths should be used for the full run? Is a local Globus transfer available for the Diffsky files?
- What terms govern redistribution of the Diffsky student data? How should the Flagship student copy be distributed under CC BY-NC 3.0 IGO?

## Mentor commands

Run these from the repository root using the existing `.venv`. Set the paths to the mounted disk and the local Diffsky copy.

```bash
export MANIFOLDCLOUD_DATA_ROOT="/Volumes/Catalogues/ManifoldCloud"
test -d "$MANIFOLDCLOUD_DATA_ROOT"
```

### S08 Verify Flagship metadata

After confirming scripted use with CosmoHub, run the metadata check. Review the saved column descriptions against the three assumptions in the plan. For the browser route, inspect the same descriptions on catalogue 353.

```bash
.venv/bin/python scripts/fetch_flagship.py --mode api --check-only
```

### S09 Acquire and verify Flagship

Run the count query before the data query. A resumed request uses the ID printed at submission.

```bash
.venv/bin/python scripts/fetch_flagship.py --mode api --count --submit
.venv/bin/python scripts/fetch_flagship.py --mode api --submit
# If a query was interrupted, set its numeric ID and run the matching command.
.venv/bin/python scripts/fetch_flagship.py --mode api --count --resume "$COUNT_QUERY_ID"
.venv/bin/python scripts/fetch_flagship.py --mode api --resume "$DATA_QUERY_ID"
```

For manual acquisition, generate the SQL and run each file in Expert Mode with Parquet output. Set the two variables to the downloaded paths before ingestion.

```bash
.venv/bin/python scripts/fetch_flagship.py --mode manual --count
.venv/bin/python scripts/fetch_flagship.py --mode manual
.venv/bin/python scripts/fetch_flagship.py --mode manual --count --input "$FLAGSHIP_COUNT_PARQUET"
.venv/bin/python scripts/fetch_flagship.py --mode manual --input "$FLAGSHIP_DATA_PARQUET"
```

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

### S05 Run full Diffsky acquisition

Copy the 67 HDF5 shells and the transmission-curve support file using Globus. Point the fetch script at the downloaded HDF5 directory, then run the verified local extraction.

```bash
export DIFFSKY_H5_DIR="/Volumes/Catalogues/c260710_09_02_2026"
.venv/bin/python scripts/fetch_diffsky.py --location "$DIFFSKY_H5_DIR" --dry-run --verify-full
.venv/bin/python scripts/fetch_diffsky.py --location "$DIFFSKY_H5_DIR" --verify-full
```

The dry run expects 116,531,444,695 bytes across 67 shells. The extraction checks the output hashes. After acquisition, follow the [reproduction guide](reproduce_data.md) for both catalogue builds, the filter comparison using the local support file, and student reproducibility in `umapz`.

## Files created or changed

Tracked additions and modifications since the baseline follow. This report is an additional tracked file.

```text
A	.gitignore
A	config/default.toml
A	config/local.example.toml
A	documents/decisions_log.md
A	documents/reproduce_data.md
M	environment.yml
A	figures/data_validation/colours.png
A	figures/data_validation/manifest.json
A	figures/data_validation/number_counts.png
A	figures/data_validation/redshift_distribution.png
A	figures/data_validation/sizes.png
A	manifoldcloud/__init__.py
A	manifoldcloud/config.py
A	manifoldcloud/cosmohub.py
A	manifoldcloud/diffsky.py
A	manifoldcloud/flagship.py
A	manifoldcloud/harmonise.py
A	manifoldcloud/logs.py
A	manifoldcloud/noise.py
A	manifoldcloud/provenance.py
A	manifoldcloud/sizes.py
A	manifoldcloud/validate.py
A	pyproject.toml
A	report/data_validation_summary.json
A	report/manifest.json
A	scripts/check_data_env.py
A	scripts/fetch_diffsky.py
A	scripts/fetch_flagship.py
A	scripts/harmonise.py
A	scripts/make_flagship_query.py
A	scripts/make_year1_sample.py
A	scripts/queries/flagship_mirror_843.sql
A	scripts/queries/flagship_mirror_843_count.sql
A	scripts/validate.py
A	tests/test_config.py
A	tests/test_cosmohub.py
A	tests/test_diffsky.py
A	tests/test_fetch_diffsky.py
A	tests/test_filter_curves.py
A	tests/test_flagship.py
A	tests/test_harmonise.py
A	tests/test_logs.py
A	tests/test_noise.py
A	tests/test_provenance.py
A	tests/test_sizes.py
A	tests/test_student_sample.py
A	tests/test_validate.py
A	documents/overnight_report.md
```

Files generated under the ignored data root follow.

```text
data/interim/harmonised/diffsky_843/shell_300.parquet
data/interim/harmonised/diffsky_843/shell_392.parquet
data/interim/harmonised/diffsky_843/shell_442.parquet
data/interim/harmonised/diffsky_843/shell_487.parquet
data/interim/harmonised/manifest.json
data/processed/year1/B.parquet
data/processed/year1/manifest.json
data/processed/year1/student_B.parquet
data/processed/year1/summary.json
data/raw/diffsky/c260710_09_02_2026/diffsky_c260710_09_02_2026_transmission_curves.hdf5
data/raw/diffsky/c260710_09_02_2026/manifest.json
data/raw/diffsky/c260710_09_02_2026/shell_300.parquet
data/raw/diffsky/c260710_09_02_2026/shell_392.parquet
data/raw/diffsky/c260710_09_02_2026/shell_442.parquet
data/raw/diffsky/c260710_09_02_2026/shell_487.parquet
```

Dependencies, bytecode, test results, plotting caches, the synthetic Flagship fixture and the clean-clone check live under ignored scratch paths. Manifest locks also use ignored `.part` names. The existing lecture and notebook folders remain untracked.

## Commands and actual output

The commands below ran from the repository root unless they change directory. Exit codes are recorded with the output. Trailing formatting spaces are omitted.

### S00 Repository scaffolding

#### S00 sandbox init

````bash
git init
````

Exit code 1.

````text
<repository>/.git: Operation not permitted
````

#### S00 approved init

````bash
git init
````

Exit code 0.

````text
Initialized empty Git repository in <repository>/.git/
````

#### S00 baseline

````bash
git add -- environment.yml documents/ && git diff --cached --name-only && git commit -m 'baseline before pipeline work'
````

Exit code 0.

````text
documents/codex_overnight_prompt.md
documents/data_pipeline_plan.md
documents/reference/blosc2_fallback_decoder.py
documents/reference/https_range_file.py
environment.yml
[main (root-commit) 3f3f6df] baseline before pipeline work
 5 files changed, 963 insertions(+)
 create mode 100644 documents/codex_overnight_prompt.md
 create mode 100644 documents/data_pipeline_plan.md
 create mode 100644 documents/reference/blosc2_fallback_decoder.py
 create mode 100644 documents/reference/https_range_file.py
 create mode 100644 environment.yml
````

#### S00 install import ignores

````bash
<conda>/envs/CosmoConda/bin/python -m venv --system-site-packages .venv && .venv/bin/python -m pip install --no-cache-dir --no-deps --no-build-isolation -e . && .venv/bin/python -c 'import manifoldcloud; print(manifoldcloud.__file__)' && git check-ignore config/local.toml .env x.parquet
````

Exit code 0.

````text
Obtaining file://<repository>
  Checking if build backend supports build_editable: started
  Checking if build backend supports build_editable: finished with status 'done'
  Preparing editable metadata (pyproject.toml): started
  Preparing editable metadata (pyproject.toml): finished with status 'done'
Building wheels for collected packages: manifoldcloud
  Building editable for manifoldcloud (pyproject.toml): started
  Building editable for manifoldcloud (pyproject.toml): finished with status 'done'
  Created wheel for manifoldcloud: filename=manifoldcloud-0.1.0-0.editable-py3-none-any.whl size=2802 sha256=cdff91847c12d1e89c5f5af57b24fce4a4a2384616f02165bd30322e48218c02
  Stored in directory: <tmp>/pip-ephem-wheel-cache-lcbt_627/wheels/7f/61/47/1e3218b865f0c702523965ec7970c624c7f450197ebe2b9a8b
Successfully built manifoldcloud
Installing collected packages: manifoldcloud
Successfully installed manifoldcloud-0.1.0
<repository>/manifoldcloud/__init__.py
config/local.toml
.env
x.parquet
````

#### S00 commit

````bash
git add -- .gitignore pyproject.toml manifoldcloud/__init__.py documents/decisions_log.md && git commit -m 'S00: repository scaffolding'
````

Exit code 0.

````text
[main e4a97bc] S00: repository scaffolding
 4 files changed, 37 insertions(+)
 create mode 100644 .gitignore
 create mode 100644 documents/decisions_log.md
 create mode 100644 manifoldcloud/__init__.py
 create mode 100644 pyproject.toml
````

### S01 Environment

#### S01 pip

````bash
mkdir -p .venv/tmp && TMPDIR="$PWD/.venv/tmp" PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_CONFIG_FILE=/dev/null .venv/bin/python -m pip install --no-cache-dir --index-url https://pypi.org/simple --retries 1 --timeout 12 hdf5plugin pytest responses
````

Exit code 1.

````text
WARNING: Retrying (Retry(total=0, connect=None, read=None, redirect=None, status=None)) after connection broken by 'NewConnectionError('<pip._vendor.urllib3.connection.HTTPSConnection object at 0x1071d1790>: Failed to establish a new connection: [Errno 8] nodename nor servname provided, or not known')': /simple/hdf5plugin/
ERROR: Could not find a version that satisfies the requirement hdf5plugin (from versions: none)
ERROR: No matching distribution found for hdf5plugin
````

#### S01 pip allowed network

````bash
TMPDIR="$PWD/.venv/tmp" PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_CONFIG_FILE=/dev/null .venv/bin/python -m pip install --no-cache-dir --index-url https://pypi.org/simple --retries 1 --timeout 12 hdf5plugin pytest responses
````

Exit code 0.

````text
Collecting hdf5plugin
  Downloading hdf5plugin-7.1.0-py3-none-macosx_11_0_arm64.whl.metadata (3.2 kB)
Collecting pytest
  Downloading pytest-9.2.0-py3-none-any.whl.metadata (7.9 kB)
Collecting responses
  Downloading responses-0.26.3-py3-none-any.whl.metadata (48 kB)
Requirement already satisfied: h5py>=3.0.0 in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from hdf5plugin) (3.16.0)
Collecting iniconfig>=2 (from pytest)
  Downloading iniconfig-2.3.1-py3-none-any.whl.metadata (2.8 kB)
Requirement already satisfied: packaging>=24 in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from pytest) (26.3)
Collecting pluggy<2,>=1.6 (from pytest)
  Downloading pluggy-1.7.0-py3-none-any.whl.metadata (5.0 kB)
Requirement already satisfied: pygments>=2.15 in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from pytest) (2.21.0)
Requirement already satisfied: requests<3.0,>=2.30.0 in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from responses) (2.34.2)
Requirement already satisfied: urllib3<3.0,>=1.25.10 in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from responses) (2.8.0)
Requirement already satisfied: pyyaml in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from responses) (6.0.3)
Requirement already satisfied: numpy>=1.21.2 in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from h5py>=3.0.0->hdf5plugin) (2.5.4)
Requirement already satisfied: charset_normalizer<4,>=2 in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from requests<3.0,>=2.30.0->responses) (3.5.1)
Requirement already satisfied: idna<4,>=2.5 in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from requests<3.0,>=2.30.0->responses) (3.20)
Requirement already satisfied: certifi>=2023.5.7 in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from requests<3.0,>=2.30.0->responses) (2026.10.23)
Downloading hdf5plugin-7.1.0-py3-none-macosx_11_0_arm64.whl (6.1 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 6.1/6.1 MB 52.3 MB/s eta 0:00:00
Downloading pytest-9.2.0-py3-none-any.whl (411 kB)
Downloading responses-0.26.3-py3-none-any.whl (36 kB)
Downloading iniconfig-2.3.1-py3-none-any.whl (7.6 kB)
Downloading pluggy-1.7.0-py3-none-any.whl (27 kB)
Installing collected packages: pluggy, iniconfig, responses, pytest, hdf5plugin
Successfully installed hdf5plugin-7.1.0 iniconfig-2.3.1 pluggy-1.7.0 pytest-9.2.0 responses-0.26.3
````

#### S01 filter

````bash
.venv/bin/python scripts/check_data_env.py
````

Exit code 0.

````text
numpy 2.5.4
pandas 3.1.1
astropy 8.0.2
pyarrow 26.0.1
h5py 3.16.0
hdf5plugin 7.1.0
fsspec 2026.9.0
requests 2.34.2
pytest 9.2.0
responses 0.26.3
photerr 1.6.0
speclite 0.20
HDF5 filter 32026 available: True
Blosc2 LZ4/bitshuffle round trip: 1024 exact values
````

#### S01 commit

````bash
git add -- environment.yml scripts/check_data_env.py documents/decisions_log.md && git commit -m 'S01: verify the pipeline environment'
````

Exit code 0.

````text
[main a3afa3a] S01: verify the pipeline environment
 3 files changed, 39 insertions(+)
 create mode 100644 scripts/check_data_env.py
````

### S02 Configuration

#### S02 configuration

````bash
.venv/bin/python -m pytest -q --basetemp=.venv/tmp/pytest tests/test_config.py && .venv/bin/python -c 'from manifoldcloud.config import load; print(load().flagship.box)'
````

Exit code 0.

````text
..                                                                       [100%]
2 passed in 0.02s
namespace(ra_min=226.66667, ra_max=233.33333, dec_min=23.16209, dec_max=28.90335)
````

#### S02 commit

````bash
git add -- config/default.toml config/local.example.toml manifoldcloud/config.py tests/test_config.py documents/decisions_log.md && git commit -m 'S02: catalogue configuration and data root'
````

Exit code 0.

````text
[main 5a5e5a1] S02: catalogue configuration and data root
 5 files changed, 134 insertions(+)
 create mode 100644 config/default.toml
 create mode 100644 config/local.example.toml
 create mode 100644 manifoldcloud/config.py
 create mode 100644 tests/test_config.py
````

### S03 Logging and provenance

#### S03 provenance

````bash
.venv/bin/python -m pytest -q --basetemp=.venv/tmp/pytest tests/test_provenance.py
````

Exit code 0.

````text
..                                                                       [100%]
2 passed in 0.01s
````

#### S03 logging and provenance

````bash
.venv/bin/python -B -m pytest -q --basetemp=.venv/tmp/pytest tests/test_logs.py tests/test_provenance.py
````

Exit code 0.

````text
......                                                                   [100%]
6 passed in 0.01s
````

#### S03 commit

````bash
git add -- manifoldcloud/logs.py manifoldcloud/provenance.py tests/test_logs.py tests/test_provenance.py && git commit -m 'S03: redacted logging and provenance'
````

Exit code 0.

````text
[main 885a4e9] S03: redacted logging and provenance
 4 files changed, 268 insertions(+)
 create mode 100644 manifoldcloud/logs.py
 create mode 100644 manifoldcloud/provenance.py
 create mode 100644 tests/test_logs.py
 create mode 100644 tests/test_provenance.py
````

### S04 Diffsky reader

#### S04 offline

````bash
.venv/bin/python -B -m pytest -q --basetemp=.venv/tmp/pytest tests/test_diffsky.py
````

Exit code 0.

````text
..                                                                       [100%]
2 passed, 2 deselected in 0.79s
````

#### S04 live

````bash
MANIFOLDCLOUD_DIFFSKY_NETWORK=1 .venv/bin/python -B -m pytest -q -s -m network --basetemp=.venv/tmp/pytest tests/test_diffsky.py
````

Exit code 1.

````text
FF
=================================== FAILURES ===================================
_____________________________ test_real_shell_487 ______________________________

    @pytest.mark.network
    @live
    def test_real_shell_487():
        budget = TransferBudget(limit=10_000_000)
>       with open_shell(BASE_URL, 487, budget=budget) as shell:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests/test_diffsky.py:67:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/contextlib.py:137: in __enter__
    return next(self.gen)
           ^^^^^^^^^^^^^^
manifoldcloud/diffsky.py:205: in open_shell
    with _RangeFile(fs, path, session, size, budget) as remote, h5py.File(remote, "r") as handle:
                                                                ^^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/h5py/_hl/files.py:555: in __init__
    fid = make_fid(name, mode, userblock_size, fapl, fcpl, swmr=swmr)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/h5py/_hl/files.py:232: in make_fid
    fid = h5f.open(name, flags, fapl=fapl)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
h5py/_objects.pyx:54: in h5py._objects.with_phil.wrapper
    ???
h5py/_objects.pyx:55: in h5py._objects.with_phil.wrapper
    ???
h5py/h5f.pyx:106: in h5py.h5f.open
    ???
h5py/h5fd.pyx:159: in h5py.h5fd.H5FD_fileobj_read
    ???
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/spec.py:2207: in readinto
    data = self.read(out.nbytes)
           ^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/implementations/http.py:649: in read
    return super().read(length)
           ^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/spec.py:2189: in read
    out = self.cache._fetch(self.loc, self.loc + length)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/caching.py:70: in _fetch
    return self.fetcher(start, stop)
           ^^^^^^^^^^^^^^^^^^^^^^^^^
manifoldcloud/diffsky.py:159: in _fetch_range
    parts = [self._block(left)[max(0, start - left):end - left]
             ^^^^^^^^^^^^^^^^^
manifoldcloud/diffsky.py:144: in _load_block
    return sync(self.loop, self._request, start, min(start + BLOCK_BYTES, self.size))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/asyn.py:106: in sync
    raise return_result
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/asyn.py:59: in _runner
    result[0] = await coro
                ^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <File-like object HTTPFileSystem, https://g-45a93.fd635.8443.data.globus.org/Diffsky/synthetic_galaxies/c260710_09_02_2026/lc_cores-487.diffsky_gals.hdf5>
start = 0, end = 65536

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
                    if (response.status != 206
                            or response.headers.get("Content-Range") != f"bytes {start}-{end - 1}/{self.size}"
                            or response.content_length != expected):
>                       raise OSError("Diffsky server did not return the exact requested byte range")
E                       OSError: Diffsky server did not return the exact requested byte range

manifoldcloud/diffsky.py:130: OSError
_____________ test_real_shell_300_transfers_only_requested_ranges ______________

    @pytest.mark.network
    @live
    def test_real_shell_300_transfers_only_requested_ranges():
        budget = TransferBudget(limit=30_000_000)
>       with open_shell(BASE_URL, 300, budget=budget) as shell:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests/test_diffsky.py:84:
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/contextlib.py:137: in __enter__
    return next(self.gen)
           ^^^^^^^^^^^^^^
manifoldcloud/diffsky.py:205: in open_shell
    with _RangeFile(fs, path, session, size, budget) as remote, h5py.File(remote, "r") as handle:
                                                                ^^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/h5py/_hl/files.py:555: in __init__
    fid = make_fid(name, mode, userblock_size, fapl, fcpl, swmr=swmr)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/h5py/_hl/files.py:232: in make_fid
    fid = h5f.open(name, flags, fapl=fapl)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
h5py/_objects.pyx:54: in h5py._objects.with_phil.wrapper
    ???
h5py/_objects.pyx:55: in h5py._objects.with_phil.wrapper
    ???
h5py/h5f.pyx:106: in h5py.h5f.open
    ???
h5py/h5fd.pyx:159: in h5py.h5fd.H5FD_fileobj_read
    ???
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/spec.py:2207: in readinto
    data = self.read(out.nbytes)
           ^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/implementations/http.py:649: in read
    return super().read(length)
           ^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/spec.py:2189: in read
    out = self.cache._fetch(self.loc, self.loc + length)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/caching.py:70: in _fetch
    return self.fetcher(start, stop)
           ^^^^^^^^^^^^^^^^^^^^^^^^^
manifoldcloud/diffsky.py:159: in _fetch_range
    parts = [self._block(left)[max(0, start - left):end - left]
             ^^^^^^^^^^^^^^^^^
manifoldcloud/diffsky.py:144: in _load_block
    return sync(self.loop, self._request, start, min(start + BLOCK_BYTES, self.size))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/asyn.py:106: in sync
    raise return_result
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/asyn.py:59: in _runner
    result[0] = await coro
                ^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <File-like object HTTPFileSystem, https://g-45a93.fd635.8443.data.globus.org/Diffsky/synthetic_galaxies/c260710_09_02_2026/lc_cores-300.diffsky_gals.hdf5>
start = 0, end = 65536

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
                    if (response.status != 206
                            or response.headers.get("Content-Range") != f"bytes {start}-{end - 1}/{self.size}"
                            or response.content_length != expected):
>                       raise OSError("Diffsky server did not return the exact requested byte range")
E                       OSError: Diffsky server did not return the exact requested byte range

manifoldcloud/diffsky.py:130: OSError
=========================== short test summary info ============================
FAILED tests/test_diffsky.py::test_real_shell_487 - OSError: Diffsky server d...
FAILED tests/test_diffsky.py::test_real_shell_300_transfers_only_requested_ranges
2 failed, 2 deselected in 3.36s
````

#### S04 live attempt 2

````bash
MANIFOLDCLOUD_DIFFSKY_NETWORK=1 .venv/bin/python -B -m pytest -q -s -m network --tb=short --basetemp=.venv/tmp/pytest tests/test_diffsky.py
````

Exit code 1.

````text
FF
=================================== FAILURES ===================================
_____________________________ test_real_shell_487 ______________________________
tests/test_diffsky.py:67: in test_real_shell_487
    with open_shell(BASE_URL, 487, budget=budget) as shell:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/contextlib.py:137: in __enter__
    return next(self.gen)
           ^^^^^^^^^^^^^^
manifoldcloud/diffsky.py:212: in open_shell
    with _RangeFile(fs, path, session, size, budget) as remote, h5py.File(remote, "r") as handle:
                                                                ^^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/h5py/_hl/files.py:555: in __init__
    fid = make_fid(name, mode, userblock_size, fapl, fcpl, swmr=swmr)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/h5py/_hl/files.py:232: in make_fid
    fid = h5f.open(name, flags, fapl=fapl)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
h5py/_objects.pyx:54: in h5py._objects.with_phil.wrapper
    ???
h5py/_objects.pyx:55: in h5py._objects.with_phil.wrapper
    ???
h5py/h5f.pyx:106: in h5py.h5f.open
    ???
h5py/h5fd.pyx:159: in h5py.h5fd.H5FD_fileobj_read
    ???
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/spec.py:2207: in readinto
    data = self.read(out.nbytes)
           ^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/implementations/http.py:649: in read
    return super().read(length)
           ^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/spec.py:2189: in read
    out = self.cache._fetch(self.loc, self.loc + length)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/caching.py:70: in _fetch
    return self.fetcher(start, stop)
           ^^^^^^^^^^^^^^^^^^^^^^^^^
manifoldcloud/diffsky.py:166: in _fetch_range
    parts = [self._block(left)[max(0, start - left):end - left]
             ^^^^^^^^^^^^^^^^^
manifoldcloud/diffsky.py:151: in _load_block
    return sync(self.loop, self._request, start, min(start + BLOCK_BYTES, self.size))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/asyn.py:106: in sync
    raise return_result
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/asyn.py:59: in _runner
    result[0] = await coro
                ^^^^^^^^^^
manifoldcloud/diffsky.py:131: in _request
    raise OSError(
E   OSError: Expected Diffsky range 0-65535/5600236; got HTTP 206, Content-Range 'bytes 0-65535/*', Content-Length 65536
_____________ test_real_shell_300_transfers_only_requested_ranges ______________
tests/test_diffsky.py:84: in test_real_shell_300_transfers_only_requested_ranges
    with open_shell(BASE_URL, 300, budget=budget) as shell:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/contextlib.py:137: in __enter__
    return next(self.gen)
           ^^^^^^^^^^^^^^
manifoldcloud/diffsky.py:212: in open_shell
    with _RangeFile(fs, path, session, size, budget) as remote, h5py.File(remote, "r") as handle:
                                                                ^^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/h5py/_hl/files.py:555: in __init__
    fid = make_fid(name, mode, userblock_size, fapl, fcpl, swmr=swmr)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/h5py/_hl/files.py:232: in make_fid
    fid = h5f.open(name, flags, fapl=fapl)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
h5py/_objects.pyx:54: in h5py._objects.with_phil.wrapper
    ???
h5py/_objects.pyx:55: in h5py._objects.with_phil.wrapper
    ???
h5py/h5f.pyx:106: in h5py.h5f.open
    ???
h5py/h5fd.pyx:159: in h5py.h5fd.H5FD_fileobj_read
    ???
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/spec.py:2207: in readinto
    data = self.read(out.nbytes)
           ^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/implementations/http.py:649: in read
    return super().read(length)
           ^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/spec.py:2189: in read
    out = self.cache._fetch(self.loc, self.loc + length)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/caching.py:70: in _fetch
    return self.fetcher(start, stop)
           ^^^^^^^^^^^^^^^^^^^^^^^^^
manifoldcloud/diffsky.py:166: in _fetch_range
    parts = [self._block(left)[max(0, start - left):end - left]
             ^^^^^^^^^^^^^^^^^
manifoldcloud/diffsky.py:151: in _load_block
    return sync(self.loop, self._request, start, min(start + BLOCK_BYTES, self.size))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/asyn.py:106: in sync
    raise return_result
../../Software/minigorge3/envs/CosmoConda/lib/python3.12/site-packages/fsspec/asyn.py:59: in _runner
    result[0] = await coro
                ^^^^^^^^^^
manifoldcloud/diffsky.py:131: in _request
    raise OSError(
E   OSError: Expected Diffsky range 0-65535/729684030; got HTTP 206, Content-Range 'bytes 0-65535/*', Content-Length 65536
=========================== short test summary info ============================
FAILED tests/test_diffsky.py::test_real_shell_487 - OSError: Expected Diffsky...
FAILED tests/test_diffsky.py::test_real_shell_300_transfers_only_requested_ranges
2 failed, 2 deselected in 3.18s
````

#### S04 live attempt 3

````bash
MANIFOLDCLOUD_DIFFSKY_NETWORK=1 .venv/bin/python -B -m pytest -q -s -m network --tb=short --basetemp=.venv/tmp/pytest tests/test_diffsky.py
````

Exit code 0.

````text
Step 487: c260710_09_02_2026, rows {'cores': 697, 'synth_cores': 183}, 327 columns per group
.Step 300: 339,890 rows, 5,341,357 payload bytes
.
2 passed, 2 deselected in 19.78s
````

#### S04 final offline

````bash
.venv/bin/python -B -m pytest -q --basetemp=.venv/tmp/pytest tests/test_diffsky.py
````

Exit code 0.

````text
..                                                                       [100%]
2 passed, 2 deselected in 0.76s
````

#### S04 commit

````bash
git add -- manifoldcloud/diffsky.py tests/test_diffsky.py documents/decisions_log.md && git commit -m 'S04: Diffsky reader'
````

Exit code 0.

````text
[main 6cd71f1] S04: Diffsky reader
 3 files changed, 352 insertions(+)
 create mode 100644 manifoldcloud/diffsky.py
 create mode 100644 tests/test_diffsky.py
````

### S05 Diffsky pilot and offline fetch checks

#### S05 pilot attempt 1

````bash
MANIFOLDCLOUD_DATA_ROOT="$PWD/data" .venv/bin/python -B scripts/fetch_diffsky.py --steps 487,442,392,300 --verify-pilot --byte-limit 125000000
````

Exit code 1.

````text
Step 487: 880 before, 622 after, 183 synthetic before; 2,051,994 bytes in 18.23 s
Step 442: 14,724 before, 13,844 after, 11,362 synthetic before; 6,135,117 bytes in 37.86 s
Step 392: 51,476 before, 46,182 after, 40,019 synthetic before; 12,597,683 bytes in 43.72 s
Step 300: 339,890 before, 197,334 after, 280,356 synthetic before; 61,284,731 bytes in 75.50 s
Step 300: i < 25.3 and p_merge < 0.5: 124,057 rows
Transfer: 82,069,525 payload bytes; 82,069,525 reserved bytes; 416 range requests; 175.31 s; 0.468 MB/s
Pilot throughput 0.468 MB/s did not exceed 2.0 MB/s
````

#### S05 offline

````bash
.venv/bin/python -B -m pytest -q --basetemp=.venv/tmp/pytest tests/test_fetch_diffsky.py
````

Exit code 0.

````text
..                                                                       [100%]
2 passed in 3.11s
````

#### S05 offline after coalescing

````bash
.venv/bin/python -B -m pytest -q --basetemp=.venv/tmp/pytest tests/test_diffsky.py tests/test_fetch_diffsky.py
````

Exit code 0.

````text
....                                                                     [100%]
4 passed, 2 deselected in 3.18s
````

#### S05 dry-run interface

````bash
.venv/bin/python -B scripts/fetch_diffsky.py --help && git diff --check
````

Exit code 0.

````text
usage: fetch_diffsky.py [-h] [--data-root DATA_ROOT] [--location LOCATION]
                        [--steps STEPS] [--dry-run] [--refresh]
                        [--byte-limit BYTE_LIMIT]
                        [--verify-pilot | --verify-full]

Extract selected Diffsky columns and publish resumable Parquet shells.

options:
  -h, --help            show this help message and exit
  --data-root DATA_ROOT
  --location LOCATION   Local directory or public HTTPS base URL
  --steps STEPS         Comma-separated subset of catalogue steps
  --dry-run             Show source sizes without downloading data
  --refresh             Re-read shells even if their checksums match
  --byte-limit BYTE_LIMIT
                        Maximum total byte reservations for range requests
  --verify-pilot        Check pilot counts and throughput
  --verify-full         Check full source size and output checksums
````

#### S05 pilot attempt 2

````bash
MANIFOLDCLOUD_DATA_ROOT="$PWD/data" .venv/bin/python -B scripts/fetch_diffsky.py --steps 487,442,392,300 --verify-pilot --refresh --byte-limit 125000000
````

Exit code 1.

````text
Step 487: 880 before, 622 after, 183 synthetic before; 1,986,458 bytes in 16.50 s
Step 442: 14,724 before, 13,844 after, 11,362 synthetic before; 6,069,581 bytes in 36.37 s
Step 392: 51,476 before, 46,182 after, 40,019 synthetic before; 12,532,147 bytes in 38.29 s
Step 300: 339,890 before, 197,334 after, 280,356 synthetic before; 61,219,195 bytes in 72.29 s
Step 300: i < 25.3 and p_merge < 0.5: 124,057 rows
Pilot throughput 0.501 MB/s did not exceed 2.0 MB/s
Transfer: 81,807,381 payload bytes; 81,807,381 reserved bytes; 412 range requests; 163.44 s; 0.501 MB/s
````

#### S05 raw outputs

````bash
MANIFOLDCLOUD_DATA_ROOT="$PWD/data" .venv/bin/python -B - <<'PY'
from pathlib import Path
import pyarrow.parquet as pq
from manifoldcloud.config import load, resolve_data_root
from manifoldcloud.provenance import verified_entry
config = load()
folder = resolve_data_root(config=config)/'raw'/'diffsky'/config.diffsky.catalogue
for step in config.diffsky.pilot_steps:
    file = folder/f'shell_{step}.parquet'
    entry = verified_entry(folder/'manifest.json', file)
    assert entry and not file.stat().st_mode & 0o222
    assert pq.ParquetFile(file).metadata.num_rows == entry['row_count']
    details = entry['details']
    print(f'{file.name}: SHA-256 verified, read-only; {details["z_range"]} z, {entry["row_count"]:,} rows; {details["depth"]}')
PY
````

Exit code 0.

````text
shell_487.parquet: SHA-256 verified, read-only; [0.0, 0.024464831804281495] z, 622 rows; {'floor_halo_bright_rows': 32, 'floor_halo_rows': 32, 'mag_bin_peak': [16.0, 16.5]}
shell_442.parquet: SHA-256 verified, read-only; [0.10076670317634195, 0.12794612794612803] z, 13,844 rows; {'floor_halo_bright_rows': 1586, 'floor_halo_rows': 2505, 'mag_bin_peak': [22.0, 22.5]}
shell_392.parquet: SHA-256 verified, read-only; [0.2422744128553771, 0.2705436156763592] z, 46,182 rows; {'floor_halo_bright_rows': 121, 'floor_halo_rows': 8779, 'mag_bin_peak': [24.5, 25.0]}
shell_300.parquet: SHA-256 verified, read-only; [0.6183574879227054, 0.655683690280066] z, 197,334 rows; {'floor_halo_bright_rows': 0, 'floor_halo_rows': 62705, 'mag_bin_peak': [26.5, 27.0]}
````

#### S05 offline after larger blocks

````bash
.venv/bin/python -B -m pytest -q --basetemp=.venv/tmp/pytest tests/test_diffsky.py tests/test_fetch_diffsky.py
````

Exit code 0.

````text
....                                                                     [100%]
4 passed, 2 deselected in 3.22s
````

#### S05 pilot attempt 3

````bash
MANIFOLDCLOUD_DATA_ROOT="$PWD/data" .venv/bin/python -B scripts/fetch_diffsky.py --steps 487,442,392,300 --verify-pilot --refresh --byte-limit 125000000
````

Exit code 1.

````text
Step 487: 880 before, 622 after, 183 synthetic before; 2,752,965 bytes in 11.32 s
Step 442: 14,724 before, 13,844 after, 11,362 synthetic before; 8,508,262 bytes in 29.84 s
Step 392: 51,476 before, 46,182 after, 40,019 synthetic before; 15,525,929 bytes in 35.99 s
Step 300: 339,890 before, 197,334 after, 280,356 synthetic before; 68,140,147 bytes in 71.12 s
Step 300: i < 25.3 and p_merge < 0.5: 124,057 rows
Transfer: 94,927,303 payload bytes; 94,927,303 reserved bytes; 353 range requests; 148.28 s; 0.640 MB/s
Pilot throughput 0.640 MB/s did not exceed 2.0 MB/s
````

#### S05 commit implementation

````bash
git add -- manifoldcloud/diffsky.py scripts/fetch_diffsky.py tests/test_fetch_diffsky.py documents/decisions_log.md && git commit -m 'S05: implement resumable fetch and record blocked pilot throughput'
````

Exit code 0.

````text
[main c88e7da] S05: implement resumable fetch and record blocked pilot throughput
 4 files changed, 326 insertions(+), 18 deletions(-)
 create mode 100644 scripts/fetch_diffsky.py
 create mode 100644 tests/test_fetch_diffsky.py
````

### S06 Flagship SQL

#### S06 generation

````bash
.venv/bin/python -B scripts/make_flagship_query.py && cat scripts/queries/flagship_mirror_843.sql scripts/queries/flagship_mirror_843_count.sql
````

Exit code 0.

````text
<repository>/scripts/queries/flagship_mirror_843.sql
<repository>/scripts/queries/flagship_mirror_843_count.sql
SELECT
  galaxy_id,
  halo_id,
  kind,
  random_index,
  ra_gal,
  dec_gal,
  true_redshift_gal,
  observed_redshift_gal,
  lsst_u_el_model3_ext,
  lsst_g_el_model3_ext,
  lsst_r_el_model3_ext,
  lsst_i_el_model3_ext,
  lsst_z_el_model3_ext,
  lsst_y_el_model3_ext,
  dominant_shape,
  bulge_fraction,
  bulge_r50,
  disk_r50,
  bulge_axis_ratio,
  disk_axis_ratio,
  bulge_nsersic,
  inclination_angle,
  log_stellar_mass,
  log_sfr,
  color_kind,
  euclid_nisp_h
FROM euclid_fs2_mock_dr_v1_1_phz
WHERE (ra_gal >= 226.66667 AND ra_gal < 233.33333
    AND dec_gal >= 23.16209 AND dec_gal < 28.90335)
  AND kind IN (0, 1)
  AND lsst_i_el_model3_ext > 0
  AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 26.5
SELECT
  COUNT(*) AS n_all,
  SUM(CASE WHEN kind IN (0, 1) THEN 1 ELSE 0 END) AS n_kind_01,
  SUM(CASE WHEN lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 26.5 THEN 1 ELSE 0 END) AS n_i265,
  SUM(CASE WHEN kind IN (0, 1) AND lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 26.5 THEN 1 ELSE 0 END) AS n_i265_kind_01,
  SUM(CASE WHEN lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 25.5 THEN 1 ELSE 0 END) AS n_i255,
  SUM(CASE WHEN kind IN (0, 1) AND lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 25.5 THEN 1 ELSE 0 END) AS n_i255_kind_01,
  SUM(CASE WHEN lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 25.3 THEN 1 ELSE 0 END) AS n_i253,
  SUM(CASE WHEN kind IN (0, 1) AND lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 25.3 THEN 1 ELSE 0 END) AS n_i253_kind_01,
  SUM(CASE WHEN lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 24.5 THEN 1 ELSE 0 END) AS n_i245,
  SUM(CASE WHEN kind IN (0, 1) AND lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 24.5 THEN 1 ELSE 0 END) AS n_i245_kind_01,
  SUM(CASE WHEN lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 24.1 THEN 1 ELSE 0 END) AS n_i241,
  SUM(CASE WHEN kind IN (0, 1) AND lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 24.1 THEN 1 ELSE 0 END) AS n_i241_kind_01
FROM euclid_fs2_mock_dr_v1_1_phz
WHERE (ra_gal >= 226.66667 AND ra_gal < 233.33333
    AND dec_gal >= 23.16209 AND dec_gal < 28.90335)
````

#### S06 fingerprints

````bash
.venv/bin/python -B - <<'PY'
from pathlib import Path
from manifoldcloud.provenance import sha256
for path in sorted(Path('scripts/queries').glob('flagship_mirror_843*.sql')):
    print(f'{path.name} {path.stat().st_size} bytes {sha256(path)}')
PY
````

Exit code 0.

````text
flagship_mirror_843.sql 707 bytes 308c178ee96dbb555e9c266a9829343f66ce7afdace5ea187a49e53ea33985d2
flagship_mirror_843_count.sql 1601 bytes db1d03fab6c83164f3bb693b078f09703793e8ee27c52e17acbd006e31a52716
````

#### S06 golden and SQL semantics

````bash
.venv/bin/python -B -m pytest -q --basetemp=.venv/tmp/pytest tests/test_flagship.py
````

Exit code 0.

````text
..                                                                       [100%]
2 passed in 0.24s
````

#### S06 commit

````bash
git add -- manifoldcloud/flagship.py scripts/make_flagship_query.py scripts/queries/flagship_mirror_843.sql scripts/queries/flagship_mirror_843_count.sql tests/test_flagship.py && git commit -m 'S06: generate Flagship extraction and count SQL'
````

Exit code 0.

````text
[main f821ca5] S06: generate Flagship extraction and count SQL
 5 files changed, 235 insertions(+)
 create mode 100644 manifoldcloud/flagship.py
 create mode 100644 scripts/make_flagship_query.py
 create mode 100644 scripts/queries/flagship_mirror_843.sql
 create mode 100644 scripts/queries/flagship_mirror_843_count.sql
 create mode 100644 tests/test_flagship.py
````

#### S06 final tests

````bash
.venv/bin/python -B -m pytest -q --basetemp=.venv/tmp/pytest tests/test_flagship.py && git status --short
````

Exit code 0.

````text
...                                                                      [100%]
3 passed in 0.02s
?? lectures/
?? notebooks/
?? scripts/fetch_flagship.py
````

### S07 Mock CosmoHub

#### S07 mocked suite

````bash
.venv/bin/python -B -m pytest -q --basetemp=.venv/tmp/pytest tests/test_cosmohub.py tests/test_logs.py
````

Exit code 0.

````text
.............                                                            [100%]
13 passed in 0.75s
````

#### S07 commit

````bash
git add -- manifoldcloud/cosmohub.py scripts/fetch_flagship.py tests/test_cosmohub.py documents/decisions_log.md && git commit -m 'S07: add manual Flagship ingest and mocked CosmoHub client'
````

Exit code 0.

````text
[main 69b570d] S07: add manual Flagship ingest and mocked CosmoHub client
 4 files changed, 598 insertions(+)
 create mode 100644 manifoldcloud/cosmohub.py
 create mode 100644 scripts/fetch_flagship.py
 create mode 100644 tests/test_cosmohub.py
````

#### S07 final mocked check

````bash
.venv/bin/python -B -m pytest -q --basetemp=.venv/tmp/pytest tests/test_cosmohub.py tests/test_logs.py
````

Exit code 0.

````text
.............                                                            [100%]
13 passed in 0.57s
````

#### S07 redirect follow-up commit

````bash
git add -- manifoldcloud/cosmohub.py && git commit -m 'S07: validate every result redirect and clear Basic auth'
````

Exit code 0.

````text
[main c9d63e1] S07: validate every result redirect and clear Basic auth
 1 file changed, 22 insertions(+), 10 deletions(-)
````

### S10 Harmonisation

#### S10 synthetic raw input

````bash
.venv/bin/python -B - <<'PY'
from pathlib import Path
import numpy as np
import pandas as pd
from manifoldcloud.config import load
from manifoldcloud.provenance import atomic_path
config = load()
path = Path('.venv/tmp/synthetic-data/raw/flagship2/mirror_843/flagship.parquet')
n = 400
magnitude = np.linspace(23.3, 26.4, n)
raw = pd.DataFrame({name: np.ones(n) for name in config.flagship.columns})
raw['galaxy_id'] = np.arange(n, dtype=np.int64)
raw['halo_id'] = np.arange(n, dtype=np.int64)
raw['kind'] = np.arange(n) % 2
raw['random_index'] = np.arange(n) / n
raw['ra_gal'], raw['dec_gal'] = 230.0, 25.0
raw['true_redshift_gal'], raw['observed_redshift_gal'] = 0.7, 0.701
for index, band in enumerate('ugrizy'):
    raw[f'lsst_{band}_el_model3_ext'] = 10 ** (-0.4 * (magnitude + (3 - index) * 0.2 + 48.6))
raw['dominant_shape'], raw['bulge_fraction'] = 1, 0.35
raw['bulge_r50'], raw['disk_r50'] = 0.25, 0.4
raw['bulge_axis_ratio'], raw['disk_axis_ratio'] = 0.8, 0.65
raw['log_stellar_mass'] = 10.0
with atomic_path(path) as part:
    raw.to_parquet(part, index=False)
print(f'Synthetic Flagship input: {len(raw)} rows, {len(raw.columns)} columns, {path}')
PY
````

Exit code 0.

````text
Synthetic Flagship input: 400 rows, 26 columns, .venv/tmp/synthetic-data/raw/flagship2/mirror_843/flagship.parquet
````

#### S10 CLI

````bash
MANIFOLDCLOUD_DATA_ROOT="$PWD/data" .venv/bin/python -B scripts/harmonise.py --catalogue B --steps 487,442,392,300 && .venv/bin/python -B scripts/harmonise.py --catalogue A --data-root .venv/tmp/synthetic-data
````

Exit code 0.

````text
B shell_487.parquet: 622 exact-schema finite rows; 622 flux or disk-axis round trips
B shell_442.parquet: 13,844 exact-schema finite rows; 13,844 flux or disk-axis round trips
B shell_392.parquet: 46,182 exact-schema finite rows; 46,182 flux or disk-axis round trips
B shell_300.parquet: 197,334 exact-schema finite rows; 197,334 flux or disk-axis round trips
B median a_hl at 23.5 < i < 24.5: 0.369845 arcsec
A flagship2_mirror_843.parquet: 400 exact-schema finite rows; 400 flux or disk-axis round trips
A median a_hl at 23.5 < i < 24.5: 0.354789 arcsec
````

#### S10 unit checks

````bash
.venv/bin/python -B -m pytest -q --basetemp=.venv/tmp/pytest tests/test_sizes.py tests/test_harmonise.py
````

Exit code 0.

````text
.............                                                            [100%]
13 passed in 0.81s
````

#### S10 commit

````bash
git add -- manifoldcloud/sizes.py manifoldcloud/harmonise.py scripts/harmonise.py tests/test_sizes.py tests/test_harmonise.py && git commit -m 'S10: harmonise both schemas and verify Diffsky pilot sizes'
````

Exit code 0.

````text
[main b77d5a8] S10: harmonise both schemas and verify Diffsky pilot sizes
 5 files changed, 474 insertions(+)
 create mode 100644 manifoldcloud/harmonise.py
 create mode 100644 manifoldcloud/sizes.py
 create mode 100644 scripts/harmonise.py
 create mode 100644 tests/test_harmonise.py
 create mode 100644 tests/test_sizes.py
````

### S11 Validation

#### S11 bounded optional live curve input

````bash
MANIFOLDCLOUD_DATA_ROOT="$PWD/data" .venv/bin/python -B - <<'PY'
from pathlib import Path
import h5py
import requests
from manifoldcloud.config import load, resolve_data_root
from manifoldcloud.provenance import atomic_path, record_file, verified_entry
config = load()
name = f'diffsky_{config.diffsky.catalogue}_transmission_curves.hdf5'
url = config.diffsky.location + name
path = resolve_data_root(config=config)/'raw'/'diffsky'/config.diffsky.catalogue/name
manifest = path.parent/'manifest.json'
headers = {'User-Agent': 'ManifoldCloud/0.1', 'Accept-Encoding': 'identity'}
if verified_entry(manifest, path) is None:
    with requests.Session() as session:
        session.trust_env = False
        with session.head(url, headers=headers, allow_redirects=False, timeout=30) as response:
            if response.status_code != 200:
                raise SystemExit(f'Filter curves HEAD returned HTTP {response.status_code}')
            expected = int(response.headers['Content-Length'])
        if not 0 < expected <= 10_000_000:
            raise SystemExit(f'Filter curves outside the 10 MB reservation: {expected} bytes')
        with session.get(url, headers=headers, allow_redirects=False, timeout=30, stream=True) as response:
            if response.status_code != 200 or int(response.headers['Content-Length']) != expected:
                raise SystemExit(f'Unexpected filter curves response HTTP {response.status_code}')
            with atomic_path(path) as part, part.open('wb') as stream:
                received = 0
                for block in response.iter_content(65_536):
                    received += len(block)
                    if received > expected:
                        raise SystemExit('Filter curves response exceeded the declared size')
                    stream.write(block)
                if received != expected:
                    raise SystemExit('Filter curves response was truncated')
    print(f'Optional Diffsky curve input: {received:,} payload bytes')
    record_file(manifest, path, source=url, command='bounded Diffsky optional live curve check', row_count=None, raw=True)
with h5py.File(path) as file:
    def describe(name, obj):
        print(name, getattr(obj, 'shape', None), getattr(obj, 'dtype', None), {key: val for key, val in obj.attrs.items()})
    file.visititems(describe)
PY
````

Exit code 1.

````text
Traceback (most recent call last):
  File "<stdin>", line 22, in <module>
  File "<conda>/envs/CosmoConda/lib/python3.12/site-packages/requests/structures.py", line 65, in __getitem__
    return self._store[key.lower()][1]
           ~~~~~~~~~~~^^^^^^^^^^^^^
KeyError: 'content-length'
````

#### S11 bounded optional curve retry

````bash
MANIFOLDCLOUD_DATA_ROOT="$PWD/data" .venv/bin/python -B - <<'PY'
from pathlib import Path
import h5py
import requests
from manifoldcloud.config import load, resolve_data_root
from manifoldcloud.provenance import atomic_path, record_file, verified_entry
config = load()
name = f'diffsky_{config.diffsky.catalogue}_transmission_curves.hdf5'
url = config.diffsky.location + name
path = resolve_data_root(config=config)/'raw'/'diffsky'/config.diffsky.catalogue/name
manifest = path.parent/'manifest.json'
headers = {'User-Agent': 'ManifoldCloud/0.1', 'Accept-Encoding': 'identity'}
if verified_entry(manifest, path) is None:
    with requests.Session() as session:
        session.trust_env = False
        with session.head(url, headers=headers, allow_redirects=False, timeout=30) as response:
            if response.status_code != 200:
                raise SystemExit(f'Filter curves HEAD returned HTTP {response.status_code}')
            expected = int(response.headers['Content-Length'])
        if not 0 < expected <= 10_000_000:
            raise SystemExit(f'Filter curves outside the 10 MB reservation: {expected} bytes')
        with session.get(url, headers=headers, allow_redirects=False, timeout=30, stream=True) as response:
            if response.status_code != 200 or int(response.headers.get('Content-Length', expected)) != expected:
                raise SystemExit(f'Unexpected filter curves response HTTP {response.status_code}')
            with atomic_path(path) as part, part.open('wb') as stream:
                received = 0
                for block in response.iter_content(65_536):
                    received += len(block)
                    if received > expected:
                        raise SystemExit('Filter curves response exceeded the declared size')
                    stream.write(block)
                if received != expected:
                    raise SystemExit('Filter curves response was truncated')
    print(f'Optional Diffsky curve input: {received:,} payload bytes')
    record_file(manifest, path, source=url, command='bounded Diffsky optional live curve check', row_count=None, raw=True)
with h5py.File(path) as file:
    def describe(name, obj):
        print(name, getattr(obj, 'shape', None), getattr(obj, 'dtype', None), {key: val for key, val in obj.attrs.items()})
    file.visititems(describe)
PY
````

Exit code 0.

````text
Optional Diffsky curve input: 1,233,976 payload bytes
lsst_g None None {}
lsst_g/transmission (8500,) float64 {}
lsst_g/wave (8500,) float64 {}
lsst_i None None {}
lsst_i/transmission (8500,) float64 {}
lsst_i/wave (8500,) float64 {}
lsst_r None None {}
lsst_r/transmission (8500,) float64 {}
lsst_r/wave (8500,) float64 {}
lsst_u None None {}
lsst_u/transmission (8500,) float64 {}
lsst_u/wave (8500,) float64 {}
lsst_y None None {}
lsst_y/transmission (8500,) float64 {}
lsst_y/wave (8500,) float64 {}
lsst_z None None {}
lsst_z/transmission (8500,) float64 {}
lsst_z/wave (8500,) float64 {}
roman_F062 None None {}
roman_F062/transmission (2200,) float64 {}
roman_F062/wave (2200,) float64 {}
roman_F087 None None {}
roman_F087/transmission (2200,) float64 {}
roman_F087/wave (2200,) float64 {}
roman_F106 None None {}
roman_F106/transmission (2200,) float64 {}
roman_F106/wave (2200,) float64 {}
roman_F129 None None {}
roman_F129/transmission (2200,) float64 {}
roman_F129/wave (2200,) float64 {}
roman_F146 None None {}
roman_F146/transmission (2200,) float64 {}
roman_F146/wave (2200,) float64 {}
roman_F158 None None {}
roman_F158/transmission (2200,) float64 {}
roman_F158/wave (2200,) float64 {}
roman_F184 None None {}
roman_F184/transmission (2200,) float64 {}
roman_F184/wave (2200,) float64 {}
roman_F213 None None {}
roman_F213/transmission (2200,) float64 {}
roman_F213/wave (2200,) float64 {}
roman_Grism_0thOrder None None {}
roman_Grism_0thOrder/transmission (2200,) float64 {}
roman_Grism_0thOrder/wave (2200,) float64 {}
roman_Grism_1stOrder None None {}
roman_Grism_1stOrder/transmission (2200,) float64 {}
roman_Grism_1stOrder/wave (2200,) float64 {}
roman_Prism None None {}
roman_Prism/transmission (2200,) float64 {}
roman_Prism/wave (2200,) float64 {}
````

#### S11 compare support grids

````bash
.venv/bin/python -B - <<'PY'
from pathlib import Path
import h5py
import numpy as np
from speclite.filters import load_filter
path = next(Path('data/raw/diffsky').glob('*/*_transmission_curves.hdf5'))
with h5py.File(path) as file:
    for band in 'ugrizy':
        data=file[f'lsst_{band}']
        w=data['wave'][:]; y=data['transmission'][:]
        model=load_filter(f'lsst2023-{band}')
        matches = np.interp(w, model.wavelength, model.response, left=0, right=0)
        absmax=np.max(np.abs(matches-y))
        model_mask=(w>=model.wavelength[0]) & (w<=model.wavelength[-1])
        print(band, 'grid',w[0],w[-1],np.diff(w)[:3], 'max deviation',absmax,'at',w[np.argmax(np.abs(matches-y))], 'outside ref maxima',np.max(np.abs(y[~model_mask])))
PY
````

Exit code 0.

````text
u grid 3001.0 11500.000000001932 [1. 1. 1.] max deviation 1.5057399771478686e-15 at 3987.0000000002246 outside ref maxima 0.0
g grid 3001.0 11500.000000001932 [1. 1. 1.] max deviation 4.191091917959966e-15 at 5574.000000000586 outside ref maxima 0.0
r grid 3001.0 11500.000000001932 [1. 1. 1.] max deviation 2.2426505097428162e-14 at 6867.0000000008795 outside ref maxima 0.0
i grid 3001.0 11500.000000001932 [1. 1. 1.] max deviation 6.117328865684613e-14 at 7595.000000001045 outside ref maxima 0.0
z grid 3001.0 11500.000000001932 [1. 1. 1.] max deviation 1.532107773982716e-14 at 8239.000000001191 outside ref maxima 0.0
y grid 3001.0 11500.000000001932 [1. 1. 1.] max deviation 1.4654943925052066e-14 at 9515.00000000148 outside ref maxima 0.0
````

#### S11 pilot validation

````bash
MANIFOLDCLOUD_DATA_ROOT="$PWD/data" MPLCONFIGDIR="$PWD/.venv/tmp/matplotlib" .venv/bin/python -B scripts/validate.py --catalogue B --steps 487,442,392,300
````

Exit code 0.

````text
Matplotlib is building the font cache; this may take a moment.
Diffsky: 257,982 rows; {'i_lt_24_1': 116097, 'i_lt_25_3': 176581}
Diffsky depth: {'step': 442, 'status': 'passed', 'reference_z_range': [0.1, 0.13], 'expected_mag_bin_peak': [22.0, 22.5], 'expected_floor_halo_bright_percent': 63.0, 'z_range': [0.10076670317634195, 0.12794612794612803], 'mag_bin_peak': [22.0, 22.5], 'floor_halo_rows': 2505, 'floor_halo_bright_rows': 1586, 'floor_halo_bright_percent': 63.31337325349301, 'difference_percentage_points': 0.3133732534930118}
Diffsky depth: {'step': 392, 'status': 'passed', 'reference_z_range': [0.24, 0.27], 'expected_mag_bin_peak': [24.5, 25.0], 'expected_floor_halo_bright_percent': 1.4, 'z_range': [0.2422744128553771, 0.2705436156763592], 'mag_bin_peak': [24.5, 25.0], 'floor_halo_rows': 8779, 'floor_halo_bright_rows': 121, 'floor_halo_bright_percent': 1.378289098986217, 'difference_percentage_points': 0.021710901013782813}
Diffsky depth: {'step': 300, 'status': 'passed', 'reference_z_range': [0.62, 0.66], 'expected_mag_bin_peak': [26.5, 27.0], 'expected_floor_halo_bright_percent': 0.0, 'z_range': [0.6183574879227054, 0.655683690280066], 'mag_bin_peak': [26.5, 27.0], 'floor_halo_rows': 62705, 'floor_halo_bright_rows': 0, 'floor_halo_bright_percent': 0.0, 'difference_percentage_points': 0.0}
Diffsky u vs speclite lsst2023: maximum difference 1.51e-15 (8,500 samples)
Diffsky g vs speclite lsst2023: maximum difference 4.19e-15 (8,500 samples)
Diffsky r vs speclite lsst2023: maximum difference 2.24e-14 (8,500 samples)
Diffsky i vs speclite lsst2023: maximum difference 6.12e-14 (8,500 samples)
Diffsky z vs speclite lsst2023: maximum difference 1.53e-14 (8,500 samples)
Diffsky y vs speclite lsst2023: maximum difference 1.47e-14 (8,500 samples)
<repository>/report/data_validation_summary.json
<repository>/figures/data_validation/number_counts.png
<repository>/figures/data_validation/redshift_distribution.png
<repository>/figures/data_validation/sizes.png
<repository>/figures/data_validation/colours.png
````

#### S11 unit checks

````bash
.venv/bin/python -B -m pytest -q --basetemp=.venv/tmp/pytest tests/test_validate.py tests/test_filter_curves.py
````

Exit code 0.

````text
........                                                                 [100%]
8 passed in 1.09s
````

#### S11 final pilot validation

````bash
MANIFOLDCLOUD_DATA_ROOT="$PWD/data" MPLCONFIGDIR="$PWD/.venv/tmp/matplotlib" .venv/bin/python -B scripts/validate.py --catalogue B --steps 487,442,392,300
````

Exit code 0.

````text
Diffsky: 257,982 rows; {'i_lt_24_1': 116097, 'i_lt_25_3': 176581}
Diffsky depth: {'step': 442, 'status': 'passed', 'reference_z_range': [0.1, 0.13], 'expected_mag_bin_peak': [22.0, 22.5], 'expected_floor_halo_bright_percent': 63.0, 'z_range': [0.10076670317634195, 0.12794612794612803], 'mag_bin_peak': [22.0, 22.5], 'floor_halo_rows': 2505, 'floor_halo_bright_rows': 1586, 'floor_halo_bright_percent': 63.31337325349301, 'difference_percentage_points': 0.3133732534930118}
Diffsky depth: {'step': 392, 'status': 'passed', 'reference_z_range': [0.24, 0.27], 'expected_mag_bin_peak': [24.5, 25.0], 'expected_floor_halo_bright_percent': 1.4, 'z_range': [0.2422744128553771, 0.2705436156763592], 'mag_bin_peak': [24.5, 25.0], 'floor_halo_rows': 8779, 'floor_halo_bright_rows': 121, 'floor_halo_bright_percent': 1.378289098986217, 'difference_percentage_points': 0.021710901013782813}
Diffsky depth: {'step': 300, 'status': 'passed', 'reference_z_range': [0.62, 0.66], 'expected_mag_bin_peak': [26.5, 27.0], 'expected_floor_halo_bright_percent': 0.0, 'z_range': [0.6183574879227054, 0.655683690280066], 'mag_bin_peak': [26.5, 27.0], 'floor_halo_rows': 62705, 'floor_halo_bright_rows': 0, 'floor_halo_bright_percent': 0.0, 'difference_percentage_points': 0.0}
Diffsky u vs speclite lsst2023: maximum difference 1.51e-15 (8,500 samples)
Diffsky g vs speclite lsst2023: maximum difference 4.19e-15 (8,500 samples)
Diffsky r vs speclite lsst2023: maximum difference 2.24e-14 (8,500 samples)
Diffsky i vs speclite lsst2023: maximum difference 6.12e-14 (8,500 samples)
Diffsky z vs speclite lsst2023: maximum difference 1.53e-14 (8,500 samples)
Diffsky y vs speclite lsst2023: maximum difference 1.47e-14 (8,500 samples)
<repository>/report/data_validation_summary.json
<repository>/figures/data_validation/number_counts.png
<repository>/figures/data_validation/redshift_distribution.png
<repository>/figures/data_validation/sizes.png
<repository>/figures/data_validation/colours.png
````

#### S11 final artifact QA

````bash
MANIFOLDCLOUD_DATA_ROOT="$PWD/data" MPLCONFIGDIR="$PWD/.venv/tmp/matplotlib" .venv/bin/python -B scripts/validate.py --catalogue B --steps 487,442,392,300 && .venv/bin/python -B - <<'PY'
import json
from pathlib import Path
from PIL import Image
from manifoldcloud.provenance import verified_entry
path = Path('report/data_validation_summary.json')
summary = json.loads(path.read_text())
assert verified_entry(path.parent/'manifest.json', path)
assert summary['diffsky_depth']['passed']
assert sum(row['count'] for row in summary['catalogues']['B']['number_counts']) == 257_982
assert sum(row['count'] for row in summary['catalogues']['B']['redshift_distribution']) == 116_097
for image in sorted(Path('figures/data_validation').glob('*.png')):
    assert verified_entry(image.parent/'manifest.json', image)
    with Image.open(image) as figure:
        figure.verify()
        print(f'{image.name}: readable PNG, {figure.size}, SHA-256 verified')
PY
````

Exit code 0.

````text
Diffsky: 257,982 rows; {'i_lt_24_1': 116097, 'i_lt_25_3': 176581}
Diffsky depth: {'step': 442, 'status': 'passed', 'reference_z_range': [0.1, 0.13], 'expected_mag_bin_peak': [22.0, 22.5], 'expected_floor_halo_bright_percent': 63.0, 'z_range': [0.10076670317634195, 0.12794612794612803], 'mag_bin_peak': [22.0, 22.5], 'floor_halo_rows': 2505, 'floor_halo_bright_rows': 1586, 'floor_halo_bright_percent': 63.31337325349301, 'difference_percentage_points': 0.3133732534930118}
Diffsky depth: {'step': 392, 'status': 'passed', 'reference_z_range': [0.24, 0.27], 'expected_mag_bin_peak': [24.5, 25.0], 'expected_floor_halo_bright_percent': 1.4, 'z_range': [0.2422744128553771, 0.2705436156763592], 'mag_bin_peak': [24.5, 25.0], 'floor_halo_rows': 8779, 'floor_halo_bright_rows': 121, 'floor_halo_bright_percent': 1.378289098986217, 'difference_percentage_points': 0.021710901013782813}
Diffsky depth: {'step': 300, 'status': 'passed', 'reference_z_range': [0.62, 0.66], 'expected_mag_bin_peak': [26.5, 27.0], 'expected_floor_halo_bright_percent': 0.0, 'z_range': [0.6183574879227054, 0.655683690280066], 'mag_bin_peak': [26.5, 27.0], 'floor_halo_rows': 62705, 'floor_halo_bright_rows': 0, 'floor_halo_bright_percent': 0.0, 'difference_percentage_points': 0.0}
Diffsky u vs speclite lsst2023: maximum difference 1.51e-15 (8,500 samples)
Diffsky g vs speclite lsst2023: maximum difference 4.19e-15 (8,500 samples)
Diffsky r vs speclite lsst2023: maximum difference 2.24e-14 (8,500 samples)
Diffsky i vs speclite lsst2023: maximum difference 6.12e-14 (8,500 samples)
Diffsky z vs speclite lsst2023: maximum difference 1.53e-14 (8,500 samples)
Diffsky y vs speclite lsst2023: maximum difference 1.47e-14 (8,500 samples)
<repository>/report/data_validation_summary.json
<repository>/figures/data_validation/number_counts.png
<repository>/figures/data_validation/redshift_distribution.png
<repository>/figures/data_validation/sizes.png
<repository>/figures/data_validation/colours.png
colours.png: readable PNG, (1440, 1280), SHA-256 verified
number_counts.png: readable PNG, (1280, 752), SHA-256 verified
redshift_distribution.png: readable PNG, (1280, 752), SHA-256 verified
sizes.png: readable PNG, (1280, 752), SHA-256 verified
````

#### S11 commit

````bash
git add -- manifoldcloud/validate.py scripts/validate.py tests/test_validate.py tests/test_filter_curves.py figures/data_validation/colours.png figures/data_validation/number_counts.png figures/data_validation/redshift_distribution.png figures/data_validation/sizes.png figures/data_validation/manifest.json report/data_validation_summary.json report/manifest.json documents/decisions_log.md && git commit -m 'S11: validate Diffsky pilot and Rubin filter curves'
````

Exit code 0.

````text
[main 12d1b0f] S11: validate Diffsky pilot and Rubin filter curves
 12 files changed, 1036 insertions(+)
 create mode 100644 figures/data_validation/colours.png
 create mode 100644 figures/data_validation/manifest.json
 create mode 100644 figures/data_validation/number_counts.png
 create mode 100644 figures/data_validation/redshift_distribution.png
 create mode 100644 figures/data_validation/sizes.png
 create mode 100644 manifoldcloud/validate.py
 create mode 100644 report/data_validation_summary.json
 create mode 100644 report/manifest.json
 create mode 100644 scripts/validate.py
 create mode 100644 tests/test_filter_curves.py
 create mode 100644 tests/test_validate.py
````

### S12 Year 1 noise

#### S12 synthetic A

````bash
.venv/bin/python -B scripts/make_year1_sample.py --catalogue A --data-root .venv/tmp/synthetic-data
````

Exit code 0.

````text
Catalogue A, seed 42: {'rows': 400, 'science_rows': 105, 'control_rows': 103, 'i_error_rows': 25, 'median_i_error': 0.13366679847240448, 'science_true_i_gt_25_5_rows': 0, 'science_true_i_gt_25_5_fraction': 0.0, 'science_true_i_gt_cut_rows': 8, 'science_true_i_gt_cut_fraction': 0.0761904761904762, 'i_limit': 24.1}
Wrote <repository>/.venv/tmp/synthetic-data/processed/year1/A.parquet
Wrote <repository>/.venv/tmp/synthetic-data/processed/year1/summary.json
````

#### S12 pilot reproducibility

````bash
export MANIFOLDCLOUD_DATA_ROOT="$PWD/data"
.venv/bin/python -B scripts/make_year1_sample.py --catalogue B --steps 487,442,392,300 && .venv/bin/python -B - <<'PY'
from pathlib import Path
import subprocess
import sys
from manifoldcloud.provenance import sha256, verified_entry
folder = Path('data/processed/year1')
files = [folder/'B.parquet', folder/'summary.json']
before = {file.name: sha256(file) for file in files}
subprocess.run([sys.executable, '-B', 'scripts/make_year1_sample.py', '--catalogue', 'B', '--steps', '487,442,392,300'], check=True)
for file in files:
    digest = sha256(file)
    assert digest == before[file.name]
    assert verified_entry(folder/'manifest.json', file)
    print(f'{file.name}: identical SHA-256 across runs ({digest})')
PY
````

Exit code 0.

````text
Catalogue B, seed 43: {'rows': 257982, 'science_rows': 116460, 'control_rows': 116097, 'i_error_rows': 8939, 'median_i_error': 0.12755687534809113, 'science_true_i_gt_25_5_rows': 4, 'science_true_i_gt_25_5_fraction': 3.434655675768504e-05, 'science_true_i_gt_cut_rows': 2912, 'science_true_i_gt_cut_fraction': 0.025004293319594712, 'i_limit': 24.1}
Diffsky input: 4 shells. Diffsky is incomplete for a Year 1 sample below approximately z = 0.25.
Wrote <repository>/data/processed/year1/B.parquet
Wrote <repository>/data/processed/year1/summary.json
Catalogue B, seed 43: {'rows': 257982, 'science_rows': 116460, 'control_rows': 116097, 'i_error_rows': 8939, 'median_i_error': 0.12755687534809113, 'science_true_i_gt_25_5_rows': 4, 'science_true_i_gt_25_5_fraction': 3.434655675768504e-05, 'science_true_i_gt_cut_rows': 2912, 'science_true_i_gt_cut_fraction': 0.025004293319594712, 'i_limit': 24.1}
Diffsky input: 4 shells. Diffsky is incomplete for a Year 1 sample below approximately z = 0.25.
Wrote <repository>/data/processed/year1/B.parquet
Wrote <repository>/data/processed/year1/summary.json
B.parquet: identical SHA-256 across runs (eff00303a6220beb303843104b29ae19bb4ddc174a6707719f05913ecfdbcca8)
summary.json: identical SHA-256 across runs (c5dcfc74df2244af001c765e7dbf9d27e6338c57921fe55edcb23a3de2cc2a4d)
````

#### S12 installed photerr arguments

````bash
.venv/bin/python -B - <<'PY'
from importlib.metadata import version
from manifoldcloud.noise import make_noise_model
model = make_noise_model()
print('photerr',version('photerr'))
for name in ('nYrObs','extendedType','majorCol','minorCol','sigLim','ndFlag','decorrelate','renameDict'):
    print(name, repr(getattr(model.params,name)))
PY
````

Exit code 0.

````text
photerr 1.6.0
nYrObs 1
extendedType 'auto'
majorCol 'a_hl'
minorCol 'b_hl'
sigLim 0
ndFlag nan
decorrelate True
renameDict None
````

#### S12 effective band mapping

````bash
.venv/bin/python -B - <<'PY'
from manifoldcloud.noise import make_noise_model
params = make_noise_model().params
assert set(params.nVisYr) == {f'mag_{band}' for band in 'ugrizy'}
print('Effective photerr band mapping:', ', '.join(params.nVisYr))
PY
````

Exit code 0.

````text
Effective photerr band mapping: mag_u, mag_g, mag_r, mag_i, mag_z, mag_y
````

#### S12 synthetic reproducibility

````bash
.venv/bin/python -B - <<'PY'
from pathlib import Path
import subprocess
import sys
from manifoldcloud.provenance import sha256, verified_entry
folder = Path('.venv/tmp/synthetic-data/processed/year1')
files = [folder/'A.parquet', folder/'summary.json']
before = {file.name: sha256(file) for file in files}
subprocess.run([sys.executable, '-B', 'scripts/make_year1_sample.py', '--catalogue', 'A', '--data-root', '.venv/tmp/synthetic-data'], check=True)
for file in files:
    digest = sha256(file)
    assert digest == before[file.name]
    assert verified_entry(folder/'manifest.json', file)
    print(f'Synthetic {file.name}: identical SHA-256 across runs ({digest})')
PY
````

Exit code 0.

````text
Catalogue A, seed 42: {'rows': 400, 'science_rows': 105, 'control_rows': 103, 'i_error_rows': 25, 'median_i_error': 0.13366679847240448, 'science_true_i_gt_25_5_rows': 0, 'science_true_i_gt_25_5_fraction': 0.0, 'science_true_i_gt_cut_rows': 8, 'science_true_i_gt_cut_fraction': 0.0761904761904762, 'i_limit': 24.1}
Wrote <repository>/.venv/tmp/synthetic-data/processed/year1/A.parquet
Wrote <repository>/.venv/tmp/synthetic-data/processed/year1/summary.json
Synthetic A.parquet: identical SHA-256 across runs (1c0cfb2dcb8b30fa2ba3c08ee8444a2aef9ad5a2dc1c6b99a1a5e949be3e77dd)
Synthetic summary.json: identical SHA-256 across runs (fb82874189123829d65b6354cccb864a8b7d5897158b9c107bcaaf5ad4887e0a)
````

#### S12 exact unit checks

````bash
.venv/bin/python -B -m pytest -q --basetemp=.venv/tmp/pytest tests/test_noise.py
````

Exit code 0.

````text
....                                                                     [100%]
4 passed in 0.33s
````

#### S12 commit

````bash
git add -- manifoldcloud/noise.py scripts/make_year1_sample.py tests/test_noise.py documents/decisions_log.md && git commit -m 'S12: add reproducible Rubin Year 1 noise and selection'
````

Exit code 0.

````text
[main 23edb56] S12: add reproducible Rubin Year 1 noise and selection
 4 files changed, 284 insertions(+)
 create mode 100644 manifoldcloud/noise.py
 create mode 100644 scripts/make_year1_sample.py
 create mode 100644 tests/test_noise.py
````

### S13 Student hand-over

#### S13 student subsets and readback

````bash
MANIFOLDCLOUD_DATA_ROOT="$PWD/data" .venv/bin/python -B scripts/make_year1_sample.py --catalogue B --student-only && .venv/bin/python -B scripts/make_year1_sample.py --catalogue A --student-only --data-root .venv/tmp/synthetic-data && .venv/bin/python -B - <<'PY'
from pathlib import Path
import pandas as pd
from manifoldcloud.config import load
from manifoldcloud.provenance import verified_entry
from scripts.make_year1_sample import STUDENT_COLUMNS
fraction = load().cuts.student_fraction
for label, root in [('B', Path('data')), ('A', Path('.venv/tmp/synthetic-data'))]:
    folder = root/'processed'/'year1'
    path = folder/f'student_{label}.parquet'
    back = pd.read_parquet(path)
    source = pd.read_parquet(folder/f'{label}.parquet', columns=[*STUDENT_COLUMNS, 'sample'])
    expected = source.loc[source['sample'] & source['random_index'].lt(fraction), list(STUDENT_COLUMNS)]
    pd.testing.assert_frame_equal(back, expected.reset_index(drop=True))
    assert path.stat().st_size < 200_000_000
    assert verified_entry(folder/'manifest.json', path)['row_count'] == len(back)
    note = 'real Diffsky pilot' if label == 'B' else 'synthetic Flagship fixture'
    print(f'{path.name}: pandas.read_parquet found {len(back):,} expected rows and {len(back.columns)} columns; {path.stat().st_size:,} bytes; SHA-256 verified ({note})')
PY
````

Exit code 0.

````text
<repository>/data/processed/year1/student_B.parquet: 2,366 science rows, 21 columns, 299,599 bytes
Diffsky is incomplete for a Year 1 sample below approximately z = 0.25.
<repository>/.venv/tmp/synthetic-data/processed/year1/student_A.parquet: 8 science rows, 21 columns, 6,467 bytes
student_B.parquet: pandas.read_parquet found 2,366 expected rows and 21 columns; 299,599 bytes; SHA-256 verified (real Diffsky pilot)
student_A.parquet: pandas.read_parquet found 8 expected rows and 21 columns; 6,467 bytes; SHA-256 verified (synthetic Flagship fixture)
````

#### S13 named student environment

````bash
for candidate in <conda>/envs/umapz/bin/python ~/.conda/envs/umapz/bin/python; do
  if test -x "$candidate"; then printf 'Found student Python: %s\n' "$candidate"; exit 0; fi
done
printf 'No student umapz Python found in the mentor Miniforge or user conda environment directories.\n'
exit 2
````

Exit code 2.

````text
No student umapz Python found in the mentor Miniforge or user conda environment directories.
````

#### S13 student unit checks

````bash
.venv/bin/python -B -m pytest -q --basetemp=.venv/tmp/pytest tests/test_student_sample.py
````

Exit code 0.

````text
.......                                                                  [100%]
7 passed in 0.81s
````

#### S13 commit

````bash
git add -- scripts/make_year1_sample.py tests/test_student_sample.py documents/reproduce_data.md documents/decisions_log.md && git commit -m 'S13: select student science tables and document reproduction'
````

Exit code 0.

````text
[main 030b131] S13: select student science tables and document reproduction
 4 files changed, 305 insertions(+), 1 deletion(-)
 create mode 100644 documents/reproduce_data.md
 create mode 100644 tests/test_student_sample.py
````

#### S13 clean clone setup

````bash
git clone --no-local -- "$PWD" .venv/tmp/manual-clean-check && cd .venv/tmp/manual-clean-check && test -z "$(git status --short)" && git log -1 --oneline && mkdir -p .venv/tmp data && TMPDIR="$PWD/.venv/tmp" <conda>/envs/CosmoConda/bin/python -m venv --system-site-packages .venv
````

Exit code 0.

````text
Cloning into '.venv/tmp/manual-clean-check'...
030b131 S13: select student science tables and document reproduction
````

#### S13 clean clone dependency setup

````bash
cd .venv/tmp/manual-clean-check && TMPDIR="$PWD/.venv/tmp" PIP_CONFIG_FILE=/dev/null PIP_DISABLE_PIP_VERSION_CHECK=1 .venv/bin/python -m pip install --no-cache-dir --index-url https://pypi.org/simple --retries 1 --timeout 12 hdf5plugin==7.1.0 pytest==9.2.0 responses==0.26.3
````

Exit code 0.

````text
Collecting hdf5plugin==7.1.0
  Downloading hdf5plugin-7.1.0-py3-none-macosx_11_0_arm64.whl.metadata (3.2 kB)
Collecting pytest==9.2.0
  Downloading pytest-9.2.0-py3-none-any.whl.metadata (7.9 kB)
Collecting responses==0.26.3
  Downloading responses-0.26.3-py3-none-any.whl.metadata (48 kB)
Requirement already satisfied: h5py>=3.0.0 in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from hdf5plugin==7.1.0) (3.16.0)
Collecting iniconfig>=2 (from pytest==9.2.0)
  Downloading iniconfig-2.3.1-py3-none-any.whl.metadata (2.8 kB)
Requirement already satisfied: packaging>=24 in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from pytest==9.2.0) (26.3)
Collecting pluggy<2,>=1.6 (from pytest==9.2.0)
  Downloading pluggy-1.7.0-py3-none-any.whl.metadata (5.0 kB)
Requirement already satisfied: pygments>=2.15 in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from pytest==9.2.0) (2.21.0)
Requirement already satisfied: requests<3.0,>=2.30.0 in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from responses==0.26.3) (2.34.2)
Requirement already satisfied: urllib3<3.0,>=1.25.10 in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from responses==0.26.3) (2.8.0)
Requirement already satisfied: pyyaml in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from responses==0.26.3) (6.0.3)
Requirement already satisfied: numpy>=1.21.2 in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from h5py>=3.0.0->hdf5plugin==7.1.0) (2.5.4)
Requirement already satisfied: charset_normalizer<4,>=2 in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from requests<3.0,>=2.30.0->responses==0.26.3) (3.5.1)
Requirement already satisfied: idna<4,>=2.5 in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from requests<3.0,>=2.30.0->responses==0.26.3) (3.20)
Requirement already satisfied: certifi>=2023.5.7 in <conda>/envs/CosmoConda/lib/python3.12/site-packages (from requests<3.0,>=2.30.0->responses==0.26.3) (2026.10.23)
Downloading hdf5plugin-7.1.0-py3-none-macosx_11_0_arm64.whl (6.1 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 6.1/6.1 MB 8.5 MB/s eta 0:00:00
Downloading pytest-9.2.0-py3-none-any.whl (411 kB)
Downloading responses-0.26.3-py3-none-any.whl (36 kB)
Downloading iniconfig-2.3.1-py3-none-any.whl (7.6 kB)
Downloading pluggy-1.7.0-py3-none-any.whl (27 kB)
Installing collected packages: pluggy, iniconfig, responses, pytest, hdf5plugin
Successfully installed hdf5plugin-7.1.0 iniconfig-2.3.1 pluggy-1.7.0 pytest-9.2.0 responses-0.26.3
````

#### S13 clean clone manual run

````bash
set -e
flagship_fixture="$PWD/.venv/tmp/synthetic-data/raw/flagship2/mirror_843/flagship.parquet"
cd .venv/tmp/manual-clean-check
export MANIFOLDCLOUD_DATA_ROOT="$PWD/data"
export FLAGSHIP_DATA_PARQUET="$flagship_fixture"
export FLAGSHIP_COUNT_PARQUET="$PWD/.venv/tmp/downloaded-counts.parquet"
TMPDIR="$PWD/.venv/tmp" PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1 .venv/bin/python -m pip install --no-cache-dir --no-deps --no-build-isolation -e .
.venv/bin/python -B scripts/check_data_env.py
.venv/bin/python -B - <<'PY'
import os
from pathlib import Path
import numpy as np
import pandas as pd
from manifoldcloud.flagship import COUNT_CUTS
from manifoldcloud.provenance import atomic_path
fixture = pd.read_parquet(os.environ['FLAGSHIP_DATA_PARQUET'], columns=['lsst_i_el_model3_ext', 'kind'])
mag = -2.5*np.log10(fixture['lsst_i_el_model3_ext'])-48.6
kinds = fixture['kind'].isin([0,1])
counts = {'n_all': len(fixture), 'n_kind_01': int(kinds.sum())}
for cut in COUNT_CUTS:
    key = f'n_i{int(round(cut*10))}'
    counts[key], counts[f'{key}_kind_01'] = (int((mag<cut).sum()), int(((mag<cut) & kinds).sum()))
with atomic_path(Path(os.environ['FLAGSHIP_COUNT_PARQUET'])) as part:
    pd.DataFrame([counts]).to_parquet(part, index=False)
print(f'Synthetic downloaded count row: {counts}')
PY
.venv/bin/python -B scripts/fetch_flagship.py --mode manual --count
.venv/bin/python -B scripts/fetch_flagship.py --mode manual
.venv/bin/python -B scripts/fetch_flagship.py --mode manual --count --input "$FLAGSHIP_COUNT_PARQUET"
.venv/bin/python -B scripts/fetch_flagship.py --mode manual --input "$FLAGSHIP_DATA_PARQUET"
.venv/bin/python -B scripts/harmonise.py --catalogue A
.venv/bin/python -B scripts/make_year1_sample.py --catalogue A
.venv/bin/python -B scripts/make_year1_sample.py --catalogue A --student-only
.venv/bin/python -B - <<'PY'
from pathlib import Path
import manifoldcloud
import pandas as pd
from manifoldcloud.provenance import verified_entry
assert Path(manifoldcloud.__file__).resolve().is_relative_to(Path.cwd())
raw = Path('data/raw/flagship2/mirror_843')
assert pd.read_parquet(raw/'counts.parquet').iloc[0]['n_i265_kind_01'] == len(pd.read_parquet(raw/'flagship.parquet'))
folder = Path('data/processed/year1')
path = folder/'student_A.parquet'
student = pd.read_parquet(path)
assert student.shape == (8, 21) and verified_entry(folder/'manifest.json', path)
print(f'Clean clone retained its own package and wrote {len(student)} synthetic student rows with {len(student.columns)} columns')
PY
test -z "$(git status --short)"
printf 'Clean clone status: no tracked changes or untracked files outside ignored paths\n'
````

Exit code 0.

````text
Obtaining file://<repository>/.venv/tmp/manual-clean-check
  Checking if build backend supports build_editable: started
  Checking if build backend supports build_editable: finished with status 'done'
  Preparing editable metadata (pyproject.toml): started
  Preparing editable metadata (pyproject.toml): finished with status 'done'
Building wheels for collected packages: manifoldcloud
  Building editable for manifoldcloud (pyproject.toml): started
  Building editable for manifoldcloud (pyproject.toml): finished with status 'done'
  Created wheel for manifoldcloud: filename=manifoldcloud-0.1.0-0.editable-py3-none-any.whl size=2824 sha256=b7b3db9d39f229f7b0197a8e1a72d835815157a96287625eb17ced0365d31072
  Stored in directory: <repository>/.venv/tmp/manual-clean-check/.venv/tmp/pip-ephem-wheel-cache-adho_lip/wheels/8b/57/3d/0ea33dd598f7efa3573de9ca375276411a2a572ab671d68211
Successfully built manifoldcloud
Installing collected packages: manifoldcloud
Successfully installed manifoldcloud-0.1.0
numpy 2.5.4
pandas 3.1.1
astropy 8.0.2
pyarrow 26.0.1
h5py 3.16.0
hdf5plugin 7.1.0
fsspec 2026.9.0
requests 2.34.2
pytest 9.2.0
responses 0.26.3
photerr 1.6.0
speclite 0.20
HDF5 filter 32026 available: True
Blosc2 LZ4/bitshuffle round trip: 1024 exact values
Synthetic downloaded count row: {'n_all': 400, 'n_kind_01': 400, 'n_i265': 400, 'n_i265_kind_01': 400, 'n_i255': 284, 'n_i255_kind_01': 284, 'n_i253': 258, 'n_i253_kind_01': 258, 'n_i245': 155, 'n_i245_kind_01': 155, 'n_i241': 103, 'n_i241_kind_01': 103}
Open catalogue 353 in CosmoHub and paste <repository>/.venv/tmp/manual-clean-check/data/raw/flagship2/mirror_843/count_query.sql into Expert Mode.
Submit the query in Parquet format and download the result when it succeeds.
Ingest the file with `python scripts/fetch_flagship.py --mode manual --count --input /path/to/result.parquet`.
Open catalogue 353 in CosmoHub and paste <repository>/.venv/tmp/manual-clean-check/data/raw/flagship2/mirror_843/query.sql into Expert Mode.
Submit the query in Parquet format and download the result when it succeeds.
Ingest the file with `python scripts/fetch_flagship.py --mode manual --input /path/to/result.parquet`.
Saved 1 rows to <repository>/.venv/tmp/manual-clean-check/data/raw/flagship2/mirror_843/counts.parquet
Saved 400 rows to <repository>/.venv/tmp/manual-clean-check/data/raw/flagship2/mirror_843/flagship.parquet
A flagship2_mirror_843.parquet: 400 exact-schema finite rows; 400 flux or disk-axis round trips
A median a_hl at 23.5 < i < 24.5: 0.354789 arcsec
Catalogue A, seed 42: {'rows': 400, 'science_rows': 105, 'control_rows': 103, 'i_error_rows': 25, 'median_i_error': 0.13366679847240448, 'science_true_i_gt_25_5_rows': 0, 'science_true_i_gt_25_5_fraction': 0.0, 'science_true_i_gt_cut_rows': 8, 'science_true_i_gt_cut_fraction': 0.0761904761904762, 'i_limit': 24.1}
Wrote <repository>/.venv/tmp/manual-clean-check/data/processed/year1/A.parquet
Wrote <repository>/.venv/tmp/manual-clean-check/data/processed/year1/summary.json
<repository>/.venv/tmp/manual-clean-check/data/processed/year1/student_A.parquet: 8 science rows, 21 columns, 6,467 bytes
Clean clone retained its own package and wrote 8 synthetic student rows with 21 columns
Clean clone status: no tracked changes or untracked files outside ignored paths
````

#### S13 guide syntax

````bash
.venv/bin/python -B - <<'PY'
from pathlib import Path
import re
import subprocess
source = Path('documents/reproduce_data.md').read_text()
blocks = re.findall(r'```bash\n(.*?)```', source, flags=re.S)
for block in blocks:
    subprocess.run(['bash', '-n'], input=block, text=True, check=True)
snippets = re.findall(r"<<'PY'\n(.*?)\nPY", source, flags=re.S)
for snippet in snippets:
    compile(snippet, 'documents/reproduce_data.md', 'exec')
print(f'{len(blocks)} Bash examples and {len(snippets)} embedded Python checks parsed')
PY
````

Exit code 0.

````text
12 Bash examples and 2 embedded Python checks parsed
````

### Final full test suite and Git status

#### Full offline suite

````bash
.venv/bin/python -B -m pytest --basetemp=.venv/tmp/pytest-final
````

Exit code 0.

````text
============================= test session starts ==============================
platform darwin -- Python 3.12.16, pytest-9.2.0, pluggy-1.7.0
rootdir: <repository>
configfile: pyproject.toml
plugins: platformdirs-4.14.5, anyio-4.16.0
collected 58 items / 2 deselected / 56 selected

tests/test_config.py ..                                                  [  3%]
tests/test_cosmohub.py .........                                         [ 19%]
tests/test_diffsky.py ..                                                 [ 23%]
tests/test_fetch_diffsky.py ..                                           [ 26%]
tests/test_filter_curves.py .....                                        [ 35%]
tests/test_flagship.py ...                                               [ 41%]
tests/test_harmonise.py .....                                            [ 50%]
tests/test_logs.py ....                                                  [ 57%]
tests/test_noise.py ....                                                 [ 64%]
tests/test_provenance.py ..                                              [ 67%]
tests/test_sizes.py ........                                             [ 82%]
tests/test_student_sample.py .......                                     [ 94%]
tests/test_validate.py ...                                               [100%]

======================= 56 passed, 2 deselected in 4.69s =======================
````

#### Git status before creating the report

````bash
git status
````

Exit code 0.

````text
On branch main
Untracked files:
  (use "git add <file>..." to include in what will be committed)
	lectures/
	notebooks/

nothing added to commit but untracked files present (use "git add" to track)
````
