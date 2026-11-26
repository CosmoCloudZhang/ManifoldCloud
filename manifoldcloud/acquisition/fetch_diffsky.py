"""Acquire the Diffsky shells from the public server and verify the stored rows.

The script reads the needed columns of each shell and keeps the rows below the
noiseless i-band limit. Each shell becomes one Parquet file under
raw/diffsky/<catalogue>/ in the data root, with its checksum and source in
manifest.json. A shell whose file already matches its recorded checksum is
skipped, so an interrupted run can be restarted with the same command. The
server needs no account.
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
# Rows and synthetic rows of four source shells before the selection, from the pipeline plan.
REFERENCE_COUNTS = {487: (880, 183), 442: (14_724, 11_362), 392: (51_476, 40_019), 300: (339_890, 280_356)}
# Rows of step 300 with i < 25.3 and p_merge < 0.5, from the same plan.
REFERENCE_STEP_300_BRIGHT = 124_057
FULL_SOURCE_BYTES = 116_531_444_695
# The noiseless i-band limit at which the Flagship density is checked, used here for comparison.
DENSITY_CUT = 25.3
# Seconds to wait before the second and third attempts at a remote shell.
RETRY_WAITS = (30, 120)


def diffsky_folder(root, config):
    """Return the folder that holds the extracted shells of the configured catalogue."""
    return Path(root) / "raw" / "diffsky" / config.diffsky.catalogue


def selected_steps(text, config):
    """Return the steps to work on and whether they are the whole catalogue."""
    steps = [int(step) for step in text.split(",")] if text else list(config.diffsky.steps)
    if len(set(steps)) != len(steps) or not set(steps) <= set(config.diffsky.steps):
        raise ValueError("Supply unique Diffsky step numbers from config/default.toml")
    return steps, set(steps) == set(config.diffsky.steps)


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


def check_reference_counts(step, details):
    """Compare the source counts recorded for a reference shell with the pipeline plan."""
    counts = details["rows_before"], details["synthetic_before"]
    if counts != REFERENCE_COUNTS[step]:
        raise ValueError(f"Step {step} has rows/synthetic {counts}, expected {REFERENCE_COUNTS[step]}")
    if step == 300 and details["bright_and_unmerged"] != REFERENCE_STEP_300_BRIGHT:
        raise ValueError(f"Step 300 bright and unmerged: {details['bright_and_unmerged']:,}, "
                         f"expected {REFERENCE_STEP_300_BRIGHT:,}")


def check_empty_steps(steps, empty_steps):
    """Accept shells without selected rows only at the highest redshifts, which are the lowest steps."""
    if not empty_steps:
        return
    nonempty_steps = set(steps) - set(empty_steps)
    if not nonempty_steps or max(empty_steps) >= min(nonempty_steps):
        raise ValueError(f"Empty outputs outside the highest-redshift prefix: {sorted(empty_steps)}")
    print(f"Empty highest-redshift steps: {sorted(empty_steps)}")


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


def check(location, steps, full):
    """List the source size of each shell without transferring catalogue data.

    For the whole catalogue the total must equal the size recorded when the
    catalogue was chosen, so a changed source is noticed before a long run.
    """
    sizes = resource_sizes([shell_location(location, step) for step in steps])
    for step, size in zip(steps, sizes, strict=True):
        print(f"Step {step}: {size:,} source bytes")
    total = sum(sizes)
    print(f"Total source size: {total:,} bytes across {len(steps)} shells")
    if full:
        if total != FULL_SOURCE_BYTES:
            raise ValueError(f"Full Diffsky source size differs from {FULL_SOURCE_BYTES:,} bytes")
        print("The total matches the size recorded for the catalogue.")


def fetch(args, config, root):
    """Extract the selected shells and the transmission curves, skipping what is stored and intact."""
    location = args.location or config.diffsky.location
    steps, full = selected_steps(args.steps, config)
    if full:
        check(location, steps, full)

    folder = diffsky_folder(root, config)
    manifest = folder / "manifest.json"
    command = command_line(PROGRAM, args.arguments)
    budget = TransferBudget(limit=args.byte_limit)
    started = perf_counter()
    empty_steps = []
    try:
        curves = fetch_curves(config, location, folder, command, budget, refresh=args.refresh, required=full)
        print(f"Transmission curves: {curves}", flush=True)
        for number, step in enumerate(steps, start=1):
            source = shell_location(location, step)
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
                with atomic_path(output) as part:
                    selected.to_parquet(part, index=False)
                    if pq.ParquetFile(part).metadata.num_rows != len(selected):
                        raise ValueError(f"Step {step} has an inconsistent Parquet row count")
                record_file(manifest, output, source=source, command=command,
                            row_count=len(selected), details=details, raw=True)
                action = f"{budget.bytes_received - before:,} bytes in {perf_counter() - shell_started:.2f} s"
            if details["rows_after"] == 0:
                empty_steps.append(step)
            print(f"Step {step} ({number} of {len(steps)}): {details['rows_before']:,} before, "
                  f"{details['rows_after']:,} after, {details['synthetic_before']:,} synthetic before; {action}",
                  flush=True)
            if step == 300:
                print(f"Step 300: i < 25.3 and p_merge < 0.5: {details['bright_and_unmerged']:,} rows", flush=True)
            if full and not verified_entry(manifest, output):
                raise ValueError(f"Manifest checksum failed for step {step}")
    finally:
        elapsed = perf_counter() - started
        rate = budget.bytes_received / 1_000_000 / elapsed
        print(f"Transfer: {budget.bytes_received:,} payload bytes; {budget.bytes_reserved:,} reserved bytes; "
              f"{budget.requests} range requests; {elapsed:.2f} s; {rate:.3f} MB/s", flush=True)
    if full:
        check_empty_steps(steps, empty_steps)
    print(f"Stored {len(steps)} of {len(config.diffsky.steps)} shells in {folder}")


def verify(config, folder, steps=None):
    """Check the stored shells against their checksums, the selection and the reference counts.

    The check is offline and reads one shell at a time, so it works on a
    laptop. Without steps it covers the whole catalogue and the transmission
    curves. Returns the measured numbers and raises ValueError at the first
    check that fails.
    """
    full = steps is None
    steps = list(config.diffsky.steps) if full else list(steps)
    manifest = folder / "manifest.json"
    limit = config.cuts.preselection_i
    required = {*config.diffsky.columns, "is_synthetic", "step"}
    rows = bright = 0
    faintest = -np.inf
    empty_steps, reference_steps = [], []
    for step in steps:
        path = folder / f"shell_{step}.parquet"
        if not path.exists():
            raise ValueError(f"Diffsky shell {step} has not been acquired yet: {path}")
        entry = verified_entry(manifest, path)
        if not entry:
            raise ValueError(f"Diffsky shell {step} has no manifest record or differs from its "
                             f"recorded checksum: {path}")
        shell = pq.ParquetFile(path)
        missing = required - set(shell.schema_arrow.names)
        if missing:
            raise ValueError(f"Diffsky shell {step} is missing columns: {', '.join(sorted(missing))}")
        table = shell.read(columns=["lsst_i_unlensed", "step"])
        magnitudes = table.column("lsst_i_unlensed").to_numpy()
        details = entry["details"]
        if not len(magnitudes) == entry["row_count"] == details["rows_after"]:
            raise ValueError(f"Diffsky shell {step} has {len(magnitudes):,} rows; the manifest records "
                             f"{entry['row_count']:,}.")
        if not np.all(table.column("step").to_numpy() == step):
            raise ValueError(f"Diffsky shell {step} has rows labelled with another step.")
        if not np.all(magnitudes < limit):
            raise ValueError(f"Diffsky shell {step} has rows that fail noiseless i < {limit}.")
        if step in REFERENCE_COUNTS:
            check_reference_counts(step, details)
            reference_steps.append(step)
        if len(magnitudes):
            faintest = max(faintest, float(magnitudes.max()))
        else:
            empty_steps.append(step)
        rows += len(magnitudes)
        bright += int(np.count_nonzero(magnitudes < DENSITY_CUT))

    print(f"Shells: {len(steps)} of {len(config.diffsky.steps)}, {rows:,} rows, all with noiseless i < {limit}, "
          f"faintest i = {faintest:.4f}")
    if reference_steps:
        print(f"Reference shells {', '.join(map(str, reference_steps))}: source counts match the pipeline plan")
    result = {"shells": len(steps), "rows": rows, "bright_rows": bright, "faintest_i": faintest,
              "empty_steps": empty_steps}
    if not full:
        print("Checked a subset of the shells. Run --verify without --steps for the whole catalogue.")
        return result
    check_empty_steps(steps, empty_steps)
    curves = folder / Path(str(curves_location(folder, config.diffsky.catalogue))).name
    if not curves.exists():
        raise ValueError(f"The Diffsky transmission curves have not been acquired yet: {curves}")
    if not verified_entry(manifest, curves):
        raise ValueError("The Diffsky transmission curves have no manifest record or differ from their "
                         f"recorded checksum: {curves}")
    result["density"] = bright / config.diffsky.area_deg2
    print(f"Density at i < {DENSITY_CUT}: {result['density']:,.0f} per deg^2 (no reference value is set)")
    print("Transmission curves: verified")
    print("Diffsky acquisition verified.")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-root", type=Path, help="Folder for catalogue data (default: outputs/data)")
    parser.add_argument("--steps", help="Comma-separated subset of the catalogue steps (default: all)")
    parser.add_argument("--location", help="With --check or --fetch: a local folder or HTTPS address "
                                           "that holds the source files")
    parser.add_argument("--refresh", action="store_true",
                        help="With --fetch: read the shells again even if their checksums match")
    parser.add_argument("--byte-limit", type=int,
                        help="With --fetch: maximum total byte reservations for range requests")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true",
                        help="List the source sizes; transfers no catalogue data")
    action.add_argument("--fetch", action="store_true", help="Extract the shells; safe to restart")
    action.add_argument("--verify", action="store_true", help="Check the stored shells offline")
    args = parser.parse_args(argv)
    if not args.fetch and (args.refresh or args.byte_limit is not None):
        parser.error("--refresh and --byte-limit apply only to --fetch")
    if args.verify and args.location:
        parser.error("--location applies only to --check and --fetch")
    args.arguments = argv
    try:
        config = load()
        root = resolve_data_root(args.data_root, config)
        if args.verify:
            steps = selected_steps(args.steps, config)[0] if args.steps else None
            verify(config, diffsky_folder(root, config), steps)
        elif args.check:
            check(args.location or config.diffsky.location, *selected_steps(args.steps, config))
        else:
            fetch(args, config, root)
    except (OSError, ValueError, aiohttp.ClientError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
