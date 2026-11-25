"""Apply Rubin Year 1 photometric errors and check the resulting sample."""

import numpy as np
from photerr import LsstErrorModel

from manifoldcloud.catalogue.harmonise import BANDS, MAG_COLUMNS


def make_noise_model():
    """Build the photerr 1.6 extended-source model for harmonised magnitudes."""
    return LsstErrorModel(
        nYrObs=1, extendedType="auto", majorCol="a_hl", minorCol="b_hl",
        sigLim=0, ndFlag=np.nan, decorrelate=True,
        renameDict={band: f"mag_{band}" for band in BANDS},
    )


def add_noise(table, *, random_state, model=None, i_limit=24.1):
    """Add observed magnitudes, errors and both selection flags without replacing truth."""
    model = make_noise_model() if model is None else model
    measurements = model(table[[*MAG_COLUMNS, "a_hl", "b_hl"]], random_state=random_state)
    columns = {}
    for column in MAG_COLUMNS:
        columns[f"{column}_obs"] = measurements[column].astype("float32")
        columns[f"{column}_err"] = measurements[f"{column}_err"].astype("float32")
    observed_i = columns["mag_i_obs"]
    columns["sample"] = np.isfinite(observed_i) & observed_i.lt(i_limit)
    columns["control_sample"] = table["mag_i"].lt(i_limit)
    return table.assign(**columns)


class NoiseSummary:
    """Accumulate row counts and retain only errors needed for an exact median."""

    def __init__(self, i_limit=24.1):
        self.i_limit = i_limit
        self.rows = 0
        self.science_rows = 0
        self.control_rows = 0
        self.faint_science_rows = 0
        self.crossed_cut_rows = 0
        self.errors_at_limit = []

    def add(self, noisy_table):
        """Accumulate one batch of the full table, including unselected rows."""
        true_i = noisy_table["mag_i"]
        science = noisy_table["sample"]
        errors = noisy_table["mag_i_err"]
        self.rows += len(noisy_table)
        self.science_rows += int(science.sum())
        self.control_rows += int(noisy_table["control_sample"].sum())
        self.faint_science_rows += int((science & true_i.gt(25.5)).sum())
        self.crossed_cut_rows += int((science & true_i.gt(self.i_limit)).sum())
        at_limit = true_i.gt(24.0) & true_i.lt(24.2) & np.isfinite(errors)
        if at_limit.any():
            self.errors_at_limit.append(errors[at_limit].to_numpy(dtype=np.float64, copy=True))

    def result(self):
        """Return a JSON-compatible report, with missing measurements as None."""
        errors = np.concatenate(self.errors_at_limit) if self.errors_at_limit else np.empty(0)
        return {
            "rows": self.rows,
            "science_rows": self.science_rows,
            "control_rows": self.control_rows,
            "i_error_rows": len(errors),
            "median_i_error": float(np.median(errors)) if len(errors) else None,
            "science_true_i_gt_25_5_rows": self.faint_science_rows,
            "science_true_i_gt_25_5_fraction": self.faint_science_rows / self.science_rows if self.science_rows else None,
            "science_true_i_gt_cut_rows": self.crossed_cut_rows,
            "science_true_i_gt_cut_fraction": self.crossed_cut_rows / self.science_rows if self.science_rows else None,
            "i_limit": self.i_limit,
        }


def check_noise(summary):
    """Raise if the i-band error or the faint scattering tail misses its gate."""
    median = summary["median_i_error"]
    tail = summary["science_true_i_gt_25_5_fraction"]
    problems = []
    if median is None or not 0.10 <= median <= 0.25:
        label = "undefined" if median is None else f"{median:.6f} mag"
        problems.append(f"Median i-band error {label} is outside 0.10–0.25 mag")
    if tail is None or not tail < 0.005:
        label = "undefined" if tail is None else f"{tail:.6%}"
        problems.append(f"Science sample share with noiseless i > 25.5 is {label} (requires below 0.5%)")
    if problems:
        raise ValueError(". ".join(problems))
