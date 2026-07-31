"""Post-hoc contract-probability calibration (models/contract_calibration.py)."""
from central_park_tmax.models.contract_calibration import (calibrate_contract_set,
                                                           calibrate_probability,
                                                           calibration_report, exhaustive,
                                                           has_calibration,
                                                           resolution_warning)

# The live 2026-07-31 KNYC board that exposed the renormalisation bug.
LIVE_NYC = {"<=81": 0.089, "82-83": 0.407, "84-85": 0.324,
            "86-87": 0.122, "88-89": 0.035, ">=90": 0.023}


def test_curve_is_available_for_the_three_cities():
    assert has_calibration("KNYC") and has_calibration("KPHX") and has_calibration("KLAS")
    assert not has_calibration("KDEN")


def test_unknown_station_passes_probabilities_through():
    assert calibrate_probability("KDEN", 0.37) == 0.37


def test_calibration_lifts_the_underconfident_low_tail():
    # Measured defect: raw ~6% corresponds to a realised ~20%.
    assert calibrate_probability("KNYC", 0.06) > 0.12


def test_naive_calibration_does_not_sum_to_one():
    """The whole reason this module exists: per-contract calibration breaks the partition."""
    rep = calibration_report("KNYC", LIVE_NYC)
    assert rep["uncalibrated_total"] > 1.5          # measured 1.835 live
    assert abs(sum(rep["calibrated"].values()) - 1.0) < 1e-9


def test_renormalised_set_is_a_distribution_and_flattens_the_peak():
    cal = calibrate_contract_set("KNYC", LIVE_NYC)
    assert abs(sum(cal.values()) - 1.0) < 1e-9
    assert all(0.0 <= v <= 1.0 for v in cal.values())
    # Correcting overconfidence must pull the modal bucket DOWN.
    assert cal["82-83"] < LIVE_NYC["82-83"]


def test_resolution_loss_is_reported():
    rep = calibration_report("KNYC", LIVE_NYC)
    assert rep["distinct_calibrated_values"] < rep["n_contracts"]
    assert "not distinguishable" in (resolution_warning(rep) or "")


def test_empty_and_degenerate_inputs():
    assert calibrate_contract_set("KNYC", {}) == {}
    flat = calibrate_contract_set("KNYC", {"a": 0.0, "b": 0.0})
    assert abs(sum(flat.values()) - 1.0) < 1e-9


def test_exhaustive_helper():
    assert exhaustive(list(LIVE_NYC.values()))
    assert not exhaustive([0.2, 0.3])
