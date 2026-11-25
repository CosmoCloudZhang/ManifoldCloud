"""Measure the harmonised catalogues and write their validation tables and figures."""

import argparse
from pathlib import Path
import shlex
import sys

from manifoldcloud.core.config import OUTPUTS, load, resolve_data_root
from manifoldcloud.core.provenance import atomic_path, load_manifest, record_file, write_json
from manifoldcloud.catalogue.validate import COLOURS, compare_filter_curves, diffsky_depth, summarise_catalogue

DIFFSKY_CAVEAT = "Diffsky is incomplete for a Year 1 sample below approximately z = 0.25."
PALETTE = {"A": "#26669c", "B": "#a6482d"}
LABELS = {"A": "Flagship 2", "B": "Diffsky"}


def _plot(summary, folder):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures = []
    status = summary["diffsky_coverage"]
    for name, field, x_key, y_key, x_label, y_label in (
        ("number_counts", "number_counts", "mag_lo", "per_deg2", "Noiseless i magnitude (AB)",
         "Galaxies / deg² / 0.5 mag"),
        ("redshift_distribution", "redshift_distribution", "z_lo", "count", "True redshift",
         "Galaxies per Δz = 0.1"),
        ("sizes", "sizes", "mag_lo", "median_a_hl", "Noiseless i magnitude (AB)",
         "Median half-light major axis (arcsec)"),
    ):
        figure, axis = plt.subplots(figsize=(8, 4.7), layout="constrained")
        for key, catalogue in summary["catalogues"].items():
            rows = catalogue[field]
            x = [row[x_key] for row in rows]
            y = [row[y_key] for row in rows]
            if name == "sizes":
                axis.plot([value + 0.25 for value in x], y, color=PALETTE[key], label=LABELS[key], marker=".")
            else:
                width = 0.5 if name == "number_counts" else 0.1
                axis.bar(x, y, width=width, align="edge", facecolor="none", linewidth=1.1,
                         edgecolor=PALETTE[key], label=LABELS[key])
        if name == "number_counts":
            axis.set_yscale("log")
        if name == "redshift_distribution":
            axis.set_title(f"Noiseless i < {summary['year1_i']}", loc="left", fontsize=11)
        axis.set(xlabel=x_label, ylabel=y_label)
        axis.legend()
        axis.grid(axis="y", alpha=0.22)
        if status:
            figure.suptitle(status, fontsize=10)
        figures.append((name, figure))

    figure, axes = plt.subplots(3, 2, figsize=(9, 8), sharex=True, layout="constrained")
    for axis, colour in zip(axes.flat, COLOURS):
        for key, catalogue in summary["catalogues"].items():
            rows = catalogue["colours"]
            axis.plot([row["z_lo"] + 0.05 for row in rows], [row[colour] for row in rows],
                      color=PALETTE[key], marker="o", markersize=4, linestyle="none", label=LABELS[key])
        axis.set(ylabel=f"Median {colour} (mag)")
        axis.grid(axis="y", alpha=0.22)
    axes.flat[0].legend()
    axes.flat[-1].set_visible(False)
    figure.supxlabel("True redshift")
    if status:
        figure.suptitle(status, fontsize=10)
    figures.append(("colours", figure))
    paths = []
    for name, figure in figures:
        path = folder / f"{name}.png"
        with atomic_path(path) as part:
            figure.savefig(part, format="png", dpi=160)
        plt.close(figure)
        paths.append(path)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--catalogue", choices=("A", "B", "both"), default="both")
    parser.add_argument("--steps", help="Comma-separated Diffsky steps for the validation plots")
    parser.add_argument("--curve-file", type=Path, help="Local Diffsky transmission-curves HDF5 file")
    args = parser.parse_args()
    config = load()
    try:
        data = resolve_data_root(args.data_root, config)
        interim = data / "interim" / "harmonised"
        source = data / "raw" / "diffsky" / config.diffsky.catalogue
        command = shlex.join(["python", *sys.argv])
        summary = {"catalogues": {}, "diffsky_coverage": None, "year1_i": config.cuts.year1_i}
        paths = {}
        if args.catalogue != "B":
            paths["A"] = [interim / "flagship2_mirror_843.parquet"]
        if args.catalogue != "A":
            folder = interim / "diffsky_843"
            if args.steps:
                paths["B"] = [folder / f"shell_{int(step)}.parquet" for step in args.steps.split(",")]
            else:
                paths["B"] = sorted(folder.glob("shell_*.parquet"))
            if len(paths["B"]) == len(config.diffsky.steps):
                summary["diffsky_coverage"] = DIFFSKY_CAVEAT
            else:
                summary["diffsky_coverage"] = f"Diffsky subset ({len(paths['B'])} shells). {DIFFSKY_CAVEAT}"
        for key, files in paths.items():
            if not files or not all(file.is_file() for file in files):
                raise ValueError(f"Missing harmonised catalogue {key} files under {interim}")
            result = summarise_catalogue(files, area_deg2=config.diffsky.area_deg2,
                                         i_limit=config.cuts.year1_i, temp_directory=data)
            summary["catalogues"][key] = result
            print(f"{LABELS[key]}: {result['rows']:,} rows; {result['totals']}")
        if "B" in paths:
            summary["diffsky_depth"] = diffsky_depth(load_manifest(source / "manifest.json"))
            curve_file = args.curve_file or source / f"diffsky_{config.diffsky.catalogue}_transmission_curves.hdf5"
            summary["diffsky_filter_curves"] = compare_filter_curves(curve_file)
            for row in summary["diffsky_depth"]["rows"]:
                print(f"Diffsky depth: {row}")
            for band, metrics in summary["diffsky_filter_curves"].items():
                print(f"Diffsky {band} vs speclite lsst2023: maximum difference "
                      f"{metrics['max_absolute_difference']:.3g} ({metrics['samples']:,} samples)")
        figure_paths = _plot(summary, OUTPUTS / "figures" / "data_validation")
        report = OUTPUTS / "tables" / "data_validation_summary.json"
        write_json(report, summary)
        row_count = sum(catalogue["rows"] for catalogue in summary["catalogues"].values())
        inputs = [str(file) for files in paths.values() for file in files]
        if "B" in paths:
            inputs.extend((str(source / "manifest.json"), str(curve_file)))
        for output in (report, *figure_paths):
            record_file(output.parent / "manifest.json", output, source=inputs, command=command, row_count=row_count)
            print(output)
        if "B" in paths and not summary["diffsky_depth"]["passed"]:
            raise ValueError("Diffsky depth evidence did not meet the plan's three-shell check")
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
