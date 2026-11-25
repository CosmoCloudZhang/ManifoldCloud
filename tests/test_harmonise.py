"""Check the common galaxy schema using both complete synthetic raw schemas."""

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from astropy.cosmology import FlatLambdaCDM

from manifoldcloud.core.config import load
from manifoldcloud.catalogue.harmonise import (
    HARMONISED_SCHEMA, harmonise_diffsky, harmonise_flagship, validate_harmonised,
)


CONFIG = load()
COSMOLOGY = FlatLambdaCDM(H0=CONFIG.diffsky.h0, Om0=CONFIG.diffsky.omega_m)
SCHEMA_FIELDS = {
    "gal_id": pa.int64(), "ra": pa.float64(), "dec": pa.float64(),
    **{column: pa.float32() for column in (
        "z_true", "z_obs", "mag_u", "mag_g", "mag_r", "mag_i", "mag_z", "mag_y",
        "a_disk", "b_disk", "a_bulge", "b_bulge", "bulge_frac", "a_hl", "b_hl", "log_mstar",
    )},
    "is_central": pa.bool_(), "is_synthetic": pa.bool_(),
    "p_merge": pa.float32(), "random_index": pa.float32(),
}


@pytest.fixture
def raw_catalogues():
    flagship = pd.DataFrame({column: [1, 1] for column in CONFIG.flagship.columns}, index=[9, 12])
    flagship = flagship.assign(
        galaxy_id=[120, 121], kind=[0, 1], random_index=[0.12, 0.34],
        ra_gal=[230.0, 230.2], dec_gal=[25.0, 25.1], true_redshift_gal=[0.32, 0.35],
        observed_redshift_gal=[0.321, 0.351], dominant_shape=[1, 0], bulge_fraction=[0.3, 0.2],
        disk_r50=[0.5, np.nan], disk_axis_ratio=[0.8, np.nan],
        bulge_r50=[0.25, 0.55], bulge_axis_ratio=[0.6, 0.7], log_stellar_mass=[9.1, 9.6],
    )
    for offset, band in enumerate("ugrizy"):
        magnitudes = np.array([23.85, 24.05]) + 0.05 * offset
        flagship[f"lsst_{band}_el_model3_ext"] = 10 ** (-0.4 * (magnitudes + 48.6))

    diffsky = pd.DataFrame({column: [1, 1] for column in CONFIG.diffsky.columns}, index=[4, 7])
    diffsky = diffsky.assign(
        gal_id=[-4, 2 ** 60], central=[1, 0], lc_patch=[843, 843], ra=[230.0, 230.2], dec=[-25.0, -25.1],
        redshift_true=[0.32, 0.35], redshift_obs=[0.319, 0.349], r50_disk_2d=[2.0, 2.5],
        alpha_disk=[3.0, 4.0], beta_disk=[2.4, 2.0], r50_bulge_2d=[1.0, 1.3],
        alpha_bulge=[1.5, 2.0], beta_bulge=[0.9, 1.8], bulge_to_total=[0.9, 0.8],
        lsst_i_bulge_unlensed=[24.0, 22.0], lsst_i_disk_unlensed=[24.0, 23.0],
        lsst_i_knots_unlensed=[24.0, 24.0], logsm_obs=[9.0, 9.5], p_merge=[0.1, 0.4],
        is_synthetic=[False, True], step=[392, 392],
    )
    for offset, band in enumerate("ugrizy"):
        diffsky[f"lsst_{band}_unlensed"] = np.array([23.9, 24.1]) + 0.05 * offset
    return flagship, diffsky


def test_harmonised_schema_and_size_rule_survive_parquet(tmp_path, raw_catalogues):
    flagship, diffsky = raw_catalogues
    expected = pa.schema(list(SCHEMA_FIELDS.items()), metadata={"size_rule": "flux_weighted_quadrature"})
    assert HARMONISED_SCHEMA.equals(expected, check_metadata=True)
    for name, result in (
        ("flagship", harmonise_flagship(flagship)), ("diffsky", harmonise_diffsky(diffsky, COSMOLOGY)),
    ):
        validate_harmonised(result)
        path = tmp_path / f"{name}.parquet"
        arrow = pa.Table.from_pandas(result, schema=HARMONISED_SCHEMA, preserve_index=False)
        pq.write_table(arrow, path)
        checked = pq.read_table(path)
        validate_harmonised(checked)
        assert checked.schema.equals(expected, check_metadata=False)
        assert checked.schema.metadata[b"size_rule"] == b"flux_weighted_quadrature"


def test_flagship_flux_round_trip_and_bulge_only_sizes(raw_catalogues):
    flagship, _ = raw_catalogues
    result = harmonise_flagship(flagship)
    assert list(result.index) == list(flagship.index)
    for band in "ugrizy":
        round_trip = 10 ** (-0.4 * (result[f"mag_{band}"].to_numpy(dtype=np.float64) + 48.6))
        np.testing.assert_allclose(round_trip, flagship[f"lsst_{band}_el_model3_ext"], rtol=2e-6, atol=0)
    assert result["is_central"].tolist() == [True, False]
    assert not result["is_synthetic"].any()
    assert result["p_merge"].isna().all()
    np.testing.assert_allclose(result["random_index"], flagship["random_index"])
    np.testing.assert_allclose(result["log_mstar"], flagship["log_stellar_mass"] - 2 * np.log10(0.67))
    np.testing.assert_allclose(result["a_hl"], [np.sqrt(0.3 * 0.25 ** 2 + 0.7 * 0.5 ** 2), 0.55])
    np.testing.assert_allclose(result["b_hl"], [np.sqrt(0.3 * 0.15 ** 2 + 0.7 * 0.4 ** 2), 0.55 * 0.7])


def test_diffsky_sizes_flux_share_and_stable_hash(raw_catalogues):
    flagship, diffsky = raw_catalogues
    result = harmonise_diffsky(diffsky, COSMOLOGY)
    assert list(result.index) == list(diffsky.index)
    np.testing.assert_array_equal(result["gal_id"], diffsky["gal_id"])
    np.testing.assert_allclose(result["a_disk"] / result["b_disk"], diffsky["alpha_disk"] / diffsky["beta_disk"])
    np.testing.assert_allclose(result["a_bulge"] / result["b_bulge"], diffsky["alpha_bulge"] / diffsky["beta_bulge"])
    second_share = 1 / (1 + 10 ** (-0.4) + 10 ** (-0.8))
    np.testing.assert_allclose(result["bulge_frac"], [1 / 3, second_share])
    np.testing.assert_allclose(result["mag_i"], diffsky["lsst_i_unlensed"])
    np.testing.assert_allclose(result["log_mstar"], diffsky["logsm_obs"])
    np.testing.assert_allclose(result["p_merge"], diffsky["p_merge"])
    assert result["is_central"].tolist() == [True, False]
    assert result["is_synthetic"].tolist() == [False, True]

    random = result["random_index"]
    assert (random >= 0).all() and (random < 1).all()
    assert random.nunique() == 2
    shuffled = harmonise_diffsky(diffsky.iloc[::-1], COSMOLOGY)
    pd.testing.assert_series_equal(shuffled["random_index"].sort_index(), random)

    converted = harmonise_flagship(flagship)
    medians = [catalogue.loc[catalogue["mag_i"].between(23.5, 24.5), "a_hl"].median()
               for catalogue in (converted, result)]
    assert all(0.1 < median < 1.0 for median in medians)
    assert max(medians) / min(medians) < 2


def test_validation_rejects_missing_schema_nonfinite_values_and_reversed_axes(raw_catalogues):
    _, diffsky = raw_catalogues
    result = harmonise_diffsky(diffsky, COSMOLOGY)
    with pytest.raises(ValueError, match="schema"):
        validate_harmonised(result.drop(columns="random_index"))
    arrow = pa.Table.from_pandas(result, schema=HARMONISED_SCHEMA, preserve_index=False)
    with pytest.raises(ValueError, match="size_rule"):
        validate_harmonised(arrow.replace_schema_metadata(None))

    result.loc[4, "mag_i"] = np.inf
    with pytest.raises(ValueError, match="Nonfinite.*mag_i"):
        validate_harmonised(result)
    result.loc[4, "mag_i"] = np.float32(24.0)
    result.loc[4, "b_hl"] = np.float32(2.0)
    with pytest.raises(ValueError, match="minor axis exceeds"):
        validate_harmonised(result)


def test_empty_raw_shell_retains_harmonised_schema(raw_catalogues):
    _, diffsky = raw_catalogues
    result = harmonise_diffsky(diffsky.iloc[0:0], COSMOLOGY)
    assert result.empty
    validate_harmonised(result)
