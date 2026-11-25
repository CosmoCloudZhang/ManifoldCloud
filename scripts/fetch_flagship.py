"""Prepare a Flagship web query or acquire its result through the CosmoHub API."""

import argparse
from getpass import getpass
from math import isfinite
import os
from pathlib import Path
import shlex
from shutil import copyfile
import sys

import pyarrow.parquet as pq

from manifoldcloud.config import load, resolve_data_root
from manifoldcloud.cosmohub import CosmoHubClient, CosmoHubError
from manifoldcloud.flagship import COUNT_CUTS, build_count_query, build_data_query
from manifoldcloud.logs import setup_logging
from manifoldcloud.provenance import atomic_path, record_file, write_json, write_text

SOURCE = "CosmoHub catalogue 353 (Euclid Flagship 2)"
PRIVATE_KEYS = {"authorization", "cookie", "e_mail", "email", "password", "token", "x_token",
                "access_token", "refresh_token", "user_email", "username"}


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
            f"n_i{int(round(cut * 10))}{suffix}" for cut in COUNT_CUTS for suffix in ("", "_kind_01")
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
        command = "python scripts/fetch_flagship.py --mode manual"
        if args.count:
            command += " --count"
        print(f"Ingest the file with `{command} --input /path/to/result.parquet`.")
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


def main(argv=None, *, environ=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("manual", "api"))
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--count", action="store_true", help="Prepare or acquire the count query")
    parser.add_argument("--input", type=Path, help="Ingest a Parquet file downloaded manually")
    parser.add_argument("--poll-interval", type=float, default=10.0, metavar="SECONDS")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check-only", action="store_true", help="Verify catalogue metadata")
    action.add_argument("--submit", action="store_true", help="Submit a new API query")
    action.add_argument("--resume", type=int, metavar="ID", help="Resume polling an API query")
    args = parser.parse_args(argv)
    if args.mode == "manual" and (args.check_only or args.submit or args.resume is not None):
        parser.error("API actions require --mode api")
    if args.mode == "api" and (args.input or not (args.check_only or args.submit or args.resume is not None)):
        parser.error("API mode requires --check-only, --submit or --resume ID")
    if not isfinite(args.poll_interval) or args.poll_interval < 0:
        parser.error("--poll-interval must be finite and nonnegative")
    try:
        config = load()
        folder = resolve_data_root(args.data_root, config) / "raw" / "flagship2" / "mirror_843"
        command = shlex.join(["python", "scripts/fetch_flagship.py", *(sys.argv[1:] if argv is None else argv)])
        if args.mode == "manual":
            _manual(args, config, folder, command)
        else:
            with CosmoHubClient() as client:
                _sign_in(client, os.environ if environ is None else environ)
                _api(args, config, folder, command, client)
    except (CosmoHubError, OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
