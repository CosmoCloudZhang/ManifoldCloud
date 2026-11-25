"""Prepare the Flagship queries, store their results and verify the acquired rows.

Manual mode needs no network: it writes the SQL to paste into CosmoHub and later
ingests the Parquet file downloaded from the browser. API mode submits the same
SQL through CosmoHub's web API. Both leave counts.parquet, flagship.parquet, the
SQL and manifest.json under raw/flagship2/mirror_843/ in the data root.
"""

import argparse
from getpass import getpass
from math import isfinite
import os
from pathlib import Path
from shutil import copyfile

import numpy as np
import pyarrow.parquet as pq

from manifoldcloud.acquisition.cosmohub import CosmoHubClient, CosmoHubError
from manifoldcloud.acquisition.flagship import COUNT_CUTS, I_FLUX, build_count_query, build_data_query
from manifoldcloud.core.config import load, resolve_data_root
from manifoldcloud.core.logs import setup_logging
from manifoldcloud.core.provenance import (
    atomic_path, command_line, record_file, verified_entry, write_json, write_text,
)

PROGRAM = "scripts/fetch_flagship.py"
SOURCE = "CosmoHub catalogue 353 (Euclid Flagship 2)"
PRIVATE_KEYS = {"authorization", "cookie", "e_mail", "email", "password", "token", "x_token",
                "access_token", "refresh_token", "user_email", "username"}
# Galaxies per square degree at i < 25.3, from the Flagship counts in the pipeline plan.
REFERENCE_CUT = 25.3
REFERENCE_DENSITY = 192_700
DENSITY_TOLERANCE = 0.10


def flagship_folder(root):
    """Return the folder that holds the Flagship queries and their results."""
    return Path(root) / "raw" / "flagship2" / "mirror_843"


def _count_label(cut):
    return f"n_i{int(round(cut * 10))}"


def _public_metadata(value):
    if isinstance(value, dict):
        return {key: _public_metadata(item) for key, item in value.items()
                if key.casefold().replace("-", "_") not in PRIVATE_KEYS}
    if isinstance(value, list):
        return [_public_metadata(item) for item in value]
    return value


def _column_names(metadata):
    if not isinstance(metadata, dict):
        return set()
    for key in ("columns", "fields"):
        columns = metadata.get(key)
        if isinstance(columns, dict):
            return set(columns)
        if isinstance(columns, list):
            return {item if isinstance(item, str) else item.get("name", item.get("column_name"))
                    for item in columns if isinstance(item, (str, dict))} - {None}
    for key in ("catalog", "catalogue", "data", "schema"):
        names = _column_names(metadata.get(key))
        if names:
            return names
    return set()


def _required_columns(config, count):
    if count:
        return ["n_all", "n_kind_01", *(
            f"{_count_label(cut)}{suffix}" for cut in COUNT_CUTS for suffix in ("", "_kind_01")
        )]
    return config.flagship.columns


def _validate_parquet(path, config, count):
    try:
        result = pq.ParquetFile(path)
        missing = set(_required_columns(config, count)) - set(result.schema_arrow.names)
        rows = result.metadata.num_rows
    except (OSError, ValueError):
        raise ValueError("The Flagship result could not be opened as Parquet.") from None
    if missing:
        raise ValueError(f"The Flagship result is missing required columns: {', '.join(sorted(missing))}")
    if count and rows != 1:
        raise ValueError("The Flagship count result must contain a single row.")
    return rows


def _query(config, count):
    catalogue = config.flagship
    if count:
        return build_count_query(catalogue.table, [catalogue.box])
    return build_data_query(catalogue.table, catalogue.columns, [catalogue.box],
                            i_limit=config.cuts.preselection_i)


def _save_query(args, config, folder, command):
    sql = _query(config, args.count)
    query = folder / ("count_query.sql" if args.count else "query.sql")
    write_text(query, sql)
    record_file(folder / "manifest.json", query, source=SOURCE, command=command, row_count=None, raw=True)
    return query, sql


def _save_result(args, config, folder, command, writer):
    output = folder / ("counts.parquet" if args.count else "flagship.parquet")
    with atomic_path(output) as part:
        writer(part)
        rows = _validate_parquet(part, config, args.count)
    record_file(folder / "manifest.json", output, source=SOURCE, command=command, row_count=rows, raw=True)
    print(f"Saved {rows:,} rows to {output}")


def _manual(args, config, folder, command):
    query, _ = _save_query(args, config, folder, command)
    if args.input is None:
        print(f"Open catalogue 353 in CosmoHub and paste {query} into Expert Mode.")
        print("Submit the query in Parquet format and download the result when it succeeds.")
        ingest = f"python {PROGRAM} --mode manual"
        if args.count:
            ingest += " --count"
        print(f"Ingest the file with `{ingest} --input /path/to/result.parquet`.")
        return
    if not args.input.is_file():
        raise ValueError("The manual input must be an existing Parquet file.")
    _save_result(args, config, folder, command, lambda part: copyfile(args.input, part))


def _sign_in(client, environ):
    email = environ.get("COSMOHUB_EMAIL") or input("CosmoHub e-mail: ")
    password = environ.get("COSMOHUB_PASSWORD") or getpass("CosmoHub password: ")
    redaction = setup_logging(secrets=(email, password))
    try:
        client.sign_in(email, password)
    finally:
        redaction.secrets = ()
        del email, password


def _api(args, config, folder, command, client):
    if args.check_only:
        metadata = _public_metadata(client.catalog_metadata(config.flagship.catalogue))
        columns = _column_names(metadata)
        missing = set(config.flagship.columns) - columns
        if missing:
            raise ValueError(f"CosmoHub metadata is missing columns: {', '.join(sorted(missing))}")
        output = folder / "catalog_metadata.json"
        write_json(output, metadata)
        record_file(folder / "manifest.json", output, source=SOURCE, command=command,
                    row_count=len(columns), raw=True)
        print(f"Verified all {len(config.flagship.columns)} requested columns in {output}")
        return
    _, sql = _save_query(args, config, folder, command)
    query_id = args.resume
    if args.submit:
        client.check_syntax(sql)
        query_id = client.submit(sql)
        print(f"Submitted CosmoHub query {query_id}", flush=True)
    url = client.poll(query_id, interval=args.poll_interval)
    _save_result(args, config, folder, command, lambda part: client.download(url, part))


def verify(config, folder):
    """Check the stored catalogue against its checksum, the selection and the count query.

    Reads the catalogue in batches, so it works on a laptop. Returns the measured
    numbers and raises ValueError at the first check that fails.
    """
    manifest = folder / "manifest.json"
    counts, data = folder / "counts.parquet", folder / "flagship.parquet"
    for path, label in ((counts, "count result"), (data, "catalogue")):
        if not verified_entry(manifest, path):
            raise ValueError(f"The Flagship {label} is missing or differs from its recorded checksum: {path}")
    count_row, = pq.read_table(counts).to_pylist()
    box, limit = config.flagship.box, config.cuts.preselection_i
    expected = count_row.get(f"{_count_label(limit)}_kind_01")
    if expected is None:
        raise ValueError(f"The count query has no column for the i < {limit} selection.")

    rows = bright = 0
    faintest = -np.inf
    columns = ["ra_gal", "dec_gal", "kind", I_FLUX]
    for batch in pq.ParquetFile(data).iter_batches(batch_size=250_000, columns=columns):
        ra, dec, kind, flux = (batch.column(name).to_numpy(zero_copy_only=False) for name in columns)
        if not np.all((box.ra_min <= ra) & (ra < box.ra_max) & (box.dec_min <= dec) & (dec < box.dec_max)):
            raise ValueError("The Flagship catalogue has rows outside the mirror box.")
        if not np.isin(kind, (0, 1)).all():
            raise ValueError("The Flagship catalogue has rows that are not galaxies (kind 0 or 1).")
        if not np.all(np.isfinite(flux) & (flux > 0)):
            raise ValueError("The Flagship catalogue has rows without a positive i-band flux.")
        mag_i = -2.5 * np.log10(flux.astype(np.float64)) - 48.6
        if not np.all(mag_i < limit):
            raise ValueError(f"The Flagship catalogue has rows that fail noiseless i < {limit}.")
        rows += len(mag_i)
        bright += int(np.count_nonzero(mag_i < REFERENCE_CUT))
        faintest = max(faintest, float(mag_i.max()))
    if rows != expected:
        raise ValueError(f"The Flagship catalogue has {rows:,} rows; the count query found {expected:,}.")

    density = bright / config.diffsky.area_deg2
    result = {"rows": rows, "faintest_i": faintest, "bright_rows": bright, "density": density,
              "density_ratio": density / REFERENCE_DENSITY, "counts": count_row}
    print(f"Count query: {count_row}")
    print(f"Catalogue: {rows:,} rows, all inside the box, all galaxies, faintest i = {faintest:.4f}")
    print(f"Density at i < {REFERENCE_CUT}: {density:,.0f} per deg^2 "
          f"({result['density_ratio'] - 1:+.1%} against the reference {REFERENCE_DENSITY:,})")
    if abs(result["density_ratio"] - 1) > DENSITY_TOLERANCE:
        raise ValueError(f"The density differs from the reference by more than {DENSITY_TOLERANCE:.0%}.")
    print("Flagship acquisition verified.")
    return result


def main(argv=None, *, environ=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=("manual", "api"), help="Required unless --verify is given")
    parser.add_argument("--data-root", type=Path, help="Folder for catalogue data (default: outputs/data)")
    parser.add_argument("--count", action="store_true", help="Prepare or acquire the count query")
    parser.add_argument("--input", type=Path, help="Ingest a Parquet file downloaded manually")
    parser.add_argument("--poll-interval", type=float, default=10.0, metavar="SECONDS")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check-only", action="store_true", help="Verify catalogue metadata")
    action.add_argument("--submit", action="store_true", help="Submit a new API query")
    action.add_argument("--resume", type=int, metavar="ID", help="Resume polling an API query")
    action.add_argument("--verify", action="store_true", help="Check the stored results offline")
    args = parser.parse_args(argv)
    api_action = args.check_only or args.submit or args.resume is not None
    if args.verify and (args.mode or args.count or args.input):
        parser.error("--verify takes no other action")
    if not args.verify and args.mode is None:
        parser.error("--mode is required unless --verify is given")
    if args.mode == "manual" and api_action:
        parser.error("API actions require --mode api")
    if args.mode == "api" and (args.input or not api_action):
        parser.error("API mode requires --check-only, --submit or --resume ID")
    if not isfinite(args.poll_interval) or args.poll_interval < 0:
        parser.error("--poll-interval must be finite and nonnegative")
    try:
        config = load()
        folder = flagship_folder(resolve_data_root(args.data_root, config))
        command = command_line(PROGRAM, argv)
        if args.verify:
            verify(config, folder)
        elif args.mode == "manual":
            _manual(args, config, folder, command)
        else:
            with CosmoHubClient() as client:
                _sign_in(client, os.environ if environ is None else environ)
                _api(args, config, folder, command, client)
    except (CosmoHubError, OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
