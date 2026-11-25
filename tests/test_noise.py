"""Check the installed noise model, strict cuts, and validation statistics."""

import numpy as np
import pandas as pd
import pytest

from manifoldcloud.catalogue.noise import NoiseSummary, add_noise, check_noise, make_noise_model


def _catalogue(magnitudes):
    n = len(magnitudes)
    return pd.DataFrame({
        **{f"mag_{band}": np.asarray(magnitudes, dtype="float32") for band in "ugrizy"},
        "a_hl": np.full(n, 0.3, dtype="float32"), "b_hl": np.full(n, 0.2, dtype="float32"),
        "gal_id": np.arange(120, 120 + n),
    }, index=np.arange(201, 201 + n))


def test_installed_rubin_year1_model_and_reproducible_measurements():
    model = make_noise_model()
    params = model.params
    assert params.nYrObs == 1
    assert params.extendedType == "auto"
    assert (params.majorCol, params.minorCol) == ("a_hl", "b_hl")
    assert params.sigLim == 0
    assert np.isnan(params.ndFlag)
    assert params.decorrelate
    assert set(params.nVisYr) == {f"mag_{band}" for band in "ugrizy"}

    truth = _catalogue(np.linspace(23.95, 24.24, 200))
    first = add_noise(truth, random_state=42, model=model)
    second = add_noise(truth, random_state=np.random.default_rng(42))
    pd.testing.assert_frame_equal(first, second)
    pd.testing.assert_frame_equal(first[truth.columns], truth)
    assert first["sample"].dtype == bool
    assert first["control_sample"].dtype == bool
    for band in "ugrizy":
        assert first[f"mag_{band}_obs"].dtype == np.float32
        assert first[f"mag_{band}_err"].dtype == np.float32
        assert first[f"mag_{band}_err"].notna().any()
    other = add_noise(truth, random_state=43, model=model)
    assert not first["mag_i_obs"].equals(other["mag_i_obs"])

    empty = add_noise(truth.iloc[:0], random_state=42, model=model)
    assert empty.empty
    assert empty.dtypes.equals(first.dtypes)


def test_sample_and_control_use_their_own_strict_cuts():
    truth = _catalogue([23.9, 24.1, 24.2, 24.09, 25.6, 25.5])

    def measurements(frame, *, random_state):
        assert random_state == 42
        observed = frame.copy()
        observed["mag_i"] = [24.1, 24.09, np.nan, -np.inf, 23.9, np.inf]
        for band in "ugrizy":
            observed[f"mag_{band}_err"] = 0.17
        return observed

    result = add_noise(truth, random_state=42, model=measurements)
    assert result["sample"].tolist() == [False, True, False, False, True, False]
    assert result["control_sample"].tolist() == [True, False, False, True, False, False]
    stricter = add_noise(truth, random_state=42, model=measurements, i_limit=23.95)
    assert stricter["sample"].tolist() == [False, False, False, False, True, False]
    assert stricter["control_sample"].tolist() == [True, False, False, False, False, False]


def test_summary_uses_exact_median_and_fractions_from_all_batches():
    truth = _catalogue([24.0, 24.01, 24.1, 24.19, 24.2, 25.5, 25.6, 24.05])
    table = truth.assign(
        mag_i_err=np.asarray([0.9, 0.1, 0.2, 0.3, 0.9, 0.9, 0.9, np.inf], dtype="float32"),
        sample=[True, False, True, True, False, True, True, False],
        control_sample=truth["mag_i"].lt(24.1),
    )
    summary = NoiseSummary()
    summary.add(table.iloc[:3])
    summary.add(table.iloc[3:])
    assert summary.result() == pytest.approx({
        "rows": 8, "science_rows": 5, "control_rows": 3, "i_error_rows": 3, "median_i_error": 0.2,
        "science_true_i_gt_25_5_rows": 1, "science_true_i_gt_25_5_fraction": 0.2,
        "science_true_i_gt_cut_rows": 3, "science_true_i_gt_cut_fraction": 0.6, "i_limit": 24.1,
    })


def test_noise_gates_reject_undefined_errors_and_faint_tail_at_limit():
    check_noise({"median_i_error": 0.10, "science_true_i_gt_25_5_fraction": 0.004999})
    check_noise({"median_i_error": 0.25, "science_true_i_gt_25_5_fraction": 0.0})
    with pytest.raises(ValueError, match="Median i-band error"):
        check_noise({"median_i_error": 0.26, "science_true_i_gt_25_5_fraction": 0.0})
    with pytest.raises(ValueError, match="requires below 0.5%"):
        check_noise({"median_i_error": 0.17, "science_true_i_gt_25_5_fraction": 0.005})
    empty = NoiseSummary().result()
    assert empty["median_i_error"] is None
    assert empty["science_true_i_gt_25_5_fraction"] is None
    with pytest.raises(ValueError, match="undefined"):
        check_noise(empty)
