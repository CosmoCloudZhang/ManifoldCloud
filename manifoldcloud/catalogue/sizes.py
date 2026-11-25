"""Convert and combine projected galaxy half-light axes for photometric noise."""

import numpy as np

ARCSEC_PER_RADIAN = 206264.806
SIZE_RULE = "flux_weighted_quadrature"


def to_arcsec(kpc, redshift, cosmology):
    """Convert physical kpc to arcsec at positive, finite true redshift."""
    size = np.asarray(kpc, dtype=float)
    z = np.asarray(redshift, dtype=float)
    if np.any(~np.isfinite(size) | (size < 0)):
        raise ValueError("Physical sizes must be finite and nonnegative")
    if np.any(~np.isfinite(z) | (z <= 0)):
        raise ValueError("Angular sizes require a positive finite true redshift")
    distance = cosmology.angular_diameter_distance(z).to_value("kpc")
    return ARCSEC_PER_RADIAN * size / distance


def diffsky_axes(r50, alpha, beta, redshift, cosmology):
    """Convert Diffsky r50 and beta/alpha to half-light major and minor axes."""
    r50, alpha, beta = np.broadcast_arrays(*(np.asarray(value, dtype=float)
                                            for value in (r50, alpha, beta)))
    absent = (r50 == 0) & (alpha == 0) & (beta == 0)
    valid = np.isfinite(alpha) & np.isfinite(beta) & (alpha > 0) & (beta >= 0) & (beta <= alpha)
    if np.any(~(absent | valid)):
        raise ValueError("Diffsky axes require 0 <= beta <= alpha and positive alpha for a present component")
    ratio = np.divide(beta, alpha, out=np.zeros_like(alpha), where=~absent)
    major = to_arcsec(r50, redshift, cosmology)
    return major, major * ratio


def combine_axes(a_disk, b_disk, a_bulge, b_bulge, bulge_frac, *, bulge_only=None):
    """Combine half-light axes in quadrature using their component flux shares."""
    fraction = np.asarray(bulge_frac, dtype=float)
    if bulge_only is not None:
        fraction = np.where(bulge_only, 1.0, fraction)
    if np.any(~np.isfinite(fraction) | (fraction < 0) | (fraction > 1)):
        raise ValueError("Bulge flux fractions must be between zero and one")

    disk = _weighted_axes(a_disk, b_disk, 1 - fraction)
    bulge = _weighted_axes(a_bulge, b_bulge, fraction)
    return np.hypot(disk[0], bulge[0]), np.hypot(disk[1], bulge[1])


def _weighted_axes(major, minor, weight):
    # A sentinel for an unused component contributes zero regardless of its value.
    major = np.where(weight > 0, np.asarray(major, dtype=float), 0)
    minor = np.where(weight > 0, np.asarray(minor, dtype=float), 0)
    if np.any(~np.isfinite(major) | ~np.isfinite(minor) | (minor < 0) | (minor > major)):
        raise ValueError("Contributing component axes must be finite with 0 <= minor <= major")
    scale = np.sqrt(weight)
    return scale * major, scale * minor


def bulge_flux_fraction(mag_bulge, mag_disk, mag_knots):
    """Return the i-band bulge flux share, with knots counted as disk flux."""
    components = np.broadcast_arrays(*(np.asarray(magnitude, dtype=float)
                                      for magnitude in (mag_bulge, mag_disk, mag_knots)))
    brightest = np.minimum.reduce(components)
    if np.any(~np.isfinite(brightest)):
        raise ValueError("Component magnitudes require finite total flux and no NaN or -inf")
    # Normalize by the brightest component, so a common zero-point cancels.
    bulge, disk, knots = (10 ** (-0.4 * (magnitude - brightest)) for magnitude in components)
    return bulge / (bulge + disk + knots)
