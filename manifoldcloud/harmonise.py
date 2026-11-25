"""Convert raw Flagship and Diffsky galaxies to a shared typed schema."""

import numpy as np
import pandas as pd
import pyarrow as pa

from manifoldcloud.sizes import SIZE_RULE, bulge_flux_fraction, combine_axes, diffsky_axes


BANDS = tuple("ugrizy")
MAG_COLUMNS = [f"mag_{band}" for band in BANDS]
HARMONISED_SCHEMA = pa.schema([
    ("gal_id", pa.int64()),
    ("ra", pa.float64()), ("dec", pa.float64()),
    ("z_true", pa.float32()), ("z_obs", pa.float32()),
    *((column, pa.float32()) for column in MAG_COLUMNS),
    ("a_disk", pa.float32()), ("b_disk", pa.float32()),
    ("a_bulge", pa.float32()), ("b_bulge", pa.float32()),
    ("bulge_frac", pa.float32()), ("a_hl", pa.float32()), ("b_hl", pa.float32()),
    ("log_mstar", pa.float32()), ("is_central", pa.bool_()), ("is_synthetic", pa.bool_()),
    ("p_merge", pa.float32()), ("random_index", pa.float32()),
], metadata={"size_rule": SIZE_RULE})
_DTYPES = {field.name: field.type.to_pandas_dtype() for field in HARMONISED_SCHEMA}
_FINITE_COLUMNS = [*MAG_COLUMNS, "z_true", "a_hl", "b_hl"]


def _frame(raw, values):
    return pd.DataFrame(values, index=raw.index, columns=HARMONISED_SCHEMA.names).astype(_DTYPES)


def _random_index(gal_id):
    # SplitMix64 followed by the top 24 bits, an exactly representable float32 in [0, 1).
    hashed = np.asarray(gal_id, dtype=np.int64).view(np.uint64).copy()
    hashed += np.uint64(0x9E3779B97F4A7C15)
    hashed = (hashed ^ (hashed >> 30)) * np.uint64(0xBF58476D1CE4E5B9)
    hashed = (hashed ^ (hashed >> 27)) * np.uint64(0x94D049BB133111EB)
    hashed ^= hashed >> 31
    return (hashed >> 40).astype(np.float32) * np.float32(2.0 ** -24)


def _ab_magnitude(flux):
    with np.errstate(divide="ignore", invalid="ignore"):
        return -2.5 * np.log10(np.asarray(flux, dtype=np.float64)) - 48.6


def harmonise_flagship(raw, h=0.67):
    """Convert cgs Flagship fluxes, radii and h-scaled stellar masses."""
    a_disk, a_bulge = raw["disk_r50"], raw["bulge_r50"]
    b_disk = a_disk * raw["disk_axis_ratio"]
    b_bulge = a_bulge * raw["bulge_axis_ratio"]
    fraction = raw["bulge_fraction"]
    a_hl, b_hl = combine_axes(a_disk, b_disk, a_bulge, b_bulge, fraction,
                               bulge_only=raw["dominant_shape"].eq(0))
    return _frame(raw, {
        "gal_id": raw["galaxy_id"], "ra": raw["ra_gal"], "dec": raw["dec_gal"],
        "z_true": raw["true_redshift_gal"], "z_obs": raw["observed_redshift_gal"],
        **{f"mag_{band}": _ab_magnitude(raw[f"lsst_{band}_el_model3_ext"]) for band in BANDS},
        "a_disk": a_disk, "b_disk": b_disk, "a_bulge": a_bulge, "b_bulge": b_bulge,
        "bulge_frac": fraction, "a_hl": a_hl, "b_hl": b_hl,
        "log_mstar": raw["log_stellar_mass"] - 2 * np.log10(h),
        "is_central": raw["kind"].eq(0), "is_synthetic": False,
        "p_merge": np.nan, "random_index": raw["random_index"],
    })


def harmonise_diffsky(raw, cosmology):
    """Convert one Diffsky shell, using its intrinsic magnitudes and flux-weighted sizes."""
    redshift = raw["redshift_true"]
    a_disk, b_disk = diffsky_axes(raw["r50_disk_2d"], raw["alpha_disk"], raw["beta_disk"], redshift, cosmology)
    a_bulge, b_bulge = diffsky_axes(raw["r50_bulge_2d"], raw["alpha_bulge"], raw["beta_bulge"], redshift, cosmology)
    fraction = bulge_flux_fraction(raw["lsst_i_bulge_unlensed"], raw["lsst_i_disk_unlensed"],
                                  raw["lsst_i_knots_unlensed"])
    a_hl, b_hl = combine_axes(a_disk, b_disk, a_bulge, b_bulge, fraction)
    return _frame(raw, {
        "gal_id": raw["gal_id"], "ra": raw["ra"], "dec": raw["dec"],
        "z_true": redshift, "z_obs": raw["redshift_obs"],
        **{f"mag_{band}": raw[f"lsst_{band}_unlensed"] for band in BANDS},
        "a_disk": a_disk, "b_disk": b_disk, "a_bulge": a_bulge, "b_bulge": b_bulge,
        "bulge_frac": fraction, "a_hl": a_hl, "b_hl": b_hl,
        "log_mstar": raw["logsm_obs"], "is_central": raw["central"].eq(1),
        "is_synthetic": raw["is_synthetic"], "p_merge": raw["p_merge"],
        "random_index": _random_index(raw["gal_id"]),
    })


def validate_harmonised(table):
    """Raise if the schema, finite photometry and sizes, or axis order are invalid."""
    if isinstance(table, pd.DataFrame):
        schema = pa.Schema.from_pandas(table, preserve_index=False)
    else:
        schema = table.schema
        if (schema.metadata or {}).get(b"size_rule") != SIZE_RULE.encode():
            raise ValueError("The harmonised table is missing the expected size_rule metadata")
    if not schema.equals(HARMONISED_SCHEMA, check_metadata=False):
        raise ValueError("The harmonised columns and types do not match the approved schema")

    values = table[_FINITE_COLUMNS] if isinstance(table, pd.DataFrame) else table.select(_FINITE_COLUMNS).to_pandas()
    for name in _FINITE_COLUMNS:
        if not np.isfinite(values[name]).all():
            raise ValueError(f"Nonfinite harmonised values in {name}")
    if (values["b_hl"] > values["a_hl"]).any():
        raise ValueError("A harmonised half-light minor axis exceeds its major axis")
