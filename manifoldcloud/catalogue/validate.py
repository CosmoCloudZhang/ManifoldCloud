"""Summarise harmonised catalogues and check Diffsky's raw depth measurements."""

from math import isfinite
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb
import h5py
import numpy as np
from speclite.filters import load_filter


COLOURS = ("u-g", "g-r", "r-i", "i-z", "z-y")
DEPTH_REFERENCE = {
    442: ((0.10, 0.13), (22.0, 22.5), 63.0),
    392: ((0.24, 0.27), (24.5, 25.0), 1.4),
    300: ((0.62, 0.66), (26.5, 27.0), 0.0),
}
DEPTH_TOLERANCE_PP = 2.0


def _records(connection, sql, parameters=()):
    cursor = connection.execute(sql, parameters)
    names = [field[0] for field in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def _summarise(connection, area_deg2, i_limit):
    counts = _records(connection, """
        SELECT count(*) AS rows,
               count(*) FILTER (WHERE isfinite(mag_i) AND mag_i < cast_to_type(?, mag_i)) AS year1,
               count(*) FILTER (WHERE isfinite(mag_i) AND mag_i < cast_to_type(25.3, mag_i)) AS depth_25_3
        FROM catalogue
    """, [i_limit])[0]
    number_counts = _records(connection, """
        SELECT floor(mag_i * 2) / 2.0 AS mag_lo, count(*) AS count
        FROM catalogue WHERE isfinite(mag_i)
        GROUP BY mag_lo ORDER BY mag_lo
    """)
    for row in number_counts:
        row["per_deg2"] = row["count"] / area_deg2

    redshifts = _records(connection, """
        SELECT CAST(floor(z_true * 10) AS DOUBLE) / 10.0 AS z_lo, count(*) AS count
        FROM catalogue
        WHERE isfinite(z_true) AND isfinite(mag_i) AND mag_i < cast_to_type(?, mag_i)
        GROUP BY z_lo ORDER BY z_lo
    """, [i_limit])
    colour_expressions = []
    for name in COLOURS:
        blue, red = (f"mag_{band}" for band in name.split("-"))
        colour_expressions.append(
            f'median(CASE WHEN isfinite({blue}) AND isfinite({red}) '
            f'THEN CAST({blue} AS DOUBLE) - {red} END) AS "{name}"'
        )
    colours = _records(connection, f"""
        SELECT CAST(floor(z_true * 10) AS DOUBLE) / 10.0 AS z_lo, {', '.join(colour_expressions)}
        FROM catalogue WHERE isfinite(z_true)
        GROUP BY z_lo ORDER BY z_lo
    """)
    sizes = _records(connection, """
        SELECT floor(mag_i * 2) / 2.0 AS mag_lo, median(a_hl) AS median_a_hl
        FROM catalogue WHERE isfinite(mag_i) AND isfinite(a_hl)
        GROUP BY mag_lo ORDER BY mag_lo
    """)
    i_label = str(float(i_limit)).replace(".", "_")
    return {"rows": counts["rows"], "totals": {
        f"i_lt_{i_label}": counts["year1"], "i_lt_25_3": counts["depth_25_3"],
    }, "number_counts": number_counts, "redshift_distribution": redshifts,
        "colours": colours, "sizes": sizes}


def summarise_catalogue(paths, *, area_deg2, i_limit=24.1, temp_directory=None):
    """Return counts and exact medians from local Parquet projections and aggregates."""
    paths = [Path(path).resolve(strict=True) for path in paths]
    if not paths:
        raise ValueError("Supply at least one harmonised Parquet file")
    if not isfinite(area_deg2) or area_deg2 <= 0 or not isfinite(i_limit):
        raise ValueError("The catalogue area must be positive and the magnitude limit finite")
    parent = paths[0].parent if temp_directory is None else Path(temp_directory)
    with TemporaryDirectory(prefix=".validation-", dir=parent) as scratch:
        with duckdb.connect(config={"memory_limit": "1GB", "threads": "2",
                                   "temp_directory": scratch}) as connection:
            catalogue = connection.read_parquet([str(path) for path in paths])
            catalogue.project("z_true, mag_u, mag_g, mag_r, mag_i, mag_z, mag_y, a_hl").create_view("catalogue")
            return _summarise(connection, area_deg2, i_limit)


def diffsky_depth(manifest):
    """Compare pre-cut Diffsky measurements with the plan's three reference shells."""
    files = manifest.get("files", {})
    rows = []
    for step, (reference_z, reference_peak, reference_percent) in DEPTH_REFERENCE.items():
        details = files.get(f"shell_{step}.parquet", {}).get("details", {})
        depth = details.get("depth")
        row = {"step": step, "status": "missing", "reference_z_range": list(reference_z),
               "expected_mag_bin_peak": list(reference_peak),
               "expected_floor_halo_bright_percent": reference_percent}
        if depth:
            floor, bright = depth.get("floor_halo_rows"), depth.get("floor_halo_bright_rows")
            percent = 100.0 * bright / floor if floor and bright is not None and 0 <= bright <= floor else None
            delta = abs(percent - reference_percent) if percent is not None else None
            peak = depth.get("mag_bin_peak")
            passed = peak == list(reference_peak) and delta is not None and delta <= DEPTH_TOLERANCE_PP
            row.update({"status": "passed" if passed else "failed", "z_range": details.get("z_range"),
                        "mag_bin_peak": peak, "floor_halo_rows": floor, "floor_halo_bright_rows": bright,
                        "floor_halo_bright_percent": percent, "difference_percentage_points": delta})
        rows.append(row)
    return {"passed": all(row["status"] == "passed" for row in rows), "rows": rows}


def compare_filter_curves(path):
    """Compare all six Diffsky throughput grids against the matching lsst2023 curves."""
    results = {}
    with h5py.File(path, "r") as file:
        for band in "ugrizy":
            try:
                group = file[f"lsst_{band}"]
                wave, throughput = group["wave"][:], group["transmission"][:]
            except KeyError as error:
                raise ValueError(f"Diffsky {band} filter is missing its wavelength or transmission") from error
            reference = load_filter(f"lsst2023-{band}")
            if (wave.ndim != 1 or wave.shape != throughput.shape or len(wave) < 2
                    or not np.isfinite(wave).all() or not np.isfinite(throughput).all()
                    or not np.allclose(np.diff(wave), 1.0, rtol=0, atol=1e-7)
                    or wave[0] > reference.wavelength[0] + 1e-7
                    or wave[-1] < reference.wavelength[-1] - 1e-7):
                raise ValueError(f"Diffsky {band} filter has an incompatible wavelength grid")
            # The source grids have floating-point wavelength offsets and different zero-padding.
            expected = np.interp(wave, reference.wavelength, reference.response, left=0.0, right=0.0)
            deviation = float(np.max(np.abs(throughput - expected)))
            if deviation > 1e-12:
                raise ValueError(f"Diffsky {band} filter differs from lsst2023 (max difference {deviation:.3g})")
            results[band] = {"samples": len(wave), "max_absolute_difference": deviation, "match": True}
    return results
