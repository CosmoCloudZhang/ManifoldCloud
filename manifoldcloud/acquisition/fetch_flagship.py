"""Acquire the Flagship counts and catalogue from CosmoHub and verify the stored rows.

The script signs in to CosmoHub's web API, submits the SQL, waits for the query
and downloads its Parquet result. It leaves counts.parquet, flagship.parquet, the
SQL and manifest.json under raw/flagship2/mirror_843/ in the data root. A result
that is already stored and matches its checksum is not queried again. The
e-mail and password are asked for at a prompt and are never stored.
"""

import argparse
from datetime import datetime
from getpass import getpass
from math import isfinite
import os
from pathlib import Path

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


def _files(folder, count):
    """Return the paths of the SQL and of its result."""
    if count:
        return folder / "count_query.sql", folder / "counts.parquet"
    return folder / "query.sql", folder / "flagship.parquet"


def _stored(config, folder, count):
    """Tell whether the result of the present query is stored and matches its checksum.

    The result must also be newer than the stored SQL, so a query that was
    saved again without completing does not pass for the result of an older one.
    """
    manifest = folder / "manifest.json"
    query, output = _files(folder, count)
    sent, result = verified_entry(manifest, query), verified_entry(manifest, output)
    return bool(sent and result and query.read_text(encoding="utf-8") == _query(config, count)
                and datetime.fromisoformat(sent["utc_time"]) <= datetime.fromisoformat(result["utc_time"]))


def _save_query(config, folder, command, count):
    sql = _query(config, count)
    query, _ = _files(folder, count)
    write_text(query, sql)
    record_file(folder / "manifest.json", query, source=SOURCE, command=command, row_count=None, raw=True)
    return query, sql


def _save_result(config, folder, command, count, writer):
    _, output = _files(folder, count)
    with atomic_path(output) as part:
        writer(part)
        rows = _validate_parquet(part, config, count)
    record_file(folder / "manifest.json", output, source=SOURCE, command=command, row_count=rows, raw=True)
    print(f"Saved {rows:,} rows to {output}")
    if count:
        report_counts(config, output)


def report_counts(config, path):
    """Show the counts and what they predict for the data query, before it is run."""
    row, = pq.read_table(path).to_pylist()
    for name, value in row.items():
        print(f"  {name}: {value:,}" if isinstance(value, int) else f"  {name}: {value}")
    expected = row.get(f"{_count_label(config.cuts.preselection_i)}_kind_01")
    bright = row.get(f"{_count_label(REFERENCE_CUT)}_kind_01")
    if not isinstance(expected, int) or not isinstance(bright, int):
        print("The counts for the selection are missing, so the data query cannot be checked in advance.")
        return
    ratio = bright / config.diffsky.area_deg2 / REFERENCE_DENSITY
    print(f"The data query will return {expected:,} rows.")
    print(f"Density at i < {REFERENCE_CUT}: {bright / config.diffsky.area_deg2:,.0f} per deg^2 "
          f"({ratio - 1:+.1%} against the reference {REFERENCE_DENSITY:,})")
    if abs(ratio - 1) > DENSITY_TOLERANCE:
        print(f"This differs by more than {DENSITY_TOLERANCE:.0%}: review the box and the selection "
              "before running the data query.")


def _sign_in(client, environ):
    email = environ.get("COSMOHUB_EMAIL") or input("CosmoHub e-mail: ")
    password = environ.get("COSMOHUB_PASSWORD") or getpass("CosmoHub password: ")
    redaction = setup_logging(secrets=(email, password))
    try:
        client.sign_in(email, password)
    finally:
        redaction.secrets = ()
        del email, password


def _save_columns(config, folder, command, client):
    """Save the catalogue metadata and confirm that it lists every requested column."""
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


def _acquire(config, folder, command, client, *, count, resume, poll_interval):
    """Run the count query or the data query and store its result.

    With resume, wait for that earlier query instead of submitting a new one.
    """
    _, sql = _save_query(config, folder, command, count)
    query_id = resume
    if query_id is None:
        client.check_syntax(sql)
        query_id = client.submit(sql)
        print(f"Submitted CosmoHub query {query_id}", flush=True)
    url = client.poll(query_id, interval=poll_interval)
    _save_result(config, folder, command, count, lambda part: client.download(url, part))


def verify(config, folder):
    """Check the stored catalogue against its checksum, the selection and the count query.

    The SQL stored beside the results must be the query that the settings
    describe now. Reads the catalogue in batches, so it works on a laptop.
    Returns the measured numbers and raises ValueError at the first check that
    fails.
    """
    manifest = folder / "manifest.json"
    counts, data = folder / "counts.parquet", folder / "flagship.parquet"
    for path, label in ((counts, "count result"), (data, "catalogue")):
        if not path.exists():
            raise ValueError(f"The Flagship {label} has not been acquired yet: {path}")
        if not verified_entry(manifest, path):
            raise ValueError(f"The Flagship {label} has no manifest record or differs from its "
                             f"recorded checksum: {path}")
    for count, label, step in ((True, "count query", "--check"), (False, "data query", "--fetch")):
        query, _ = _files(folder, count)
        if not verified_entry(manifest, query) or query.read_text(encoding="utf-8") != _query(config, count):
            raise ValueError(f"The stored Flagship {label} is missing or differs from the query that the "
                             f"settings describe now: {query}. Run {step} again.")
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
    parser.add_argument("--data-root", type=Path, help="Folder for catalogue data (default: outputs/data)")
    parser.add_argument("--resume", type=int, metavar="ID",
                        help="With --check or --fetch: wait for a query submitted earlier instead of "
                             "submitting a new one")
    parser.add_argument("--refresh", action="store_true",
                        help="With --check or --fetch: query again even if the stored result matches its checksum")
    parser.add_argument("--poll-interval", type=float, default=10.0, metavar="SECONDS")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true",
                        help="Run the small count query, which tests the route to CosmoHub")
    action.add_argument("--fetch", action="store_true",
                        help="Run the data query and download the catalogue; safe to restart")
    action.add_argument("--verify", action="store_true", help="Check the stored results offline")
    action.add_argument("--columns", action="store_true",
                        help="Optional: compare the requested columns with the catalogue metadata")
    args = parser.parse_args(argv)
    if not (args.check or args.fetch) and (args.resume is not None or args.refresh):
        parser.error("--resume and --refresh apply only to --check and --fetch")
    if not isfinite(args.poll_interval) or args.poll_interval < 0:
        parser.error("--poll-interval must be finite and nonnegative")
    try:
        config = load()
        folder = flagship_folder(resolve_data_root(args.data_root, config))
        command = command_line(PROGRAM, argv)
        if args.verify:
            verify(config, folder)
        elif not args.columns and args.resume is None and not args.refresh and _stored(config, folder, args.check):
            print(f"The Flagship {'count result' if args.check else 'catalogue'} is already stored and matches "
                  "its checksum; nothing was queried. Add --refresh to query CosmoHub again.")
            if args.check:
                report_counts(config, _files(folder, True)[1])
        else:
            with CosmoHubClient() as client:
                _sign_in(client, os.environ if environ is None else environ)
                if args.columns:
                    _save_columns(config, folder, command, client)
                else:
                    _acquire(config, folder, command, client, count=args.check, resume=args.resume,
                             poll_interval=args.poll_interval)
    except (CosmoHubError, OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
