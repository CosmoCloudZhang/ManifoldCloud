# Data pipeline decisions

## 2026-11-25 overnight run

- The overnight prompt authorises local Git initialization and a baseline commit. The baseline contains the existing environment recipe and documents.
- The overnight prompt uses a repository virtual environment with the mentor's installed packages, limits live acquisition to the four-shell Diffsky pilot, defers S08, S09 and full S05, and sets the overnight data root to the ignored `data/` directory.
- S00 uses the mentor environment's existing build tooling for editable installation to avoid downloading build dependencies outside the package allow-list.
- S01 used approved outbound access to PyPI after the restricted sandbox could not resolve the package index. The three requested distributions resolved pytest's required dependencies `iniconfig` and `pluggy` inside `.venv`. The mentor conda environment was unchanged.
- S02 uses noise seeds 42 and 43 for Flagship and Diffsky, respectively, and a student subset fraction of 0.02. These are configurable defaults for reproducible runs and can be revised after the mentor measures the final files.
- S04 keeps fsspec's HTTP file interface and uses strict 206 responses, exact range endpoints, bounded metadata caching and coalesced prefetch. The Diffsky server reports `*` for total size in `Content-Range`; the reader accepts this with the exact offsets and verifies the received length. HEAD supplies the file size.
- The initial S00 editable install used pip's default ephemeral wheel-cache location. Pip reported that temporary path outside the repository. Later installs and test runs directed scratch files inside `.venv/` or `data/`.
- S05 records the magnitude histogram peak and the floor-halo counts in each raw manifest entry before applying the i < 26.5 selection. The S11 depth check needs the fainter rows and can now use the recorded counts without downloading the shell again.
- S05's four-shell row checks and checksums passed on all three pilot runs, but end-to-end speed reached 0.468, 0.501 and 0.640 MB/s against the unchanged >2.0 MB/s gate. The second run batched HDF5 object headers and removed fixed request-batch waits. The third used 128 KiB metadata blocks and a 64 KiB coalescing gap. The pilot scripts and verified data are available, and throughput is blocked. The downstream checks use the verified pilot files. The mentor can choose a local Globus transfer for full S05.
- S07 implements in-memory authentication and the no-network manual mode. The optional `--keyring` feature is omitted because it would require a dependency beyond the approved environment and the overnight workflow uses no persistence for credentials. Live response envelopes, API permission and download-token behaviour remain mentor checks.
- S11 uses projected Parquet scans with DuckDB's exact medians, a 1 GB memory setting, and scratch under the configured data root. Diffsky depth uses the uncut S05 counts. The optional live support-file check fetched 1,233,976 bytes. The `lsst2023` comparison aligns the 1 Å grids and uses a 1e-12 tolerance for floating-point interpolation. The largest measured difference was 6.12e-14.
- S12 uses `sample` for science membership and a separate `control_sample` boolean because the selections overlap. It stores the original rows and noisy magnitudes side by side. Numerical step order and a fixed batch size determine the seeded random stream. Output Parquet and summary JSON reproduce byte for byte. Provenance manifests record the new run time.
- S13 selects the configured 2% of science rows by `random_index` and keeps 21 analysis columns. The Diffsky pilot and separate synthetic Flagship fixture opened with pandas in the overnight virtual environment. The named `umapz` student interpreter was not available in the standard mentor or user conda locations, so its runtime check remains pending.

## 2026-11-25 single environment and acquisition module

- One conda environment, `ManifoldConda`, defined by the root `environment.yml`, replaces the mentor environment, the repository virtual environment and the separate student recipe. The students work on MacBooks, so only macOS is supported. Key packages are pinned to the minor release. `environment.lock.yml` records the exact versions that passed `scripts/check_environment.py`.
- RAIL is part of the environment: `pz-rail-base`, `qp-prob` and `tables-io` from conda-forge and `pz-rail-som` from PyPI. `pz-rail-astro-tools` is left out because it wraps the same `photerr` that the project calls directly. RAIL 2 has no UMAP stage.
- The package has three modules. `core` holds settings, logging and provenance. `acquisition` holds the Diffsky reader and fetch, the Flagship queries, the CosmoHub client and a status report. `catalogue` holds the pilot harmonisation, sizes, noise and validation. Development from `catalogue` onwards belongs to the students. The files in `scripts/` for acquisition only call functions in the package.
- Catalogue data default to `outputs/data/`. Figures and summary tables made by the scripts go to `outputs/figures/` and `outputs/tables/`. `report/` is reserved for the LaTeX sources of the written reports.
- Manifests record local sources relative to the folder that holds the manifest, and commands by their script path in the repository, so no machine-specific path is stored.
- The full Diffsky acquisition uses the public HTTPS server. The pilot was slow because each request waits 0.4 to 0.9 s before its first byte and the pilot shells are small; one stream carried 16 MiB in 2.1 s. The largest shell (step 127, 3.94 GB) needs 289 MB of column data in 75 requests of at most 8.4 MB. The 67 shells answered a size request and total 116,531,444,695 bytes. The estimate for the full run is 2 to 4 hours and is untested at that scale.
- The Diffsky fetch now also stores the filter transmission curves, repeats a failed remote shell after 30 s and 120 s, and sends no project name in its request headers.
- `scripts/fetch_flagship.py --verify` replaces the verification snippet in the reproduction guide. Manual mode is the recommended route to CosmoHub because the API mode has only been tested against fabricated replies.
- Measured on fabricated Flagship rows: a zero or negative flux in any band, an axis ratio of 1.0001 or a bulge fraction of 1.0001 makes harmonisation reject the whole batch. These limits are left for the catalogue stage to resolve.

## 2026-11-26 Flagship acquired through the CosmoHub API

- The count query and the data query ran through CosmoHub's web API, its first use against the live service. The calls match those made by the CosmoHub website on this date: sign-in with `GET /user`, `GET /catalogs/syntax`, `POST /queries`, `GET /queries` and the `download_results` address.
- Counts in the mirror box: 31,872,074 objects, all of `kind` 0 or 1. Noiseless i < 26.5: 15,393,044. i < 25.5: 7,730,176. i < 25.3: 6,701,647. i < 24.5: 3,713,082. i < 24.1: 2,736,498. The density at i < 25.3 is 194,943 per deg², 1.2% above the reference of 192,700.
- `flagship.parquet` holds 15,393,044 rows and 26 columns in 1,533,638,503 bytes. SHA-256: `3e2338f75779cde908560addda337bf86612b9883b76ba22dace1cdb3ea5d08f`. `counts.parquet` SHA-256: `1e9f4d24833bb462aedf13a532e0d526ad342879ab3e4710a7720bdd29cfb8c6`. The query and the download took about eight minutes.
- `scripts/fetch_flagship.py --verify` passed: every row lies inside the box, is a galaxy and has noiseless i < 26.5, and the row count equals the count query.
- Manual mode (`--mode manual` and `--input`) was removed at the mentor's request once both queries had passed, and `--mode` no longer exists. The manifest records the commands as they were run, `--mode api --count --submit` and `--mode api --submit`. If CosmoHub changes its API, the browser route can be restored from the commit before this change.
- Measured on the acquired rows: all six fluxes are positive and finite, both axis ratios lie between 0.108 and 1, and `bulge_fraction` lies between 0 and 1. The 728,425 rows with `dominant_shape` 0 have `bulge_fraction` exactly 1 and `disk_r50` exactly 0.
- `galaxy_id` numbers the galaxies inside one halo: it takes 5,373 distinct values, and it is 0 exactly where `kind` is 0. The pair `halo_id` and `galaxy_id` is unique. The pilot harmonisation copies `galaxy_id` alone into `gal_id`; this is left for the catalogue stage to resolve.
- Still open: the outcome of the three column checks in step 1.1 of the reproduction guide; whether CosmoHub accepts scripted use, since it publishes no API documentation or policy; and `--check-only`, which has not been run against CosmoHub.
- Still open: the access terms for Diffsky. On this date the HTTPS address served the files without credentials. The OpenCosmo portal marked the Diffsky dataset as restricted to the OpenCosmoALCF Globus group and its galaxy-catalogue product as unrestricted.

## 2026-11-26 Diffsky acquired; the same steps for both catalogues

- The full Diffsky extraction ran on this date with the command then named `--verify-full`. The manifest records 63 shells between 14:50 and 16:23 UTC, about an hour and a half; the four pilot shells of 25 November were kept. The earlier estimate was 2 to 4 hours.
- The 67 shells hold 8,754,707 rows with noiseless i < 26.5 out of 54,676,739 source rows. No shell is empty. The shells take 1,956,278,079 bytes and the transmission curves 1,233,976 bytes. Together with Flagship the acquired files take 3.5 GB; the earlier estimate of 10 GB included the products.
- `scripts/acquisition_status.py` reports the acquisition as complete: 67 of 67 shells, the curves and the four Flagship files match their checksums.
- At the mentor's request both fetch scripts now take the same three steps: `--check`, `--fetch` and `--verify`. Only the sign-in differs. For Flagship, `--check` replaces `--count --submit`, `--fetch` replaces `--submit`, and `--resume ID` is an option of either. For Diffsky, `--check` replaces `--dry-run --verify-full` and `--fetch` replaces `--verify-full`. The manifests keep the commands as they were run.
- `scripts/fetch_diffsky.py --verify` is new and offline. It recomputes every checksum and confirms that each shell has the columns and the row count in its manifest record, that every row carries its own step and has noiseless i < 26.5, that the four reference shells have the source counts of the pipeline plan, and that the curves are intact. It passed on the stored shells.
- The Diffsky density at noiseless i < 25.3 is 141,722 per deg², counting every stored row. Flagship has 194,943 per deg² at the same limit. No reference value is set for Diffsky, so the check reports the number without judging it. The difference is left for the catalogue stage to examine.
- `--check` and `--fetch` for Flagship no longer query CosmoHub when the result of the present query is stored and matches its checksum; `--refresh` queries again. Diffsky already skipped intact shells. The calls to CosmoHub are unchanged, but the new option names have run only against fabricated replies and against the stored files.
- `--verify-pilot` was removed with its throughput gate of 2 MB/s, which the pilot never passed for the reason recorded on 25 November. `--check-only` is now `--columns` and has still not been run against CosmoHub.

## 2026-11-26 Clean-up after the acquisition

- `scripts/make_flagship_query.py` was removed. It wrote the SQL to paste into the CosmoHub website; the fetch now writes the SQL beside its results. Its two SQL files moved to `tests/queries/`, where a test compares the query builder with them. They are identical to the stored `query.sql` and `count_query.sql`.
- `pilot_steps` was removed from `config/default.toml`; no code read it.
- `--byte-limit` was removed from the Diffsky fetch. It capped the transfer of the pilot run. The reader keeps its transfer limit, which its own tests use.
- `CosmoHubClient.cancel` was removed; no command called it.
- The ignore rule for `/data/`, the data folder of the first build, was removed.
- Conda holds only `base` and `ManifoldConda`. The package cache that no environment used was cleared, which freed 1.1 GB.
- `--columns` was kept until the mentor has run it once against CosmoHub.
- A `scratch/` folder at the repository root, created by the mentor and ignored by git, holds quick notes, scripts and prompts for one-off tasks. No tracked file depends on it.
- At the mentor's request the instructions given to the AI coding assistant for the first build and the run report of that build moved from `documents/archive/` to the mentor's `scratch/` folder. They remain in the git history; the last commit that holds them is `415ebef`. The pipeline plan stays in the archive because the code and the guide cite it.
- The tracked copies of the two Flagship queries were removed at the mentor's request, because the fetch stores the SQL it sends beside its results. `scripts/fetch_flagship.py --verify` now also confirms that this stored SQL is the query that the settings describe. The tests still run both queries on fabricated rows.
- `outputs/` is kept for production runs, at the mentor's request. The figures, the summary table and the data products of the four-shell pilot moved to the mentor's `scratch/` folder, and the pilot figures and table are no longer tracked; the last commit that holds them is `415ebef`. `scripts/validate.py` always writes to `outputs/figures/` and `outputs/tables/`, whatever shells it is given; this is left for the catalogue stage to resolve.

## 2026-11-26 Diffsky fetched again with the present command

- The mentor ran `scripts/fetch_diffsky.py --fetch --refresh`, which read all 67 shells and the transmission curves again. The run took 102 minutes, from 17:39 to 19:21 UTC. The manifest now records this command for every Diffsky file; these records replace those of the first run and of the pilot.
- The result equals the first run: 8,754,707 rows kept out of 54,676,739, no empty shell, and the same total of 1,956,278,079 bytes for the 67 shells.
- `scripts/fetch_diffsky.py --verify` passed on the rewritten shells, and `scripts/acquisition_status.py` reports the acquisition as complete.

## 2026-11-27 A sample of the raw catalogues

- `python scripts/make_raw_sample.py --make` writes both samples to `outputs/data/sample/`, and `python scripts/make_raw_sample.py --verify` checks the samples against their manifest.
- Flagship keeps rows where `random_index < fraction`. The raw Diffsky rows carry no random number, so Diffsky keeps rows where `uniform_from_id(gal_id) < fraction`. At a fraction of 0.01 the samples hold 154,354 Flagship rows and 87,804 Diffsky rows.
- The identifier hash moved unchanged from `catalogue/harmonise.py` to `core/sampling.py`. The caller in the harmonisation code now imports and uses it. This is the only change to the catalogue module.
- The sample drops the Flagship schema's `comments` metadata, which names the account holder. `--withhold` lets the command make a copy without specified columns.
