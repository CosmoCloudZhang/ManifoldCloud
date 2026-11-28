# ManifoldCloud

ManifoldCloud supports a mentored student research project on photometric-redshift calibration for the Rubin Observatory Legacy Survey of Space and Time. The project asks how a map of galaxy colours learned on one simulated sky behaves on a different simulation.

This repository holds the shared software: one conda environment, the code that acquires the two simulated catalogues, and a first pilot version of the catalogue preparation. The analysis that follows is developed by the students.

## Status

| Module | Purpose | State |
|---|---|---|
| `manifoldcloud.core` | Settings, logging, provenance | Complete |
| `manifoldcloud.acquisition` | Retrieve Flagship 2 and Diffsky | Complete and tested; both catalogues were acquired on 26 November 2026 |
| `manifoldcloud.catalogue` | Common schema, sizes, noise, validation | Pilot version, tested on four Diffsky shells; developed further by the students |
| Map training, redshift calibration, evaluation | | Not started; developed by the students |

## Install

The environment is built and tested on macOS with Apple silicon. The recipe also resolves for Intel Macs but has not been run on one. You need [Miniforge](https://conda-forge.org/download/) or another conda installation.

```bash
git clone https://github.com/CosmoCloudZhang/ManifoldCloud.git
cd ManifoldCloud
conda env create -f environment.yml
conda activate ManifoldConda
python scripts/check_environment.py
```

The check takes about a minute. It compares the installed versions with `environment.yml` and runs a small task with each group of packages, including a RAIL self-organising map. It ends with `The environment is ready.`

Three rules keep every copy of the environment the same:

- Create it from the repository root. The recipe installs the `manifoldcloud` package from this folder, so the folder must stay where it is.
- Add packages by editing `environment.yml`, then run `conda env update -n ManifoldConda -f environment.yml --prune`. Avoid a bare `conda install` or `pip install`.
- The name `ManifoldConda` is case-sensitive.

`environment.lock.yml` records the exact versions of the environment that was verified. Use it only to rebuild exactly that environment on an Apple silicon Mac.

Run the tests with:

```bash
python -m pytest
```

## Acquire the catalogues

Catalogue data are not part of the repository. They are written to `outputs/data/`, which git ignores. Both catalogues are acquired with the same three steps: a small check of the route, the fetch, and an offline check of the stored rows. The full instructions are in [documents/reproduce_data.md](documents/reproduce_data.md); the commands are:

```bash
python scripts/fetch_flagship.py --check    # small count query through CosmoHub
python scripts/fetch_flagship.py --fetch    # the Flagship rows, 1.5 GB
python scripts/fetch_flagship.py --verify   # checks the stored Flagship rows

python scripts/fetch_diffsky.py --check     # sizes of the 67 Diffsky source files
python scripts/fetch_diffsky.py --fetch     # the Diffsky rows, 2.0 GB
python scripts/fetch_diffsky.py --verify    # checks the stored Diffsky rows

python scripts/acquisition_status.py        # both catalogues: what is present and intact
```

The only difference is the sign-in. Flagship 2 needs a CosmoHub account; the script asks for the e-mail and password at a prompt and stores neither. Diffsky is read from a public HTTPS server and needs no account: the reader requests only the byte ranges that hold the needed columns, so only a small part of the 117 GB of source files is transferred.

Both fetch steps skip what is already stored and intact, so the same command can be run again after an interruption.

Every stored file is listed in a `manifest.json` beside it, with its SHA-256, its source, the command that made it and the package versions.

A 1% sample of both raw catalogues is available for lessons and quick tests. It writes 154,354 Flagship rows and 87,804 Diffsky rows to `outputs/data/sample/` and takes about 40 MB in total. Use `--withhold` when making the sample to omit named columns, and `--folder` to choose another sample folder.

```bash
python scripts/make_raw_sample.py --make
python scripts/make_raw_sample.py --verify
```

## Layout

```
manifoldcloud/        the Python package
  core/               settings, logging, provenance, sampling
  acquisition/        Diffsky reader and fetch, Flagship queries, CosmoHub client, status, a sample of the raw rows
  catalogue/          pilot harmonisation, sizes, noise and validation
scripts/              commands; each calls a function in the package
tests/                run offline with fabricated data
config/default.toml   catalogue names, columns, sky box, cuts and seeds
documents/            guides, the decisions log and the archived plan of the first build
outputs/data/         catalogue data (ignored by git)
outputs/figures/      figures from production runs of the scripts
outputs/tables/       summary tables from production runs of the scripts
report/               LaTeX sources of the written reports
scratch/              quick notes, scripts, prompts and exploratory results (ignored by git)
environment.yml       the single environment recipe
```

To keep data elsewhere, pass `--data-root`, set `MANIFOLDCLOUD_DATA_ROOT`, or copy `config/local.example.toml` to `config/local.toml`.

## Data sources

- **Euclid Flagship 2** mock galaxy catalogue, release 1.1, served by [CosmoHub](https://cosmohub.pic.es) as catalogue 353.
- **Diffsky** synthetic galaxy catalogue `c260710_09_02_2026`, patch 843.

Both are used over the same 34.3774 deg² of sky. The catalogues belong to their providers and carry their own terms of use and citation requirements. Check those terms before sharing any file derived from them.

## Tools this project builds on

The environment includes [RAIL](https://github.com/LSSTDESC/rail) and [qp](https://github.com/LSSTDESC/qp) from the LSST Dark Energy Science Collaboration, [photerr](https://github.com/jfcrenshaw/photerr) for Rubin photometric noise, and `umap-learn`, `minisom`, `somoclu` and `openTSNE` for map training.

## How the code was written

The first version of the pipeline and this restructuring were written with AI coding assistants under the mentor's direction and review. The plan that the first build followed is kept in [documents/archive](documents/archive). The instructions given to the assistant for that build and its run report are no longer part of the repository; they remain in its git history, and the last commit that holds them is `415ebef`.

## Licence

The code is released under the MIT licence; see [LICENSE](LICENSE). The licence does not cover the catalogue data.
