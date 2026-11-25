"""Test angular conversion, component geometry and flux-weighted sizes."""

from astropy.cosmology import FlatLambdaCDM
import numpy as np
import pytest

from manifoldcloud.sizes import bulge_flux_fraction, combine_axes, diffsky_axes, to_arcsec

COSMOLOGY = FlatLambdaCDM(H0=67.66, Om0=0.3096446816)


def test_to_arcsec_at_repeated_redshift():
    redshift = [0.2, 0.2, 0.7]
    result = to_arcsec([1.0, 2.0, 1.0], redshift, COSMOLOGY)
    expected = 206264.806 * np.array([1.0, 2.0, 1.0]) / COSMOLOGY.angular_diameter_distance(redshift).to_value("kpc")
    np.testing.assert_allclose(result, expected, rtol=1e-12)
    assert result[1] == 2 * result[0]
    assert to_arcsec([], [], COSMOLOGY).size == 0


@pytest.mark.parametrize("z", [0.0, -0.1, np.nan, np.inf])
def test_to_arcsec_rejects_invalid_redshift(z):
    with pytest.raises(ValueError, match="positive finite true redshift"):
        to_arcsec(1.0, z, COSMOLOGY)


def test_diffsky_axes_preserve_projected_ratio_and_zero_component():
    major, minor = diffsky_axes([2.0, 3.0, 0.0], [4.0, 6.0, 0.0], [2.0, 1.0, 0.0], 0.5, COSMOLOGY)
    np.testing.assert_allclose(major[:2] / minor[:2], [2.0, 6.0], rtol=1e-12)
    assert major[2] == minor[2] == 0.0
    with pytest.raises(ValueError, match="Diffsky axes"):
        diffsky_axes(1.0, 0.0, 0.0, 0.5, COSMOLOGY)


def test_combine_axes_with_bulge_only_and_unused_sentinel():
    major, minor = combine_axes(
        [4.0, np.nan, 3.0], [2.0, -99.0, 1.5], [2.0, 1.0, np.nan], [1.0, 0.6, -99.0],
        [0.25, np.nan, 0.0], bulge_only=[False, True, False],
    )
    np.testing.assert_allclose(major, [np.sqrt(13.0), 1.0, 3.0], rtol=1e-12)
    np.testing.assert_allclose(minor, [np.sqrt(3.25), 0.6, 1.5], rtol=1e-12)
    with pytest.raises(ValueError, match="Contributing component axes"):
        combine_axes(1.0, 2.0, 1.0, 0.5, 0.5)
    with pytest.raises(ValueError, match="Bulge flux fractions"):
        combine_axes(1.0, 0.5, 1.0, 0.5, 1.1)


def test_bulge_flux_fraction_uses_knots_and_absent_components():
    fractions = bulge_flux_fraction([20, 80, np.inf], [22.5, 80, 20], [22.5, np.inf, 22.5])
    np.testing.assert_allclose(fractions, [1 / 1.2, 0.5, 0.0], rtol=1e-12)
    for invalid in (np.nan, -np.inf):
        with pytest.raises(ValueError, match="Component magnitudes"):
            bulge_flux_fraction(invalid, 20, 22)
    with pytest.raises(ValueError, match="Component magnitudes"):
        bulge_flux_fraction(np.inf, np.inf, np.inf)
