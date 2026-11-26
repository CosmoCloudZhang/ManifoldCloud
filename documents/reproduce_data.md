# Acquire and reproduce the ManifoldCloud data

Catalogue A is Euclid Flagship 2, release 1.1 (CosmoHub catalogue 353). Catalogue B is Diffsky `c260710_09_02_2026`, patch 843. Both cover the same 34.3774 deg².

Sections 1 to 3 are the acquisition, which is complete and tested. Both catalogues were acquired this way on 26 November 2026. Section 4 is the pilot catalogue preparation, which the students develop further.

## Before you start

Create and check the environment as described in the [README](../README.md), then work from the repository root with `ManifoldConda` active.

Data go to `outputs/data/` in the repository, which git ignores. The folder is created on first use. To keep the data elsewhere, choose an existing folder in one of three ways; the first that is set wins:

1. `--data-root /path/to/folder` on a command.
2. The environment variable `MANIFOLDCLOUD_DATA_ROOT`.
3. `data_root` in `config/local.toml` (copy `config/local.example.toml`).

The acquired files take 3.5 GB: 1.5 GB for Flagship and 2.0 GB for Diffsky. The products made from the full catalogues have not been measured.

## The same three steps for both catalogues

| Step | Option | Flagship 2 | Diffsky |
|---|---|---|---|
| 1. Check the route | `--check` | A small count query | The sizes of the 67 source files |
| 2. Fetch | `--fetch` | The data query and its download | The extraction of the 67 shells |
| 3. Verify | `--verify` | Offline check of the stored rows | Offline check of the stored rows |

Only the sign-in differs. Flagship needs a CosmoHub account, so its first two steps ask for an e-mail and a password. Diffsky needs no account.

Both fetch steps skip what is already stored and intact, so the same command can be run again after an interruption. Add `--refresh` to fetch again anyway.

## 1. Flagship 2

Flagship needs a CosmoHub account, so the mentor runs this section. The script signs in through CosmoHub's web API and asks for the e-mail and password at a prompt. The password is not shown, and neither is stored. Keep the password out of commands and files.

CosmoHub publishes no documentation for this API. The script makes the same calls as the CosmoHub website, and both queries ran this way on 26 November 2026. If CosmoHub changes the API, the script stops and names the step that failed.

### 1.1 Check three column meanings

On the catalogue 353 page in CosmoHub, read the column descriptions and confirm that:

- the `_el_model3_ext` fluxes include internal dust and emission lines;
- `bulge_r50` and `disk_r50` are major-axis half-light radii;
- `bulge_fraction` is a fraction of flux.

Record the outcome in [decisions_log.md](decisions_log.md). If one differs, change `config/default.toml` before querying.

### 1.2 Check: run the count query

The count query is small and tests the whole route before the large download.

```bash
python scripts/fetch_flagship.py --check
```

The command prints the query ID, waits for CosmoHub and stores `counts.parquet` under `outputs/data/raw/flagship2/mirror_843/`, beside the SQL it sent as `count_query.sql`. It then prints the counts, the number of rows the data query will return, and the density at i < 25.3 against the reference. Record the counts in the decisions log. If the density differs by more than 10%, review the box and the selection before going on.

### 1.3 Fetch: run the data query

```bash
caffeinate -i python scripts/fetch_flagship.py --fetch
```

`caffeinate -i` keeps the Mac awake until the command ends. The result is stored as `flagship.parquet`, beside `query.sql`. On 26 November 2026 the query and the download of 1.5 GB took about eight minutes.

If the run is interrupted, continue with the query ID that was printed. This waits for the same query and downloads its result without submitting again:

```bash
python scripts/fetch_flagship.py --fetch --resume ID
```

Use `--check --resume ID` for a count query. The script waits up to two hours for a query; after a timeout, continue with `--resume` in the same way.

If the result of the present query is already stored and matches its checksum, `--check` and `--fetch` say so and do not sign in.

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

### Checking the column names

`python scripts/fetch_flagship.py --columns` signs in and compares the requested column names with the catalogue's metadata. It was tested only against fabricated replies and has not been run against CosmoHub. The script already asks CosmoHub to check each query before submitting it, so this step is optional.

## 2. Diffsky

Diffsky is read from a public HTTPS server and needs no account. The 67 source files total 116,531,444,695 bytes, but the reader requests only the byte ranges that hold the 27 needed columns.

### 2.1 Check: list the source files

```bash
python scripts/fetch_diffsky.py --check
```

This transfers no catalogue data. It asks the server for the size of each source file and confirms that the total is unchanged. It takes about half a minute.

### 2.2 Fetch: extract the shells

```bash
caffeinate -i python scripts/fetch_diffsky.py --fetch
```

What to expect:

- **Duration:** on 26 November 2026 the 63 shells that were not yet stored took about an hour and a half.
- **Restarting:** run the same command again. Shells whose files match their recorded checksums are skipped.
- **Outages:** a shell that fails is tried again after 30 s and after 120 s before the run stops.
- **Output:** `shell_<step>.parquet` for each shell, the filter transmission curves and `manifest.json` under `outputs/data/raw/diffsky/c260710_09_02_2026/`. Each shell keeps the rows with noiseless i < 26.5. The 67 shells hold 8,754,707 rows in 2.0 GB.

If you hold a local copy of the Diffsky files, add `--location /path/to/folder` to `--check` and `--fetch` to read them from disk.

### 2.3 Verify the stored rows

```bash
python scripts/fetch_diffsky.py --verify
```

The check is offline. It recomputes every checksum and reads each shell to confirm that:

- all 67 shells and the transmission curves are present and unchanged;
- every shell has the needed columns and the row count in its manifest record;
- every row carries the step of its shell and has noiseless i < 26.5;
- the four reference shells (steps 487, 442, 392 and 300) have the source row counts given in the pipeline plan;
- a shell without rows occurs only at the highest redshifts.

It also prints the density at noiseless i < 25.3. No reference value is set for Diffsky, so this number is reported and not judged.

## 3. Check what has been acquired

```bash
python scripts/acquisition_status.py
```

The report is offline and covers both catalogues. It recomputes the checksum of every stored file and lists what is missing or changed. It ends with `Acquisition complete.` once all 67 shells, the transmission curves and the four Flagship files are in place.

## 4. Catalogue preparation (pilot version)

These commands build the common schema, the validation figures and the Year 1 samples.

```bash
python scripts/harmonise.py
python scripts/validate.py
python scripts/make_year1_sample.py
python scripts/make_year1_sample.py --student-only
```

They write to `outputs/data/interim/`, `outputs/data/processed/year1/`, `outputs/figures/data_validation/` and `outputs/tables/`.

This stage was tested on four Diffsky shells and on fabricated Flagship rows. It has never processed the real Flagship catalogue or the full set of Diffsky shells. Five limits are known:

- Harmonisation stops at the first Flagship row with a zero or negative flux in any band, an axis ratio above 1, or a bulge fraction above 1. The catalogue acquired on 26 November 2026 has no such row.
- The Flagship `gal_id` is copied from `galaxy_id`, which numbers the galaxies inside one halo and repeats across haloes: it takes 5,373 distinct values in 15,393,044 rows. Only the pair `halo_id` and `galaxy_id` identifies a galaxy.
- The noise for a catalogue comes from one random stream, so processing a subset of shells gives different noise from processing all of them.
- About 8% of the pilot Year 1 rows have no noisy u-band magnitude. No rule for these non-detections has been chosen.
- Diffsky is incomplete for a Year 1 sample below about z = 0.25.

## Data terms

The project notes record that Flagship is distributed under CC BY-NC 3.0 IGO and asks users to cite the Flagship papers and CosmoHub. No redistribution licence has been identified for Diffsky. Check the providers' current terms before sharing any file derived from either catalogue, including the student subsets.
