"""Extract selected Diffsky columns and publish resumable Parquet shells.

Each shell becomes one Parquet file under raw/diffsky/<catalogue>/ in the data
root, with its checksum and source in manifest.json. A shell whose file already
matches its recorded checksum is skipped, so an interrupted run can be restarted
with the same command.
"""

import argparse
from pathlib import Path
from time import perf_counter, sleep

import aiohttp
import numpy as np
import pyarrow.parquet as pq

from manifoldcloud.acquisition.diffsky import (
    TransferBudget, copy_resource, curves_location, open_shell, read_columns, resource_sizes, shell_info,
    shell_location,
)
from manifoldcloud.core.config import load, resolve_data_root
from manifoldcloud.core.provenance import atomic_path, command_line, record_file, verified_entry

PROGRAM = "scripts/fetch_diffsky.py"
PILOT_COUNTS = {487: (880, 183), 442: (14_724, 11_362), 392: (51_476, 40_019), 300: (339_890, 280_356)}
PILOT_STEP_300_BRIGHT = 124_057
MIN_PILOT_MBPS = 2.0
FULL_SOURCE_BYTES = 116_531_444_695
# Seconds to wait before the second and third attempts at a remote shell.
RETRY_WAITS = (30, 120)


def diffsky_folder(root, config):
    """Return the folder that holds the extracted shells of the configured catalogue."""
    return Path(root) / "raw" / "diffsky" / config.diffsky.catalogue


def depth_statistics(table, bright_cut):
    """Measure depth on the raw sample, which still includes fainter bins."""
    magnitudes = table["lsst_i_unlensed"].to_numpy()
    finite = np.isfinite(magnitudes)
    floor = table["logmp_obs"].ge(10.5) & table["logmp_obs"].lt(10.6)
    peak = None
    if finite.any():
        counts, edges = np.histogram(magnitudes[finite], bins=np.arange(-50, 100.5, 0.5))
        if counts.any():
            mode = np.argmax(counts)
            peak = [float(edges[mode]), float(edges[mode + 1])]
    return {
        "mag_bin_peak": peak,
        "floor_halo_rows": int(floor.sum()),
        "floor_halo_bright_rows": int((floor & (magnitudes < bright_cut)).sum()),
    }


def extract_shell(config, location, step, budget):
    """Read a shell and return its selected rows and raw depth and count checks."""
    with open_shell(location, step, budget=budget) as handle:
        table = read_columns(handle, config.diffsky.columns)
        info = shell_info(handle)
    selected = table.loc[table["lsst_i_unlensed"] < config.cuts.preselection_i].copy()
    selected["step"] = np.int64(step)
    return selected, {
        **info,
        "rows_before": len(table),
        "rows_after": len(selected),
        "synthetic_before": int(table["is_synthetic"].sum()),
        "synthetic_after": int(selected["is_synthetic"].sum()),
        "bright_and_unmerged": int((table["lsst_i_unlensed"].lt(25.3) & table["p_merge"].lt(0.5)).sum()),
        "depth": depth_statistics(table, config.cuts.year1_i),
    }


def extract_with_retries(config, location, step, budget, *, remote):
    """Extract a shell, repeating a remote read that fails so a long run survives a brief outage."""
    waits = RETRY_WAITS if remote else ()
    for wait in (*waits, None):
        try:
            return extract_shell(config, location, step, budget)
        except (OSError, aiohttp.ClientError) as error:
            if wait is None:
                raise
            print(f"Step {step}: {type(error).__name__}: {error}; trying again in {wait} s", flush=True)
            sleep(wait)


def check_pilot_counts(step, details):
    counts = details["rows_before"], details["synthetic_before"]
    if counts != PILOT_COUNTS[step]:
        raise ValueError(f"Step {step} has rows/synthetic {counts}, expected {PILOT_COUNTS[step]}")
    if step == 300 and details["bright_and_unmerged"] != PILOT_STEP_300_BRIGHT:
        raise ValueError(f"Step 300 bright and unmerged: {details['bright_and_unmerged']:,}, "
                         f"expected {PILOT_STEP_300_BRIGHT:,}")


def fetch_curves(config, location, folder, command, budget, *, refresh=False, required=False):
    """Publish the filter transmission curves beside the shells; return what was done."""
    source = curves_location(location, config.diffsky.catalogue)
    output = folder / Path(str(source)).name
    manifest = folder / "manifest.json"
    if not refresh and verified_entry(manifest, output):
        return "verified existing output"
    if isinstance(source, Path) and not source.is_file():
        if required:
            raise ValueError(f"The Diffsky transmission curves are missing: {source}")
        return "not in the local folder; skipped"
    with atomic_path(output) as part:
        size = copy_resource(source, part, budget=budget)
    record_file(manifest, output, source=source, command=command, row_count=None, raw=True)
    return f"{size:,} bytes"


def fetch(args, config, root):
    location = args.location or config.diffsky.location
    steps = [int(step) for step in args.steps.split(",")] if args.steps else config.diffsky.steps
    if len(set(steps)) != len(steps) or not set(steps) <= set(config.diffsky.steps):
        raise ValueError("Supply unique Diffsky step numbers from config/default.toml")
    if args.verify_pilot and set(steps) != set(PILOT_COUNTS):
        raise ValueError("--verify-pilot requires steps 487,442,392,300")
    if args.verify_full and set(steps) != set(config.diffsky.steps):
        raise ValueError("--verify-full requires all configured shells")

    sources = [shell_location(location, step) for step in steps]
    if args.dry_run or args.verify_full:
        sizes = resource_sizes(sources)
        for step, size in zip(steps, sizes, strict=True):
            print(f"Step {step}: {size:,} source bytes")
        total = sum(sizes)
        print(f"Total source size: {total:,} bytes across {len(steps)} shells")
        if args.verify_full and total != FULL_SOURCE_BYTES:
            raise ValueError(f"Full Diffsky source size differs from {FULL_SOURCE_BYTES:,} bytes")
        if args.dry_run:
            return

    folder = diffsky_folder(root, config)
    manifest = folder / "manifest.json"
    command = command_line(PROGRAM, args.arguments)
    budget = TransferBudget(limit=args.byte_limit)
    started = perf_counter()
    fetched = 0
    empty_steps = []
    try:
        curves = fetch_curves(config, location, folder, command, budget,
                              refresh=args.refresh, required=args.verify_full)
        print(f"Transmission curves: {curves}", flush=True)
        for number, (step, source) in enumerate(zip(steps, sources, strict=True), start=1):
            output = folder / f"shell_{step}.parquet"
            saved = None if args.refresh else verified_entry(manifest, output)
            if saved:
                details = saved["details"]
                output.chmod(output.stat().st_mode & ~0o222)
                action = "verified existing output"
            else:
                before = budget.bytes_received
                shell_started = perf_counter()
                selected, details = extract_with_retries(config, location, step, budget,
                                                         remote=not isinstance(source, Path))
                if args.verify_pilot:
                    check_pilot_counts(step, details)
                with atomic_path(output) as part:
                    selected.to_parquet(part, index=False)
                    if pq.ParquetFile(part).metadata.num_rows != len(selected):
                        raise ValueError(f"Step {step} has an inconsistent Parquet row count")
                record_file(manifest, output, source=source, command=command,
                            row_count=len(selected), details=details, raw=True)
                fetched += 1
                action = f"{budget.bytes_received - before:,} bytes in {perf_counter() - shell_started:.2f} s"
            if args.verify_pilot:
                check_pilot_counts(step, details)
            if args.verify_full and details["rows_after"] == 0:
                empty_steps.append(step)
            print(f"Step {step} ({number} of {len(steps)}): {details['rows_before']:,} before, "
                  f"{details['rows_after']:,} after, {details['synthetic_before']:,} synthetic before; {action}",
                  flush=True)
            if step == 300:
                print(f"Step 300: i < 25.3 and p_merge < 0.5: {details['bright_and_unmerged']:,} rows", flush=True)
            if args.verify_full and not verified_entry(manifest, output):
                raise ValueError(f"Manifest checksum failed for step {step}")
    finally:
        elapsed = perf_counter() - started
        rate = budget.bytes_received / 1_000_000 / elapsed
        print(f"Transfer: {budget.bytes_received:,} payload bytes; {budget.bytes_reserved:,} reserved bytes; "
              f"{budget.requests} range requests; {elapsed:.2f} s; {rate:.3f} MB/s", flush=True)
    if args.verify_pilot:
        if fetched != len(steps):
            raise ValueError("Pilot throughput requires timing all four shells together; use --refresh")
        if rate <= MIN_PILOT_MBPS:
            raise ValueError(f"Pilot throughput {rate:.3f} MB/s did not exceed {MIN_PILOT_MBPS:.1f} MB/s")
    if args.verify_full and empty_steps:
        nonempty_steps = set(steps) - set(empty_steps)
        if not nonempty_steps or max(empty_steps) >= min(nonempty_steps):
            raise ValueError(f"Empty outputs outside the highest-redshift prefix: {sorted(empty_steps)}")
        print(f"Empty highest-redshift steps: {sorted(empty_steps)}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-root", type=Path, help="Folder for catalogue data (default: outputs/data)")
    parser.add_argument("--location", help="Local directory or public HTTPS base URL")
    parser.add_argument("--steps", help="Comma-separated subset of catalogue steps")
    parser.add_argument("--dry-run", action="store_true", help="Show source sizes without downloading data")
    parser.add_argument("--refresh", action="store_true", help="Re-read shells even if their checksums match")
    parser.add_argument("--byte-limit", type=int, help="Maximum total byte reservations for range requests")
    verification = parser.add_mutually_exclusive_group()
    verification.add_argument("--verify-pilot", action="store_true", help="Check pilot counts and throughput")
    verification.add_argument("--verify-full", action="store_true", help="Check full source size and output checksums")
    args = parser.parse_args(argv)
    args.arguments = argv
    try:
        config = load()
        fetch(args, config, resolve_data_root(args.data_root, config))
    except (OSError, ValueError, aiohttp.ClientError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
