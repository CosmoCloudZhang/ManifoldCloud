"""Make and verify deterministic samples of the two stored raw catalogues."""

import argparse
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from manifoldcloud.acquisition.fetch_diffsky import diffsky_folder
from manifoldcloud.acquisition.fetch_flagship import flagship_folder
from manifoldcloud.core.config import load, resolve_data_root
from manifoldcloud.core.provenance import atomic_path, command_line, record_file, verified_entry, write_text
from manifoldcloud.core.sampling import uniform_from_id

FLAGSHIP_NAME = "flagship_sample.parquet"
DIFFSKY_NAME = "diffsky_sample.parquet"
DEFAULT_FRACTION = 0.01
DEFAULT_FOLDER = "sample"
FLAGSHIP_RULE = "random_index < fraction"
DIFFSKY_RULE = "uniform_from_id(gal_id) < fraction"
PROGRAM = "scripts/make_raw_sample.py"


def sample_folder(root, name=DEFAULT_FOLDER):
    """Return a sample folder directly under the data root."""
    if (not name or "/" in name or "\\" in name or name.startswith(".")
            or name.casefold() in {"raw", "interim", "processed"}):
        raise ValueError(f"Invalid sample folder name: {name!r}")
    folder = Path(root) / name
    if folder.is_symlink():
        raise ValueError(f"Sample folder must not be a symbolic link: {name!r}")
    return folder


def _sample_schema(source, withhold):
    schema = source.schema_arrow.remove_metadata()
    # Drop fields before reading so that withheld values are never decoded.
    if withhold:
        schema = pa.Table.from_batches([], schema=schema).drop_columns(withhold).schema
    return schema


def _selected(rows, column, fraction):
    values = rows[column].to_numpy()
    if column == "gal_id":
        values = uniform_from_id(values)
    return values < fraction


def sample_flagship(path, fraction, *, withhold=()):
    """Select Flagship rows by random_index, retaining their order and column types."""
    with pq.ParquetFile(path) as source:
        schema = _sample_schema(source, withhold)
        batches = [
            batch.filter(_selected(batch, "random_index", fraction))
            for batch in source.iter_batches(batch_size=500_000, columns=schema.names)
        ]
    return pa.Table.from_batches(batches, schema=schema)


def sample_diffsky(folder, steps, fraction, *, withhold=()):
    """Select Diffsky rows by the identifier hash, in the given shell order."""
    samples = []
    for step in steps:
        with pq.ParquetFile(Path(folder) / f"shell_{step}.parquet") as source:
            schema = _sample_schema(source, withhold)
            table = source.read(columns=schema.names).replace_schema_metadata()
        samples.append(table.filter(_selected(table, "gal_id", fraction)))
    return pa.concat_tables(samples)


def _raw_rows(path):
    try:
        entry = verified_entry(path.parent / "manifest.json", path)
    except (OSError, ValueError) as error:
        raise ValueError(f"Cannot verify {path.name}. Run python scripts/acquisition_status.py") from error
    if entry is None:
        raise ValueError(f"Missing or changed raw file {path.name}. Run python scripts/acquisition_status.py")
    return entry["row_count"]


def _withheld_columns(withhold, flagship, diffsky):
    flagship_columns = pq.read_schema(flagship).names
    diffsky_columns = pq.read_schema(diffsky).names
    flagship_withheld, diffsky_withheld = [], []
    for name in sorted(set(withhold)):
        in_flagship = name in flagship_columns
        in_diffsky = name in diffsky_columns
        if name in {"random_index", "gal_id"} or in_flagship == in_diffsky:
            raise ValueError(f"Cannot withhold column {name!r}")
        (flagship_withheld if in_flagship else diffsky_withheld).append(name)
    return flagship_withheld, diffsky_withheld


def _fraction(value):
    if not 0 < value <= 1:
        raise ValueError("Sample fraction must be greater than 0 and at most 1")
    return value


def _write_sample(path, table, details):
    metadata = {
        "sample_rule": details["rule"],
        "sample_fraction": str(details["fraction"]),
        "source_rows": str(details["source_rows"]),
        "withheld": ",".join(details["withheld"]),
    }
    pq.write_table(table.replace_schema_metadata(metadata), path, compression="zstd")


def _readme(fraction, flagship_rows, diffsky_rows, withheld):
    omitted = f"| Columns left out | {', '.join(withheld)} | | |\n" if withheld else ""
    return f"""# A sample of the raw ManifoldCloud catalogues

Made by `python scripts/make_raw_sample.py --make`. Each file keeps a fixed fraction ({fraction}) of the rows of the raw catalogue, chosen by a rule that gives the same rows on every machine.

| File | Source | Rule | Rows |
|---|---|---|---|
| `{FLAGSHIP_NAME}` | Euclid Flagship 2, release 1.1, CosmoHub catalogue 353 | `{FLAGSHIP_RULE}` | {flagship_rows:,} |
| `{DIFFSKY_NAME}` | Diffsky `c260710_09_02_2026`, patch 843 | `{DIFFSKY_RULE}` | {diffsky_rows:,} |
{omitted}
Both cover the same 34.3774 deg². Check the files with `python scripts/make_raw_sample.py --verify`.

## Terms

These files are for use within the project. Do not pass them on or publish them.

Flagship 2 is served by CosmoHub, which asks every user of its data to include this text in the acknowledgements:

> This work has made use of CosmoHub (Tallada et al. 2020; Carretero et al. 2018), developed by PIC (maintained by IFAE and CIEMAT) in collaboration with ICE-CSIC. It received funding from the Spanish government (grant EQC2021-007479-P funded by MCIN/AEI/10.13039/501100011033), the EU NextGeneration/PRTR (PRTR-C17.I1), and the Generalitat de Catalunya.

The Flagship catalogue has its own reference papers, listed on its CosmoHub page. No redistribution licence has been identified for Diffsky.
"""


def make(config, root, fraction, command, *, folder=DEFAULT_FOLDER, withhold=()):
    """Verify the raw sources and write both samples with checksums and provenance."""
    fraction = _fraction(fraction)
    destination = sample_folder(root, folder)
    flagship = flagship_folder(root) / "flagship.parquet"
    diffsky = diffsky_folder(root, config)
    steps = list(config.diffsky.steps)
    if not steps:
        raise ValueError("No Diffsky shells are configured. Run python scripts/acquisition_status.py")
    flagship_rows = _raw_rows(flagship)
    diffsky_rows = sum(_raw_rows(diffsky / f"shell_{step}.parquet") for step in steps)
    flagship_withheld, diffsky_withheld = _withheld_columns(
        withhold, flagship, diffsky / f"shell_{steps[0]}.parquet",
    )
    flagship_sample = sample_flagship(flagship, fraction, withhold=flagship_withheld)
    diffsky_sample = sample_diffsky(diffsky, steps, fraction, withhold=diffsky_withheld)
    flagship_details = {
        "fraction": fraction, "rule": FLAGSHIP_RULE, "source_rows": flagship_rows, "withheld": flagship_withheld,
    }
    diffsky_details = {
        "fraction": fraction, "rule": DIFFSKY_RULE, "source_rows": diffsky_rows, "withheld": diffsky_withheld,
    }
    flagship_output, diffsky_output = destination / FLAGSHIP_NAME, destination / DIFFSKY_NAME
    with atomic_path(flagship_output) as flagship_part, atomic_path(diffsky_output) as diffsky_part:
        _write_sample(flagship_part, flagship_sample, flagship_details)
        _write_sample(diffsky_part, diffsky_sample, diffsky_details)
    manifest = destination / "manifest.json"
    for output, source, sample, details in (
        (flagship_output, flagship, flagship_sample, flagship_details),
        (diffsky_output, diffsky, diffsky_sample, diffsky_details),
    ):
        record_file(manifest, output, source=source, command=command, row_count=sample.num_rows, details=details)
        print(f"{output.name}: {sample.num_rows:,} rows")
    write_text(destination / "README.md", _readme(
        fraction, flagship_sample.num_rows, diffsky_sample.num_rows, sorted(flagship_withheld + diffsky_withheld),
    ))


def _verify_file(path, columns, column, rule):
    entry = verified_entry(path.parent / "manifest.json", path)
    if entry is None:
        raise ValueError("missing or changed since sampling")
    details = entry["details"]
    fraction = _fraction(details["fraction"])
    if details["rule"] != rule:
        raise ValueError("sampling rule differs from the expected rule")
    expected = [name for name in columns if name not in details["withheld"]]
    with pq.ParquetFile(path) as source:
        schema = source.schema_arrow
        if source.metadata.num_rows != entry["row_count"]:
            raise ValueError("row count differs from the manifest")
        if schema.names != expected:
            raise ValueError("columns differ from the expected columns")
        if b"comments" in (schema.metadata or {}):
            raise ValueError("schema contains a comments entry")
        if not _selected(source.read(columns=[column]), column, fraction).all():
            raise ValueError("one or more rows break the sampling rule")
    return entry["row_count"]


def verify(config, root, *, folder=DEFAULT_FOLDER):
    """Check both output files against their manifest and configured sampling rules."""
    directory = sample_folder(root, folder)
    complete = True
    for name, columns, column, rule in (
        (FLAGSHIP_NAME, config.flagship.columns, "random_index", FLAGSHIP_RULE),
        (DIFFSKY_NAME, [*config.diffsky.columns, "is_synthetic", "step"], "gal_id", DIFFSKY_RULE),
    ):
        try:
            rows = _verify_file(directory / name, columns, column, rule)
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"{name}: {error}")
            complete = False
        else:
            print(f"{name}: {rows:,} rows verified")
    if complete:
        print("Sample verified.")
    return complete


def main(argv=None):
    """Run the offline sample command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, help="Folder for catalogue data (default: outputs/data)")
    parser.add_argument("--fraction", type=float, default=DEFAULT_FRACTION, help="Sample fraction (default: 0.01)")
    parser.add_argument("--folder", default=DEFAULT_FOLDER, help="Name of the sample folder (default: sample)")
    parser.add_argument("--withhold", nargs="*", metavar="COLUMN", help="With --make: omit the named raw columns")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--make", action="store_true", help="Make a sample from verified local raw files")
    action.add_argument("--verify", action="store_true", help="Verify the sample offline")
    args = parser.parse_args(argv)
    if args.withhold is not None and not args.make:
        parser.error("--withhold applies only to --make")
    try:
        fraction = _fraction(args.fraction)
        config = load()
        root = resolve_data_root(args.data_root, config)
        if args.make:
            make(config, root, fraction, command_line(PROGRAM, argv), folder=args.folder, withhold=args.withhold or ())
        elif not verify(config, root, folder=args.folder):
            parser.exit(1)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
