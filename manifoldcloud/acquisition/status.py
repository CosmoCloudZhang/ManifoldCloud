"""Report which acquired files are present and still match their recorded checksums.

The check is offline. It reads every stored file once to recompute its SHA-256,
so it answers "is the raw data complete and unchanged?" before any later step.
"""

import argparse
from pathlib import Path

from manifoldcloud.acquisition.diffsky import curves_location
from manifoldcloud.acquisition.fetch_diffsky import diffsky_folder
from manifoldcloud.acquisition.fetch_flagship import flagship_folder
from manifoldcloud.core.config import load, resolve_data_root
from manifoldcloud.core.provenance import verified_entry

FLAGSHIP_FILES = {
    "count query": "count_query.sql",
    "data query": "query.sql",
    "count result": "counts.parquet",
    "catalogue": "flagship.parquet",
}


def diffsky_status(root, config):
    """Return the verified and missing Diffsky shells, their rows and the curve file."""
    folder = diffsky_folder(root, config)
    manifest = folder / "manifest.json"
    verified, rows = [], 0
    for step in config.diffsky.steps:
        entry = verified_entry(manifest, folder / f"shell_{step}.parquet")
        if entry:
            verified.append(step)
            rows += entry["row_count"]
    curves = folder / Path(str(curves_location(folder, config.diffsky.catalogue))).name
    return {
        "folder": folder,
        "verified": verified,
        "missing": [step for step in config.diffsky.steps if step not in verified],
        "rows": rows,
        "curves": verified_entry(manifest, curves) is not None,
    }


def flagship_status(root):
    """Return which Flagship files are verified and the row count of the catalogue."""
    folder = flagship_folder(root)
    manifest = folder / "manifest.json"
    entries = {label: verified_entry(manifest, folder / name) for label, name in FLAGSHIP_FILES.items()}
    catalogue = entries["catalogue"]
    return {
        "folder": folder,
        "verified": [label for label, entry in entries.items() if entry],
        "missing": [label for label, entry in entries.items() if not entry],
        "rows": catalogue["row_count"] if catalogue else None,
    }


def report(root, config):
    """Print the acquisition status and return True when everything is in place."""
    diffsky, flagship = diffsky_status(root, config), flagship_status(root)
    print(f"Data root: {root}")
    print(f"Diffsky {config.diffsky.catalogue}: {len(diffsky['verified'])} of {len(config.diffsky.steps)} "
          f"shells verified, {diffsky['rows']:,} rows")
    if diffsky["missing"]:
        print(f"  missing or changed steps: {', '.join(map(str, diffsky['missing']))}")
    print(f"  transmission curves: {'verified' if diffsky['curves'] else 'missing or changed'}")
    rows = f", {flagship['rows']:,} rows" if flagship["rows"] is not None else ""
    print(f"Flagship 2 mirror box: {len(flagship['verified'])} of {len(FLAGSHIP_FILES)} files verified{rows}")
    if flagship["missing"]:
        print(f"  missing or changed: {', '.join(flagship['missing'])}")
    complete = not diffsky["missing"] and diffsky["curves"] and not flagship["missing"]
    print("Acquisition complete." if complete else "Acquisition incomplete.")
    return complete


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-root", type=Path, help="Folder for catalogue data (default: outputs/data)")
    args = parser.parse_args(argv)
    try:
        config = load()
        complete = report(resolve_data_root(args.data_root, config), config)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    parser.exit(0 if complete else 1)


if __name__ == "__main__":
    main()
