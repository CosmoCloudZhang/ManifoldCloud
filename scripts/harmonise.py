"""Convert raw Flagship and Diffsky Parquet files to the common schema."""

import argparse
from functools import partial
from pathlib import Path
import shlex
import sys

from astropy.cosmology import FlatLambdaCDM
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from manifoldcloud.core.config import load, resolve_data_root
from manifoldcloud.catalogue.harmonise import HARMONISED_SCHEMA, harmonise_diffsky, harmonise_flagship, validate_harmonised
from manifoldcloud.core.provenance import atomic_path, record_file


def _verify_conversion(raw, table, catalogue):
    if catalogue == "A":
        flux = 10 ** (-0.4 * (table["mag_i"].to_numpy(dtype="float64") + 48.6))
        np.testing.assert_allclose(flux, raw["lsst_i_el_model3_ext"], rtol=2e-6, atol=0)
    else:
        valid = raw["beta_disk"].gt(0) & raw["r50_disk_2d"].gt(0) & table["b_disk"].gt(0)
        np.testing.assert_allclose(
            table.loc[valid, "a_disk"] / table.loc[valid, "b_disk"],
            raw.loc[valid, "alpha_disk"] / raw.loc[valid, "beta_disk"], rtol=2e-6, atol=0,
        )
        return int(valid.sum())
    return len(raw)


def _transform(source, output, catalogue, config):
    if catalogue == "A":
        transform = partial(harmonise_flagship, h=config.flagship.h)
    else:
        cosmology = FlatLambdaCDM(H0=config.diffsky.h0, Om0=config.diffsky.omega_m)
        transform = partial(harmonise_diffsky, cosmology=cosmology)
    rows = conversion_rows = 0
    sizes = []
    with atomic_path(output) as part:
        with pq.ParquetWriter(part, HARMONISED_SCHEMA) as writer:
            for batch in pq.ParquetFile(source).iter_batches(batch_size=250_000):
                raw = batch.to_pandas()
                result = transform(raw)
                validate_harmonised(result)
                conversion_rows += _verify_conversion(raw, result, catalogue)
                sizes.append(result.loc[result["mag_i"].gt(23.5) & result["mag_i"].lt(24.5), "a_hl"].to_numpy())
                writer.write_table(pa.Table.from_pandas(result, schema=HARMONISED_SCHEMA, preserve_index=False))
                rows += len(result)
        parquet = pq.ParquetFile(part)
        if not parquet.schema_arrow.remove_metadata().equals(HARMONISED_SCHEMA.remove_metadata()):
            raise ValueError("Harmonised Parquet schema differs from the plan")
        if parquet.schema_arrow.metadata.get(b"size_rule") != b"flux_weighted_quadrature":
            raise ValueError("Harmonised Parquet is missing size-rule metadata")
        if parquet.metadata.num_rows != rows:
            raise ValueError("Harmonised Parquet row count differs from the processed count")
    return rows, conversion_rows, sizes


def _sources(root, config, catalogue, steps):
    raw = root / "raw"
    out = root / "interim" / "harmonised"
    if catalogue == "A":
        return [(raw / "flagship2" / "mirror_843" / "flagship.parquet", out / "flagship2_mirror_843.parquet")]
    folder = raw / "diffsky" / config.diffsky.catalogue
    if steps is None:
        sources = sorted(folder.glob("shell_*.parquet"), key=lambda source: int(source.stem.split("_")[-1]))
    else:
        sources = [folder / f"shell_{int(step)}.parquet" for step in steps.split(",")]
    if not sources:
        raise ValueError(f"No extracted Diffsky shells in {folder}")
    return [(source, out / "diffsky_843" / source.name) for source in sources]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--catalogue", choices=("A", "B", "both"), default="both")
    parser.add_argument("--steps", help="Comma-separated Diffsky steps to harmonise")
    args = parser.parse_args()
    config = load()
    try:
        root = resolve_data_root(args.data_root, config)
        catalogues = ("A", "B") if args.catalogue == "both" else (args.catalogue,)
        manifest = root / "interim" / "harmonised" / "manifest.json"
        command = shlex.join(["python", *sys.argv])
        medians = {}
        for catalogue in catalogues:
            sizes = []
            for source, output in _sources(root, config, catalogue, args.steps):
                rows, conversions, samples = _transform(source, output, catalogue, config)
                sizes.extend(samples)
                record_file(manifest, output, source=str(source), command=command, row_count=rows)
                print(f"{catalogue} {output.name}: {rows:,} exact-schema finite rows; "
                      f"{conversions:,} flux or disk-axis round trips", flush=True)
            if not sizes or not any(sample.size for sample in sizes):
                raise ValueError(f"Catalogue {catalogue} has no sizes in the 23.5 < i < 24.5 interval")
            medians[catalogue] = float(np.median(np.concatenate(sizes)))
            print(f"{catalogue} median a_hl at 23.5 < i < 24.5: {medians[catalogue]:.6f} arcsec", flush=True)
            if not 0.1 <= medians[catalogue] <= 1.0:
                raise ValueError(f"Catalogue {catalogue} failed the [0.1, 1.0] arcsec size check")
        if len(medians) == 2 and max(medians.values()) >= 2 * min(medians.values()):
            raise ValueError("Flagship and Diffsky median sizes differ by at least a factor of two")
    except (ValueError, OSError, AssertionError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
