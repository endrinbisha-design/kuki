"""Regime-weighting add-on (advisory prior). See models/regime_weighting.py."""
import numpy as np

from central_park_tmax.models.regime_weighting import (blend_with_model, classify_regime,
                                                       DEFAULT_WEIGHTS)


def test_storm_regime_from_high_pop_trusts_nbm():
    # Jul 21 live: NBM 78, HRRR 84, GFS 85, PoP 100 -> storm, weighted toward cool NBM.
    a = classify_regime(78, 84, 85, pop_pct=100)
    assert a.regime == "storm_convective"
    assert a.weights["nbm"] > a.weights["hrrr"]
    assert a.weighted_tmax_f < 82        # pulled well below the raw high-res 84-85


def test_clean_regime_from_low_pop_respects_highres():
    # Jul 22 live: NBM 83, HRRR 85, GFS 84, PoP 20 (dry) -> clean, lean warm even though
    # NBM is cooler than high-res (the setup where NBM is too conservative).
    a = classify_regime(83, 85, 84, pop_pct=20)
    assert a.regime == "clean_warm"
    assert a.weights["hrrr"] + a.weights["gfs"] > a.weights["nbm"]
    assert a.weighted_tmax_f > 83.5      # warmer than NBM's 83


def test_moisture_sets_direction_not_model_gap():
    # NBM cooler than high-res, but DRY -> still clean_warm (gap sets magnitude, not direction).
    assert classify_regime(80, 85, 85, pop_pct=10).regime == "clean_warm"
    # Same model gap but WET -> storm.
    assert classify_regime(80, 85, 85, pop_pct=90).regime == "storm_convective"


def test_neutral_between_thresholds():
    assert classify_regime(84, 84.5, 83.5, pop_pct=35).regime == "neutral"


def test_nbm_only_fallback_uses_model_gap():
    # No PoP/cloud, NBM much cooler than high-res -> lean storm (historical signature).
    assert classify_regime(80, 86, 86, pop_pct=None).regime == "storm_convective"
    # No PoP and models agree -> neutral (no signal).
    assert classify_regime(84, 84, 84, pop_pct=None).regime == "neutral"


def test_blend_strength_bounds():
    a = classify_regime(78, 84, 85, pop_pct=100)   # weighted ~80.6
    model_point = 83.0
    assert blend_with_model(model_point, a, strength=0.0) == model_point   # pure model
    assert abs(blend_with_model(model_point, a, strength=1.0) - a.weighted_tmax_f) < 1e-9
    mid = blend_with_model(model_point, a, strength=0.5)
    assert min(model_point, a.weighted_tmax_f) < mid < max(model_point, a.weighted_tmax_f)


def test_weighted_estimate_handles_missing_sources():
    a = classify_regime(83, None, None, pop_pct=80)   # nbm only
    assert a.weighted_tmax_f == 83.0                  # only source available
    assert a.regime == "storm_convective"


def test_to_dict_shape():
    d = classify_regime(83, 85, 84, pop_pct=20).to_dict()
    for k in ("regime", "regime_suppression_score", "regime_weights",
              "regime_weighted_tmax_f", "regime_rationale"):
        assert k in d
