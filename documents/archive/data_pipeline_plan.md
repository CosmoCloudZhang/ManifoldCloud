# ManifoldCloud data pipeline: strategy and development plan

**Status:** approved by the mentor on 25 November 2026 for the steps tagged CODEX, as an unattended overnight run under `documents/codex_overnight_prompt.md`. Steps tagged HUMAN are not approved for Codex.
**Package name:** `manifoldcloud` (confirmed by the mentor, 25 November 2026).
**Intended executor:** Codex, with the steps marked HUMAN run by the mentor.
**Scope:** acquire, harmonise and validate the two mock catalogues, add Rubin Year 1 noise, and hand over analysis-ready tables. Map training and redshift calibration are out of scope.

---

## 0. How to use this document

1. Execute the steps of section 6 in order. Each step states its inputs, actions, outputs and a check.
2. A step is done only when its check passes. If a check fails, stop and report; do not loosen the check.
3. Tags on steps:
   - `CODEX`: can be completed without credentials, large downloads or the external disk.
   - `HUMAN`: needs the mentor (credentials, a licence decision, the external disk, or a long download).
   - `NET`: needs internet access.
4. Hard rules:
   - Never ask for, read, print, store or commit a password or token. Tests use mocked HTTP only.
   - Never commit catalogue data. All data lives under the configurable data root (section 4.2).
   - Change only the files a step lists as outputs. Do not edit anything under `lectures/`.
   - Record every deviation from this plan in `documents/decisions_log.md`.
5. Statements are labelled **verified** (checked against files, source code or papers on the date given) or **assumed** (to be confirmed by the step that names it).

---

## 1. Strategy

### 1.1 Purpose

The project trains an unsupervised colour-space map on catalogue A, calibrates the redshift distribution of each map cell with A's true redshifts, freezes the map, applies it to catalogue B, and compares the predicted redshift distribution with B's truth. The metric is the bias on the mean redshift of each tomographic bin, judged against the LSST Year 1 requirement of 0.002 (1 + z).

This plan delivers the two catalogues on the same footing.

### 1.2 Fixed decisions

| # | Decision | Reason |
|---|---|---|
| D1 | Catalogue A is Euclid Flagship 2 from CosmoHub | Public; has Rubin bands, sizes and true redshifts |
| D2 | Catalogue B is Diffsky `c260710_09_02_2026` alone | Public over HTTPS; intrinsic photometry; fitted to COSMOS2020 |
| D3 | OpenUniverse2024 is set aside | Needs three photometric corrections; its galaxy modelling is older |
| D4 | Depth is LSST Year 1 only: final cut at noisy i < 24.1 | Mentor decision, 25 November 2026 |
| D5 | Photometry is intrinsic: emission lines and internal dust included, no Galactic extinction, no lensing magnification | Diffsky provides exactly this; Flagship has matching columns |
| D6 | Footprint is Diffsky's single patch (34.38 deg^2) and its mirror box in Flagship | Equal shape and area in both catalogues |
| D7 | Pre-selection at noiseless i < 26.5; the science cut is applied after noise | Loses under 0.1% of a Year 1 sample (section 8.3) and keeps Year 10 open |
| D8 | Noise comes from `photerr` (Rubin model, 1 year, extended sources), identical for A and B | Same noise model on both sides |
| D9 | Public data only; readers accept a local path as well as a URL | The student has no NERSC access; the mentor expects to move there later |
| D10 | CosmoHub credentials are supplied by each user at run time and never stored | Mentor requirement |
| D11 | Null-test patches and shear noise are planned but not built now | Sections 7.1 and 7.2 |

### 1.3 What "the same footing" means

| Property | Flagship 2 (A) | Diffsky (B) |
|---|---|---|
| Flux columns | `lsst_{u,g,r,i,z,y}_el_model3_ext` | `lsst_{u,g,r,i,z,y}_unlensed` |
| Unit | erg/cm^2/s/Hz; `mag = -2.5*log10(flux) - 48.6` | AB magnitude |
| Emission lines | Included | Included (**assumed** from the stellar-population library tag `wNE`) |
| Internal dust | Included | Included |
| Galactic extinction | Not included in this variant | Not present in the catalogue |
| Lensing magnification | Not applied to catalogue fluxes | Removed by using the `_unlensed` columns |
| Position | `ra_gal`, `dec_gal` (unlensed) | `ra`, `dec` (unlensed) |
| Redshift | `true_redshift_gal`, `observed_redshift_gal` | `redshift_true`, `redshift_obs` |

Evidence for the Flagship side:
- The catalogue page (read 15 November 2026) lists three flux variants per band: plain, `_el_model3_ext` (adds emission lines) and `_el_model3_ext_odonnell_ext` (adds Milky Way extinction). **Verified** on that date; to be re-verified by step S08.
- The Flagship paper (Castander et al., arXiv:2405.13495) states that catalogue fluxes are intrinsic, and describes magnified magnitudes and magnified positions as separate quantities derived from the convergence. **Verified** in the paper, 25 November 2026.

Evidence for the Diffsky side (all **verified** by reading the files, 24 to 25 November 2026):
- `lsst_i_unlensed - lsst_i` equals `2.5*log10(magnification)` to rounding precision in 339,890 galaxies.
- The `magnification` column is never below 1 and is not reproduced from `kappa`, `shear1`, `shear2`. Do not use it. The `_unlensed` magnitudes are unaffected.
- There is no Galactic extinction column.

Known remaining mismatch, to be reported and not corrected: Diffsky's Rubin filter curves are identical to the `lsst2023` set in `speclite`. Flagship's filter version is unknown.

---

## 2. Verified facts about the sources

### 2.1 Diffsky `c260710_09_02_2026`

Access (**verified** 24 November 2026):
- Base URL: `https://g-45a93.fd635.8443.data.globus.org/Diffsky/synthetic_galaxies/c260710_09_02_2026/`
- Plain HTTPS, no credentials, byte-range requests supported. There is no directory listing.
- At NERSC the same files are at `/global/cfs/cdirs/hacc/OpenCosmo/LastJourney/synthetic_galaxies/c260710_09_02_2026/`.
- Licence: none found. Redistribution is a mentor decision (section 9).

Files:
- 67 galaxy files named `lc_cores-<step>.diffsky_gals.hdf5`, 116,531,444,695 bytes in total.
- Steps: 97, 100, 102, 105, 107, 110, 113, 116, 119, 121, 124, 127, 131, 134, 137, 141, 144, 148, 151, 155, 159, 163, 167, 171, 176, 180, 184, 189, 194, 198, 203, 208, 213, 219, 224, 230, 235, 241, 247, 253, 259, 266, 272, 279, 286, 293, 300, 307, 315, 323, 331, 338, 347, 355, 365, 373, 382, 392, 401, 411, 421, 432, 442, 453, 464, 475, 487.
- Each file is one redshift shell. The attribute `header/lightcone@z_range` is authoritative. Step 487 is 0 to 0.0245, step 300 is 0.6184 to 0.6557, step 97 reaches z = 4.
- Support files in the same folder: `ecdfs_cfg.yaml`, `lc_cores-decomposition.txt`, `diffsky_c260710_09_02_2026_transmission_curves.hdf5`, `..._ssp_data.hdf5`, `..._param_collection.hdf5`, `..._t_table.hdf5`.

File layout:
- Groups `cores/data` (galaxies in simulated halos) and `synth_cores/data` (added low-mass galaxies), each with the same 327 columns, plus `header`.
- Every column is a 1-d dataset compressed with the Blosc2 HDF5 filter (id 32026, LZ4 with bitshuffle). Plain `h5py` reads names, shapes and attributes but not values. `hdf5plugin` is needed.
- Rows are not grouped by sky patch; here there is only one patch, `lc_patch == 843`.
- Cosmology in the header: h = 0.6766, Omega_m = 0.3096446816, flat.

Footprint (**verified** from `lc_cores-decomposition.txt` and from the data):
- Patch 843 in the table: RA 46.66667 to 53.33333, Dec -28.90335 to -23.16209, 34.3774 deg^2.
- The galaxies sit 180 degrees away in RA: RA 226.66667 to 233.33333, same declination. Use the data, not the table, for RA.

Sizes (**verified** in the Diffsky source at commit `b9033d0bf`, which built this catalogue):
- `alpha_*` is the projected semi-major axis and `beta_*` the semi-minor axis, in kpc. The descriptions stored in the file have them swapped.
- `r50_disk_2d = 0.765 * alpha_disk` and `r50_bulge_2d = 0.765 * alpha_bulge`. So the half-light semi-major axis is `r50_*_2d` and the semi-minor axis is `r50_*_2d * beta_*/alpha_*`.
- `ellipticity_* = 1 - beta_*/alpha_*`.
- `bulge_to_total` is a mass ratio, not a flux ratio.
- **Assumed:** the kpc are physical, not comoving. Step S10 checks this against Flagship's angular sizes.

Depth (**verified** in three shells; a floor-mass halo is one of 10^10.5 to 10^10.6 solar masses):

| Redshift | Counts per 0.5 mag peak at | Floor-mass halos brighter than i = 24.1 |
|---|---|---|
| 0.10 to 0.13 | i = 22.0 to 22.5 | 63% |
| 0.24 to 0.27 | i = 24.5 to 25.0 | 1.4% |
| 0.62 to 0.66 | i = 26.5 to 27.0 | 0% |

So a Year 1 sample is complete only above about z = 0.25. This is a property of the catalogue and must be stated in every result.

Other properties:
- The model was fitted to COSMOS2020 grizyJHK at 0.4 < z < 2.5 and i < 25.5. The u band was not used. (**Verified** in the Diffsky repository.)
- `p_merge > 0.5` marks satellites merged into their central. In the sampled shell all of them are fainter than i = 27.5.
- The portal calls these catalogues "in-development".

### 2.2 Flagship 2

Access:
- CosmoHub, catalogue 353, table `euclid_fs2_mock_dr_v1_1_phz`, release 1.1 of 15 October 2025. A free account is needed.
- Footprint: 145 < RA < 235, 0 < Dec < 90. Avoid 150 < RA < 155, 5 < Dec < 10.
- Licence: CC BY-NC 3.0 IGO. Cite Castander, Fosalba et al. and CosmoHub.
- An accepted example query is in `lectures/lecture04/build/flagship2_patch_query.sql`. Follow its syntax.

Columns (**verified** on the catalogue page 15 November 2026; names to be re-verified by step S08):
- Identity: `galaxy_id`, `halo_id`, `kind` (0 central, 1 satellite, 2 QSO, 3 high redshift), `random_index`.
- Morphology: `dominant_shape` (0 bulge only, 1 bulge plus disc), `bulge_fraction`, `bulge_r50`, `disk_r50` (arcsec), `bulge_axis_ratio`, `disk_axis_ratio`, `bulge_nsersic`, `inclination_angle`.
- Physical: `log_stellar_mass` (Msun/h^2), `log_sfr`, `color_kind`. Cosmology h = 0.67.
- **Assumed:** `*_r50` is the half-light radius along the major axis, so semi-minor = axis ratio times r50. The paper says the disc half-light radius is 1.678 scale lengths and the axis ratio is b/a.
- **Assumed:** `bulge_fraction` is a flux fraction.

Measured in the box 180 <= RA < 190, 10 <= Dec < 20 (96.5 deg^2) on 15 November 2026:

| Selection | Rows | Per deg^2 |
|---|---|---|
| All rows | 88,956,824 | 921,800 |
| i < 25.5 | 21,469,243 | 222,500 |
| i < 25.3 | 18,597,791 | 192,700 |
| i < 24.5 | 10,293,370 | 106,700 |

All 399 columns take 1,594 bytes per row, about 4 bytes per column.

---

## 3. Column selection

### 3.1 Flagship 2 query

Box (the mirror of Diffsky's patch: same RA, declination sign flipped):

```
226.66667 <= ra_gal < 233.33333
 23.16209 <= dec_gal < 28.90335
```

Columns (26):

| Group | Columns |
|---|---|
| Identity | `galaxy_id`, `halo_id`, `kind`, `random_index` |
| Position | `ra_gal`, `dec_gal` |
| Redshift | `true_redshift_gal`, `observed_redshift_gal` |
| Photometry | `lsst_u_el_model3_ext`, `lsst_g_el_model3_ext`, `lsst_r_el_model3_ext`, `lsst_i_el_model3_ext`, `lsst_z_el_model3_ext`, `lsst_y_el_model3_ext` |
| Sizes | `dominant_shape`, `bulge_fraction`, `bulge_r50`, `disk_r50`, `bulge_axis_ratio`, `disk_axis_ratio`, `bulge_nsersic`, `inclination_angle` |
| Physical | `log_stellar_mass`, `log_sfr`, `color_kind` |
| Check | `euclid_nisp_h` |

Row filter:

```sql
kind IN (0, 1)
AND lsst_i_el_model3_ext > 0
AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 26.5
```

Deliberately not selected:
- `*_el_model3_ext_odonnell_ext`: contains Galactic extinction.
- Plain `lsst_*`: no emission lines.
- `*_error`, `*_error_realization`: the catalogue's own noise, at Euclid depth.
- Magnified positions and lensing columns: not needed for intrinsic photometry.

Expected size (**assumed**, extrapolated from the i < 25.5 count with a slope of 0.32 per mag): about 16 million rows and 1.7 GB.

### 3.2 Diffsky columns

Read from both `cores/data` and `synth_cores/data` (27 columns):

| Group | Columns |
|---|---|
| Identity | `gal_id`, `lc_patch`, `central` |
| Position | `ra`, `dec` |
| Redshift | `redshift_true`, `redshift_obs` |
| Photometry | `lsst_u_unlensed`, `lsst_g_unlensed`, `lsst_r_unlensed`, `lsst_i_unlensed`, `lsst_z_unlensed`, `lsst_y_unlensed` |
| Bulge flux share | `lsst_i_bulge_unlensed`, `lsst_i_disk_unlensed`, `lsst_i_knots_unlensed` |
| Sizes | `r50_disk_2d`, `r50_bulge_2d`, `alpha_disk`, `beta_disk`, `alpha_bulge`, `beta_bulge` |
| Labels | `p_merge`, `bulge_to_total`, `logsm_obs`, `logssfr_obs`, `logmp_obs` |

Add a boolean `is_synthetic` from the group name and an integer `step` from the file name.

Row filter, applied locally after reading: `lsst_i_unlensed < 26.5`. Record the row count before and after for every shell.

Transfer (**assumed**): about 27/327 of 116.5 GB, that is 9.6 GB.

### 3.3 Harmonised schema

One Parquet dataset per catalogue with these columns:

| Column | Type | Flagship source | Diffsky source |
|---|---|---|---|
| `gal_id` | int64 | `galaxy_id` | `gal_id` |
| `ra`, `dec` | float64, deg | `ra_gal`, `dec_gal` | `ra`, `dec` |
| `z_true`, `z_obs` | float32 | `true_redshift_gal`, `observed_redshift_gal` | `redshift_true`, `redshift_obs` |
| `mag_u` … `mag_y` | float32, AB | `-2.5*log10(flux) - 48.6` | `lsst_*_unlensed` |
| `a_disk`, `b_disk` | float32, arcsec | `disk_r50`, `disk_r50*disk_axis_ratio` | `r50_disk_2d` and `r50_disk_2d*beta_disk/alpha_disk`, converted |
| `a_bulge`, `b_bulge` | float32, arcsec | `bulge_r50`, `bulge_r50*bulge_axis_ratio` | same with bulge columns |
| `bulge_frac` | float32 | `bulge_fraction` | i-band flux share of the bulge; knots count as disc |
| `a_hl`, `b_hl` | float32, arcsec | combined, see below | combined, see below |
| `log_mstar` | float32, Msun | `log_stellar_mass - 2*log10(0.67)` | `logsm_obs` |
| `is_central` | bool | `kind == 0` | `central == 1` |
| `is_synthetic` | bool | False | from group |
| `p_merge` | float32 | NaN | `p_merge` |
| `random_index` | float32 | `random_index` | deterministic hash of `gal_id` mapped to [0, 1) |

Rules:
- Diffsky kpc to arcsec: `arcsec = kpc / D_A(z_true) * 206264.806`, with `D_A` from `astropy.cosmology.FlatLambdaCDM(H0=67.66, Om0=0.3096446816)`.
- Combined size for the noise model: `a_hl = sqrt(f*a_bulge^2 + (1-f)*a_disk^2)` and the same for `b_hl`, with `f = bulge_frac`. For Flagship rows with `dominant_shape == 0`, use the bulge axes alone. The rule name is stored in the file metadata as `size_rule = "flux_weighted_quadrature"`.
- This rule applies the additivity of second moments (Chang et al. 2013, equation A6) to half-light axes. It is an approximation chosen for the photometric noise. The exact Chang et al. size is planned in section 7.2.

---

## 4. Repository layout and conventions

### 4.1 Layout to create

```
ManifoldCloud/
├── .gitignore
├── pyproject.toml
├── environment.yml                  (edit: add packages, step S01)
├── config/
│   ├── default.toml                 tracked: sources, boxes, columns, cuts, seeds
│   └── local.example.toml           tracked template; local.toml is git-ignored
├── manifoldcloud/
│   ├── __init__.py
│   ├── config.py                    load and merge TOML, resolve data root
│   ├── logs.py                      logging setup with secret redaction
│   ├── provenance.py                manifests and checksums
│   ├── diffsky.py                   reader for a URL or a local path
│   ├── flagship.py                  SQL builder
│   ├── cosmohub.py                  client: sign in, check, submit, poll, download
│   ├── harmonise.py                 both catalogues to the common schema
│   ├── sizes.py                     size conversions and combination rules
│   ├── noise.py                     photerr wrapper and selection
│   └── validate.py                  checks and summary numbers
├── scripts/
│   ├── check_data_env.py
│   ├── fetch_diffsky.py
│   ├── make_flagship_query.py
│   ├── fetch_flagship.py
│   ├── harmonise.py
│   ├── validate.py
│   ├── make_year1_sample.py
│   └── queries/                     generated SQL, tracked
├── tests/
└── documents/
    ├── data_pipeline_plan.md        this document
    ├── decisions_log.md
    └── reproduce_data.md            instructions for the student
```

### 4.2 Data root

Resolution order: `--data-root` argument, then environment variable `MANIFOLDCLOUD_DATA_ROOT`, then `data_root` in `config/local.toml`. There is no default. If none is set, or the directory does not exist, exit with a message naming the three ways to set it.

```
<data_root>/
├── raw/diffsky/c260710_09_02_2026/      shell_<step>.parquet, manifest.json
├── raw/flagship2/mirror_843/            result file(s), query.sql, catalog_metadata.json, manifest.json
├── interim/harmonised/                  flagship2_mirror_843.parquet, diffsky_843/ (one file per shell)
└── processed/year1/                     A and B samples with noise, student subset
```

Write every file to a `.part` name and rename on success. Make raw files read-only after their manifest is written.

### 4.3 Conventions

- Names: the Python package and its import name are `manifoldcloud`, matching the project folder. The data-root variable is `MANIFOLDCLOUD_DATA_ROOT`. Do not shorten the package to `manifold`: that name is taken on the Python package index and collides in user code with `from sklearn import manifold`. The lecture material keeps its own name for the student environment and is not renamed.
- Python 3.12. Only conda-forge packages, plus `photerr` from PyPI as already done.
- Plain functions and short scripts with a module docstring, in the style of `lectures/lecture04/output/check_environment.py`.
- Every random draw uses a seed from `config/default.toml`.
- Every output file has a manifest entry: source, command line, package versions, row count, SHA-256, UTC time. Never the user's e-mail or any token.
- Tests run with `pytest`. Tests that need the internet are marked `network` and skipped by default.
- Git: the project is not yet a repository. Step S00 initialises one only if the mentor agrees.

---

## 5. CosmoHub credentials and acquisition

### 5.1 What the service offers

CosmoHub publishes no API documentation. Its web application calls a JSON API at `https://api.cosmohub.pic.es`. The following was read from the application's public JavaScript on 25 November 2026. It is **unofficial and may change**.

| Purpose | Call |
|---|---|
| Sign in | `GET /user` with HTTP Basic authentication (e-mail and password). The response header `X-Token` carries a session token |
| Later calls | Header `Authorization: Token <token>`. A new `X-Token` may arrive on any response and replaces the old one |
| Catalogue metadata | `GET /catalogs/353` |
| Syntax check | `GET /catalogs/syntax?sql=<url-encoded SQL>` |
| Submit | `POST /queries` with JSON `{"sql": "...", "format": "parquet"}` |
| List and status | `GET /queries`; each entry has `id`, `sql`, `status`, `format`, `size`, `ts_submitted`, `ts_started`, `ts_finished`, `download_results` |
| Status values | `PENDING`, `PROCESSING`, `SUCCEEDED`, `FAILED`, `CANCELLED` |
| Cancel | `POST /queries/<id>/cancel` |
| Result | The URL in `download_results` |

Not verified: the response bodies, whether the result URL needs the token header, and whether scripted use is acceptable to CosmoHub. The mentor confirms the last point before the first live run (section 9).

### 5.2 Design

Two modes behind one command, `scripts/fetch_flagship.py`:

- `--mode manual` (always works): write the SQL, print step-by-step instructions for the web page, then ingest the file the user downloaded.
- `--mode api`: sign in, check syntax, submit, poll, download.

Credential handling in `--mode api`:

1. Read the e-mail from `COSMOHUB_EMAIL`, else prompt with `input()`.
2. Read the password from `COSMOHUB_PASSWORD`, else prompt with `getpass.getpass()`, which does not echo.
3. Exchange them once for a token, then delete the password variable. Keep only the token, in memory.
4. Optional, off by default: `--keyring` stores and reads the password in the operating system keychain through the `keyring` package.

Rules the code must enforce:

- Credentials are never accepted as command-line arguments, because those appear in shell history and process lists.
- Nothing secret is written to disk: no token cache, no `.env` support, no credentials in config files or manifests.
- Log records pass through a filter that removes `Authorization` and `X-Token` values and the password string. HTTP debug logging stays off.
- Exceptions raised by the client carry the status code and a short message, never request headers.
- Credentials are sent only to `https://api.cosmohub.pic.es`, only in headers, never in a URL. Redirects to another host drop the headers.
- `.gitignore` covers `.env*` and `config/local.toml`. A pre-commit secret scanner is added if the mentor wants one.

### 5.3 What Codex must not do

Codex writes and tests this module with mocked HTTP. It never runs `--mode api`, never asks for credentials, and never signs in. The live run is step S09, by the mentor.

---

## 6. Development steps

### S00 Repository scaffolding — CODEX, with one HUMAN decision

- **Inputs:** project root as it is; the mentor's answer on `git init`.
- **Actions:**
  1. If approved, run `git init` and make no commit yet.
  2. Write `.gitignore`: `.DS_Store`, `__pycache__/`, `.ipynb_checkpoints/`, `.pytest_cache/`, `*.part`, `.env*`, `config/local.toml`, `data/`, `*.parquet`, `*.hdf5`, `*.fits`.
  3. Write `pyproject.toml` declaring the package `manifoldcloud`, and create the empty package, `tests/`, `documents/decisions_log.md`.
- **Outputs:** the files above.
- **Check:** `pip install -e .` succeeds; `python -c "import manifoldcloud"` succeeds; `git check-ignore config/local.toml .env x.parquet` prints all three.

### S01 Environment — CODEX, NET

- **Inputs:** `environment.yml`.
- **Actions:** add `hdf5plugin`, `requests`, `pytest`, `responses` to the mentor layer, with one-line comments. Leave the student block unchanged. Write `scripts/check_data_env.py`.
- **Outputs:** edited `environment.yml`; `scripts/check_data_env.py`.
- **Check:** after `conda env update`, the script prints package versions, confirms `h5py.h5z.filter_avail(32026)` is true, and round-trips a Blosc2-compressed dataset in a temporary file.
- **If the check fails:** see appendix A. Record the outcome in the decisions log.

### S02 Configuration and paths — CODEX

- **Inputs:** sections 3 and 4 of this document.
- **Actions:** write `config/default.toml` (sources, box, column lists, cuts, seeds), `config/local.example.toml`, and `manifoldcloud/config.py`.
- **Outputs:** those files; `tests/test_config.py`.
- **Check:** tests cover the three ways to set the data root, their priority, and the error when none is set. `python -c "from manifoldcloud.config import load; print(load().flagship.box)"` prints the box of section 3.1.

### S03 Logging and provenance — CODEX

- **Inputs:** section 4.3 and section 5.2.
- **Actions:** write `manifoldcloud/logs.py` with the redaction filter and `manifoldcloud/provenance.py` with manifest and checksum helpers.
- **Outputs:** the two modules; `tests/test_logs.py`, `tests/test_provenance.py`.
- **Check:** a test logs a message containing a fake token and a fake password at every level and asserts that neither appears in the captured output. A test writes a file through the `.part` helper and verifies its SHA-256 in the manifest.

### S04 Diffsky reader — CODEX, with one optional NET test

- **Inputs:** section 2.1; S01 passed.
- **Actions:** write `manifoldcloud/diffsky.py`:
  - `open_shell(location, step)` accepts a base URL or a local directory.
  - `read_columns(file, columns)` returns `cores` then `synth_cores` rows with `is_synthetic`.
  - `shell_info(file)` returns the redshift range, row counts and catalogue name from the header.
  - Remote files are opened through `fsspec` with byte-range reads; never download a whole file.
- **Outputs:** the module; `tests/test_diffsky.py` with a synthetic two-group Blosc2 fixture built in the test.
- **Check (offline):** the fixture round-trips, column order is preserved, and a missing column raises a clear error.
- **Check (network, optional):** for step 487: catalogue name `c260710_09_02_2026`; 697 `cores` rows and 183 `synth_cores` rows; 327 columns in each group; all `lc_patch == 843`; `ra` between 226.6 and 233.4; `kappa` identically zero. For step 300: reading `lsst_i_unlensed` and `redshift_true` transfers less than 30 MB of the 730 MB file.

### S05 Diffsky fetch — CODEX writes, HUMAN runs, NET

- **Inputs:** S04; the column list of section 3.2; the data root on the external disk.
- **Actions:** write `scripts/fetch_diffsky.py`:
  - Loops over the 67 steps, reads the 27 columns, applies `lsst_i_unlensed < 26.5`, writes `shell_<step>.parquet`.
  - Resumable: skips shells whose manifest entry and checksum are valid.
  - At most 4 concurrent connections, retries with backoff, a generic User-Agent.
  - `--steps 487,300` for a pilot; `--dry-run` prints the plan and total bytes from HEAD requests.
- **Outputs:** 67 Parquet files and `manifest.json` under `raw/diffsky/c260710_09_02_2026/`.
- **Check (pilot, steps 487, 442, 392, 300):** row counts before the cut are 880, 14,724, 51,476 and 339,890; synthetic rows are 183, 11,362, 40,019 and 280,356. In step 300 there are 124,057 rows with `lsst_i_unlensed < 25.3` and `p_merge < 0.5`.
- **Check (full run):** 67 files; every manifest checksum verifies; the sum of HEAD sizes equals 116,531,444,695 bytes; no shell has zero rows after the cut except possibly the highest redshifts.
- **Performance gate:** the pilot must exceed 2 MB/s. A first test managed only 0.23 MB/s with small sequential requests. If the gate fails, fetch each column's chunk ranges in coalesced requests. If it still fails, the mentor may transfer the whole files with Globus.

### S06 Flagship query builder — CODEX

- **Inputs:** section 3.1; `lectures/lecture04/build/flagship2_patch_query.sql` for syntax.
- **Actions:** write `manifoldcloud/flagship.py` and `scripts/make_flagship_query.py`. The script writes `scripts/queries/flagship_mirror_843.sql` and `scripts/queries/flagship_mirror_843_count.sql`. The builder takes a list of boxes, so that null-test boxes can be added later without code changes.
- **Outputs:** the module, the script, the two SQL files, `tests/test_flagship.py`.
- **Check:** the generated SQL matches a golden file byte for byte; the data query contains exactly the 26 columns and no column name containing `odonnell`, `error` or `mag_gal`.
- **Count query content:** `COUNT(*)` and counts at i < 26.5, 25.5, 25.3, 24.5 and 24.1 in the box, with and without `kind IN (0, 1)`.

### S07 CosmoHub client — CODEX

- **Inputs:** section 5.
- **Actions:** write `manifoldcloud/cosmohub.py` and `scripts/fetch_flagship.py` with `--mode manual|api`, `--check-only`, `--count`, `--submit`, `--resume <id>`.
  - `--check-only` signs in, fetches `GET /catalogs/353`, saves it as `catalog_metadata.json`, and verifies that every requested column exists.
- **Outputs:** the module and script; `tests/test_cosmohub.py` using `responses`.
- **Check:** mocked tests cover: sign-in success and failure; token rotation from `X-Token`; a submit, poll and download cycle; `FAILED` and `CANCELLED` endpoints; a redirect to another host that must not receive the token. One test runs the whole flow with a known fake password and asserts it is absent from logs, exception text, standard output and every written file.

### S08 Verify Flagship columns — HUMAN, NET

- **Inputs:** S07; the mentor's CosmoHub account.
- **Actions:** run `python scripts/fetch_flagship.py --mode api --check-only`.
- **Outputs:** `raw/flagship2/mirror_843/catalog_metadata.json`.
- **Check:** all 26 columns are found. The mentor reads the stored descriptions and confirms the three **assumed** points of section 2.2: the flux variants, the meaning of `*_r50`, and the meaning of `bulge_fraction`. Any correction goes to the decisions log and to `config/default.toml`.
- **Fallback:** if the API has changed, read the column list on the catalogue page and use `--mode manual` from here on.

### S09 Flagship acquisition — HUMAN, NET

- **Inputs:** S08 passed; the data root on the external disk; confirmation that scripted use is acceptable (section 9).
- **Actions:** run the count query, record its numbers, then run the data query in Parquet format.
- **Outputs:** result file(s), `query.sql`, `manifest.json` under `raw/flagship2/mirror_843/`.
- **Check:**
  - Row count equals the count query's value at i < 26.5 with `kind IN (0, 1)`.
  - `ra_gal` and `dec_gal` lie inside the box.
  - The faintest i magnitude is below 26.5.
  - Density at i < 25.3 is within 10% of 192,700 per deg^2 over 34.3774 deg^2.

### S10 Harmonise — CODEX

- **Inputs:** raw outputs of S05 and S09; section 3.3.
- **Actions:** write `manifoldcloud/sizes.py`, `manifoldcloud/harmonise.py`, `scripts/harmonise.py`. Process one Diffsky shell at a time.
- **Outputs:** `interim/harmonised/flagship2_mirror_843.parquet` and `interim/harmonised/diffsky_843/shell_<step>.parquet`; unit tests.
- **Check:**
  - Both outputs have exactly the schema of section 3.3.
  - No NaN or infinity in `mag_*`, `z_true`, `a_hl`, `b_hl`; `b_hl <= a_hl` everywhere.
  - Flagship round trip: `10**(-0.4*(mag_i + 48.6))` reproduces the flux to float precision.
  - Diffsky: `a_disk/b_disk == alpha_disk/beta_disk`.
  - Size sanity: the median `a_hl` at 23.5 < i < 24.5 lies between 0.1 and 1.0 arcsec in both catalogues, and the two medians differ by less than a factor of 2. A larger difference points to the physical-versus-comoving assumption.

### S11 Validation report — CODEX

- **Inputs:** harmonised tables.
- **Actions:** write `manifoldcloud/validate.py` and `scripts/validate.py`, producing figures in `figures/data_validation/` and numbers in `report/data_validation_summary.json`.
- **Outputs:** the figures and the JSON file.
- **Check:** the report contains, for both catalogues:
  1. Number counts per deg^2 in 0.5 mag bins, and totals at i < 24.1 and i < 25.3.
  2. Redshift distributions at i < 24.1.
  3. Median u-g, g-r, r-i, i-z, z-y against redshift in bins of 0.1.
  4. Median `a_hl` against i magnitude.
  5. For Diffsky, the table of section 2.1 reproduced within 2 percentage points.
  6. A comparison of the Diffsky filter curves with `speclite` `lsst2023`, expected identical.

### S12 Year 1 noise and selection — CODEX

- **Inputs:** harmonised tables; seeds from the configuration.
- **Actions:** write `manifoldcloud/noise.py` and `scripts/make_year1_sample.py`.
  - `photerr.LsstErrorModel(nYrObs=1, extendedType="auto", majorCol="a_hl", minorCol="b_hl", sigLim=0, ndFlag=np.nan, decorrelate=True)`, with the band names mapped to `mag_*`. Confirm the argument names against the installed `photerr` 1.6.
  - Output `mag_*_obs` and `mag_*_err` beside the noiseless magnitudes.
  - Science sample: finite `mag_i_obs < 24.1`. Control sample: noiseless `mag_i < 24.1`.
- **Outputs:** `processed/year1/A.parquet`, `processed/year1/B.parquet`, each with a `sample` flag, and a summary JSON.
- **Check:**
  - Re-running gives identical files.
  - The median i-band error at 24.0 < `mag_i` < 24.2 is between 0.10 and 0.25 mag in both catalogues. A synthetic test gave 0.17.
  - The share of the science sample with noiseless `mag_i > 25.5` is below 0.5% in both. The synthetic test gave about 0.1%. A larger share means a tail of large sizes; stop and report.
  - Report the share with noiseless `mag_i > 24.1`. The synthetic test gave 8% to 10%.

### S13 Hand-over — CODEX writes, HUMAN checks

- **Inputs:** S12 outputs.
- **Actions:** make the student subset (science sample, about 20 columns, `random_index` below a configured fraction) and write `documents/reproduce_data.md`.
- **Outputs:** `processed/year1/student_A.parquet`, `processed/year1/student_B.parquet`, the instructions.
- **Check:** each student file is under 200 MB and opens with `pandas.read_parquet` in the student environment of `lectures/lecture04/output/environment.yml`. The instructions were followed once from a clean clone with `--mode manual`.

---

## 7. Later analyses, planned but not built now

### 7.1 Null-test patches

**What they are.** Extra Flagship boxes with the same shape as the mirror box, in the same declination band. Thirteen fit between RA 146.667 and 233.333 in steps of 6.6667 degrees.

**What they test.** The frozen map, trained and calibrated on one Flagship box, is applied to other Flagship boxes. The galaxy model is identical, so any difference in the mean redshift is noise: sample variance from large-scale structure plus shot noise. The scatter among the boxes is the error bar for the A to B result.

**Why this matters.** Without it, a measured bias in B cannot be called significant or insignificant. A linear-theory estimate puts the noise at 0.0006 to 0.0024 for 34 deg^2, against a Year 1 requirement of 0.0028 to 0.0044, but that rests on an assumed share of redshift scatter inside map cells.

**Whether it is needed now.** Not for acquisition, harmonisation or the first A to B number. It is needed before any statement about the size of the bias. With K boxes the scatter is known to about 1/sqrt(2(K-1)): 41% for four boxes, 27% for eight.

**How to add it.** Add boxes to `config/default.toml` and re-run S06 and S09. Each box is about 1.7 GB with the 26 columns. No code changes are required.

**A cheaper first look.** Split the mirror box in two and transfer between the halves. This overestimates the noise, because each half is 17 deg^2.

### 7.2 Shear noise following Chang et al. (2013)

Source: Chang et al. 2013, MNRAS 434, 2121, arXiv:1305.0793. Equation numbers refer to that paper.

**Single effective size from bulge and disc (appendix A1).**
- Second-moment radius of each component from its half-light radius: `r_sec,b = 4.66 r_h,b` for a de Vaucouleurs bulge and `r_sec,d = 1.46 r_h,d` for an exponential disc (A3, A4).
- Second moments add, weighted by flux: `r_gal = sqrt(f_b (4.66 r_h,b)^2 + (1 - f_b) (1.46 r_h,d)^2)`, where `f_b` is the bulge flux fraction (A6).

**From size and flux to shear noise.**
1. PSF size: `r_PSF = sqrt(2) * FWHM / (2 sqrt(2 ln 2))` (A7).
2. Effective size: `R = r_gal^2 / r_PSF^2` (15).
3. Aperture: `r_ap = 1.64 sqrt(r_gal^2 + r_PSF^2)` (A8, A10). Source counts `S` are 90% of the total; background counts `B` are the sky rate times the aperture area.
4. Signal-to-noise ratio: `nu = S / sqrt(S + B)` (14).
5. Measurement noise per exposure: `sigma_m = (a / nu) [1 + (b / R)^c]` with `(a, b, c) = (1.58, 5.03, 0.39)` (13).
6. Combining exposures: joint fit `sigma_m,joint = [sum_j 1/sigma_m,j^2]^(-1/2)` (16), or the co-add form with summed counts and mean squared PSF size (17, 18).
7. Selection: `sigma_m < k sigma_SN` with `sigma_SN = 0.26`; `k = 1` fiducial, 0.5 conservative, 2 optimistic (19).
8. Effective number density: `n_eff = (1/Omega) sum_i sigma_SN^2 / (sigma_SN^2 + sigma_m,i^2)` (9). The summand is each galaxy's lensing weight.

**Use in this project.** The weights define a lensing-weighted redshift distribution. The A to B comparison is then repeated with weights, which is the quantity cosmic shear depends on.

**Inputs already in the harmonised tables.** `a_disk`, `b_disk`, `a_bulge`, `b_bulge`, `bulge_frac`, the r and i magnitudes. Observing conditions (seeing, sky brightness, visits) can be taken from the `photerr` Rubin parameters for consistency with S12.

**Points to settle when this is built.**
- Chang et al. assume circular profiles. Use the circularised radius `sqrt(a*b)` for each component, and record the choice.
- The factor 4.66 comes from the extended wings of an untruncated de Vaucouleurs profile. It makes bulge-dominated galaxies very large. Test the sensitivity.
- Flagship's one-component galaxies have a free Sérsic index `bulge_nsersic`. The factor 4.66 holds only for index 4; compute the factor numerically for other indices.
- Diffsky's `bulge_to_total` is a mass ratio. Use the flux share from the component magnitudes, as in section 3.3.
- The coefficients were fitted for one shape algorithm on single 15-second exposures. Outside that range the formula is an extrapolation.

### 7.3 Year 10

Change the final cut to 25.3 and `nYrObs` to 10. The i < 26.5 pre-selection already allows it. Diffsky is incomplete at i < 25.3 at z of 0.26 and complete by z of 0.64; where the change happens was not measured. An area of 34 deg^2 is marginal against the Year 10 requirement.

### 7.4 Move to NERSC

- Set the Diffsky location to the NERSC directory; the reader needs no change.
- The natural larger catalogue there is `lsst_dp2_10_22_2026` (805.72 deg^2, documented complete to i < 26.5, fitted with the u band). Its column names and build may differ; re-run S04's checks first.
- Keep catalogues that are not public out of the student's repository and results.

### 7.5 OpenUniverse2024

Set aside. If revived, it needs a zero-point from the Rubin throughput files, de-reddening with `MW_av`, and division by the magnification.

---

## 8. Reference numbers and assumptions

### 8.1 Open items

| Item | Settled by |
|---|---|
| Flagship column names and the three assumed meanings | S08 |
| Flagship row count at i < 26.5 | S09 count query |
| Whether CosmoHub accepts scripted use | Mentor, before S09 |
| Whether the result URL needs the token header | S09, first run |
| Diffsky sizes in physical kpc | S10 size check |
| Flagship's Rubin filter curves | Optional: the mentor downloads `fs2_1_10_vad.zip` (1.3 MB) from the catalogue page |
| Download speed for the Diffsky columns | S05 pilot |
| Whether `hdf5plugin` works with the installed HDF5 | S01 |

### 8.2 Volumes

| Item | Size |
|---|---|
| Diffsky transfer, 27 columns | about 9.6 GB |
| Diffsky stored after the cut | a few GB (**assumed**) |
| Flagship mirror box, 26 columns | about 1.7 GB |
| Harmonised and Year 1 tables | under 5 GB |
| Each extra null-test box | about 1.7 GB |

The laptop has 16 GB of memory. Process Diffsky one shell at a time and never load a whole catalogue.

### 8.3 Margin of the pre-selection

From a synthetic test with `photerr` and sizes that shrink with magnitude (median half-light radius 0.31 arcsec at i = 25): for a cut at noisy i < 24.1, a pre-selection 1.5 mag fainter loses 0.07% to 0.12% of the sample, and one 2.0 mag fainter loses 0.02% to 0.07%. The pre-selection at 26.5 is 2.4 mag fainter. If sizes did not shrink with magnitude, the loss would not converge; S12's check guards against this.

---

## 9. Decisions and actions that rest with the mentor

1. Approve this plan, and say whether to run `git init` and where the repository will be hosted.
2. Confirm with CosmoHub's help pages or support that scripted queries are acceptable. Until then use `--mode manual`.
3. Mount the external disk and set the data root.
4. Run S08, S09 and the full S05.
5. Decide what the student may redistribute. Flagship is CC BY-NC 3.0 IGO. No licence was found for Diffsky.
6. Decide when to add null-test boxes (section 7.1).

---

## Appendix A. If the Blosc2 filter cannot be loaded

1. Preferred: `import hdf5plugin` before opening files; `h5py` then reads the columns directly.
2. If `hdf5plugin` does not register filter 32026 with the installed HDF5 library, try the `blosc2` Python package: read each stored chunk with `dataset.id.read_direct_chunk(offset)` and decode it as a Blosc2 contiguous frame. Check the package documentation for the current function names.
3. Layout notes, verified by decoding these files by hand: each HDF5 chunk is one Blosc2 frame; the frame header length is a big-endian 32-bit integer at byte 11; the data chunks use LZ4 with bitshuffle; a column that is entirely zero is stored as a special frame with no data chunk.

## Appendix B. Sources

- Diffsky files: the base URL of section 2.1.
- Diffsky code and release notes: `https://github.com/ArgonneCPAC/diffsky` (pull requests 486, 489, 493, 494; `CHANGES.rst`).
- OpenCosmo portal: `https://cosmoexplorer.alcf.anl.gov/datasets/diffsky`.
- Flagship 2 paper: arXiv:2405.13495. CosmoHub: `https://cosmohub.pic.es/catalogs/353`.
- Chang et al. 2013: arXiv:1305.0793.
- Earlier project notes: `lectures/lecture04/project_plan_and_lecture04_agenda.md`, section 3.4.
