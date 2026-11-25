"""Apply Rubin Year 1 photometric noise and select the student science sample."""

import argparse
from pathlib import Path
import shlex
import sys

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from manifoldcloud.core.config import load, resolve_data_root
from manifoldcloud.catalogue.harmonise import BANDS, HARMONISED_SCHEMA
from manifoldcloud.catalogue.noise import NoiseSummary, add_noise, check_noise, make_noise_model
from manifoldcloud.core.provenance import atomic_path, record_file, write_json

YEAR1_SCHEMA = pa.schema(
    [*HARMONISED_SCHEMA,
     *((f"mag_{band}_{suffix}", pa.float32()) for band in BANDS for suffix in ("obs", "err")),
     ("sample", pa.bool_()), ("control_sample", pa.bool_())],
    metadata={**HARMONISED_SCHEMA.metadata, b"photometric_model": b"photerr.LsstErrorModel (Rubin Year 1)"},
)
STUDENT_COLUMNS = (
    "gal_id", "ra", "dec", "z_true", "z_obs", "mag_i",
    *(f"mag_{band}_{suffix}" for band in BANDS for suffix in ("obs", "err")),
    "a_hl", "b_hl", "random_index",
)
STUDENT_SCHEMA = pa.schema([YEAR1_SCHEMA.field(column) for column in STUDENT_COLUMNS],
                           metadata=YEAR1_SCHEMA.metadata)
MAX_STUDENT_BYTES = 200_000_000
DIFFSKY_CAVEAT = "Diffsky is incomplete for a Year 1 sample below approximately z = 0.25."


def _inputs(folder, catalogue, steps):
    if catalogue == "A":
        return [folder / "flagship2_mirror_843.parquet"]
    folder = folder / "diffsky_843"
    if steps:
        selected = [int(step) for step in steps.split(",")]
        if len(set(selected)) != len(selected):
            raise ValueError("Diffsky steps must be unique")
        return [folder / f"shell_{step}.parquet" for step in sorted(selected)]
    return sorted(folder.glob("shell_*.parquet"), key=lambda path: int(path.stem.split("_")[-1]))


def _make_sample(paths, output, seed, i_limit, catalogue):
    if not paths or not all(path.is_file() for path in paths):
        raise ValueError(f"Missing harmonised input for catalogue {catalogue}")
    rng = np.random.default_rng(seed)
    model = make_noise_model()
    measurements = NoiseSummary(i_limit=i_limit)
    with atomic_path(output) as part:
        with pq.ParquetWriter(part, YEAR1_SCHEMA) as writer:
            for path in paths:
                for batch in pq.ParquetFile(path).iter_batches(batch_size=250_000):
                    table = add_noise(batch.to_pandas(), random_state=rng, model=model, i_limit=i_limit)
                    measurements.add(table)
                    writer.write_table(pa.Table.from_pandas(table, schema=YEAR1_SCHEMA, preserve_index=False))
        summary = measurements.result()
        print(f"Catalogue {catalogue}, seed {seed}: {summary}", flush=True)
        check_noise(summary)
        result = pq.ParquetFile(part)
        if result.metadata.num_rows != summary["rows"]:
            raise ValueError(f"Catalogue {catalogue} Year 1 row count differs from the input")
    return {"seed": seed, **summary}


def select_student_sample(table, *, fraction):
    """Select science rows with random index strictly below the configured fraction."""
    if not 0 <= fraction <= 1:
        raise ValueError("The student fraction must be between zero and one")
    keep = table["sample"] & table["random_index"].lt(fraction)
    return table.loc[keep, list(STUDENT_COLUMNS)]


def _make_student_file(source, output, fraction):
    rows = 0
    with atomic_path(output) as part:
        inputs = pq.ParquetFile(source).iter_batches(batch_size=250_000, columns=[*STUDENT_COLUMNS, "sample"])
        with pq.ParquetWriter(part, STUDENT_SCHEMA) as writer:
            for batch in inputs:
                table = select_student_sample(batch.to_pandas(), fraction=fraction)
                writer.write_table(pa.Table.from_pandas(table, schema=STUDENT_SCHEMA, preserve_index=False))
                rows += len(table)
        size = part.stat().st_size
        if size >= MAX_STUDENT_BYTES:
            raise ValueError(f"{output.name} is {size:,} bytes. Reduce cuts.student_fraction to stay below 200 MB.")
        if pq.ParquetFile(part).metadata.num_rows != rows:
            raise ValueError(f"{output.name} has an inconsistent row count")
    return rows, size


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--catalogue", choices=("A", "B", "both"), default="both")
    parser.add_argument("--steps", help="Comma-separated Diffsky steps to process")
    parser.add_argument("--student-only", action="store_true", help="Select student rows from existing Year 1 files")
    args = parser.parse_args()
    if args.student_only and args.steps:
        parser.error("Select the Diffsky steps when creating the Year 1 input to --student-only")
    config = load()
    try:
        root = resolve_data_root(args.data_root, config)
        interim = root / "interim" / "harmonised"
        output = root / "processed" / "year1"
        command = shlex.join(["python", *sys.argv])
        catalogues = ("A", "B") if args.catalogue == "both" else (args.catalogue,)
        if args.student_only:
            for catalogue in catalogues:
                source = output / f"{catalogue}.parquet"
                path = output / f"student_{catalogue}.parquet"
                fraction = config.cuts.student_fraction
                rows, size = _make_student_file(source, path, fraction)
                record_file(output / "manifest.json", path, source=str(source), command=command,
                            row_count=rows, details={"student_fraction": fraction})
                print(f"{path}: {rows:,} science rows, {len(STUDENT_COLUMNS)} columns, {size:,} bytes")
                if catalogue == "B":
                    print(DIFFSKY_CAVEAT)
            return
        summary = {"catalogues": {}}
        sources = []
        for catalogue in catalogues:
            inputs = _inputs(interim, catalogue, args.steps)
            source = [str(path) for path in inputs]
            sources.extend(source)
            path = output / f"{catalogue}.parquet"
            seed = config.seeds.noise_a if catalogue == "A" else config.seeds.noise_b
            metrics = _make_sample(inputs, path, seed, config.cuts.year1_i, catalogue)
            metrics["input_files"] = [file.name for file in inputs]
            if catalogue == "B":
                metrics["coverage"] = DIFFSKY_CAVEAT
                print(f"Diffsky input: {len(inputs)} shells. {DIFFSKY_CAVEAT}")
            summary["catalogues"][catalogue] = metrics
            record_file(output / "manifest.json", path, source=source, command=command,
                        row_count=metrics["rows"], details={"seed": seed})
            print(f"Wrote {path}")
        path = output / "summary.json"
        write_json(path, summary)
        rows = sum(metrics["rows"] for metrics in summary["catalogues"].values())
        record_file(output / "manifest.json", path, source=sources, command=command, row_count=rows)
        print(f"Wrote {path}")
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
