# Acquire and reproduce the ManifoldCloud data

Catalogue A is Euclid Flagship 2, release 1.1 (CosmoHub catalogue 353). Catalogue B is Diffsky `c260710_09_02_2026`, patch 843. Both cover the same 34.3774 deg².

Sections 1 to 3 are the acquisition, which is complete and tested. Section 4 is the pilot catalogue preparation, which the students develop further.

## Before you start

Create and check the environment as described in the [README](../README.md), then work from the repository root with `ManifoldConda` active.

Data go to `outputs/data/` in the repository, which git ignores. The folder is created on first use. To keep the data elsewhere, choose an existing folder in one of three ways; the first that is set wins:

1. `--data-root /path/to/folder` on a command.
2. The environment variable `MANIFOLDCLOUD_DATA_ROOT`.
3. `data_root` in `config/local.toml` (copy `config/local.example.toml`).

The acquired files and the products made from them are expected to need roughly 10 GB. That figure is an estimate and has not been measured.

## 1. Flagship 2

Flagship needs a CosmoHub account, so the mentor runs this section. Type the password only into CosmoHub's own page or the script's hidden prompt. Keep it out of commands and files.

### 1.1 Check three column meanings

On the catalogue 353 page in CosmoHub, read the column descriptions and confirm that:

- the `_el_model3_ext` fluxes include internal dust and emission lines;
- `bulge_r50` and `disk_r50` are major-axis half-light radii;
- `bulge_fraction` is a fraction of flux.

Record the outcome in [decisions_log.md](decisions_log.md). If one differs, change `config/default.toml` before querying.

### 1.2 Run the count query

The count query is small and tests the whole route before the large download.

```bash
python scripts/fetch_flagship.py --mode manual --count
```

This writes `count_query.sql` under `outputs/data/raw/flagship2/mirror_843/`. Open catalogue 353 in CosmoHub, paste the SQL into Expert Mode, request Parquet format and download the result. Then store it:

```bash
python scripts/fetch_flagship.py --mode manual --count --input /path/to/count_result.parquet
```

### 1.3 Run the data query

```bash
python scripts/fetch_flagship.py --mode manual
```

Submit `query.sql` the same way, download the result and store it:

```bash
python scripts/fetch_flagship.py --mode manual --input /path/to/data_result.parquet
```

The script expects one Parquet file per query. If CosmoHub delivers the result in another form, stop and note it in the decisions log.

### 1.4 Verify the stored rows

```bash
python scripts/fetch_flagship.py --verify
```

The check is offline. It recomputes both checksums and reads the catalogue in batches to confirm that:

- every row lies inside the mirror box;
- every row is a galaxy (`kind` 0 or 1);
- every row has a positive i-band flux and noiseless i < 26.5;
- the row count equals the count query;
- the density at i < 25.3 is within 10% of 192,700 per deg².

### API mode

`--mode api` submits the same SQL through CosmoHub's web API with `--check-only`, `--submit` or `--resume ID`. It was tested only against fabricated replies and has never been run against CosmoHub. Confirm that CosmoHub permits scripted use before trying it.

## 2. Diffsky

Diffsky is read from a public HTTPS server and needs no account. The 67 shells total 116,531,444,695 bytes, but the reader requests only the byte ranges that hold the 27 needed columns.

List the shells first. This transfers no catalogue data and confirms the total size:

```bash
python scripts/fetch_diffsky.py --dry-run --verify-full
```

Then extract them:

```bash
python scripts/fetch_diffsky.py --verify-full
```

What to expect:

- **Duration:** an estimated 2 to 4 hours. The estimate comes from measurements on single shells and has not been tested on the full set.
- **Restarting:** run the same command again. Shells whose files match their recorded checksums are skipped.
- **Outages:** a shell that fails is tried again after 30 s and after 120 s before the run stops.
- **Output:** `shell_<step>.parquet` for each shell, the filter transmission curves and `manifest.json` under `outputs/data/raw/diffsky/c260710_09_02_2026/`. Each shell keeps the rows with noiseless i < 26.5.

If you hold a local copy of the Diffsky files, add `--location /path/to/folder` to read them from disk.

## 3. Check what has been acquired

```bash
python scripts/acquisition_status.py
```

The report is offline. It recomputes the checksum of every stored file and lists what is missing or changed. It ends with `Acquisition complete.` once all 67 shells, the transmission curves and the four Flagship files are in place.

## 4. Catalogue preparation (pilot version)

These commands build the common schema, the validation figures and the Year 1 samples.

```bash
python scripts/harmonise.py
python scripts/validate.py
python scripts/make_year1_sample.py
python scripts/make_year1_sample.py --student-only
```

They write to `outputs/data/interim/`, `outputs/data/processed/year1/`, `outputs/figures/data_validation/` and `outputs/tables/`.

This stage was tested on four Diffsky shells and on fabricated Flagship rows. It has never processed real Flagship data. Four limits are known:

- Harmonisation stops at the first Flagship row with a zero or negative flux in any band, an axis ratio above 1, or a bulge fraction above 1.
- The noise for a catalogue comes from one random stream, so processing a subset of shells gives different noise from processing all of them.
- About 8% of the pilot Year 1 rows have no noisy u-band magnitude. No rule for these non-detections has been chosen.
- Diffsky is incomplete for a Year 1 sample below about z = 0.25.

## Data terms

The project notes record that Flagship is distributed under CC BY-NC 3.0 IGO and asks users to cite the Flagship papers and CosmoHub. No redistribution licence has been identified for Diffsky. Check the providers' current terms before sharing any file derived from either catalogue, including the student subsets.
