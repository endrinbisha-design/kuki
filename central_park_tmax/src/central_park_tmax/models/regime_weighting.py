"""Regime-dependent model weighting — an OPT-IN, ADVISORY add-on (not the validated core).

Motivation (from live days, logged in track_record/): the *right* forecast source depends on
the weather regime:
  * storm / cloud-suppressed days  -> NBM (and the NWS forecaster) run cooler and verify;
    raw HRRR/GFS 2 m temperatures run too hot (they under-resolve convective cloud/rain cooling).
  * clean / sunny warm days        -> the high-res HRRR/GFS warmth verifies; NBM/NWS come in cool.

This module classifies the regime from information available at issue time (precip probability
and the NBM-vs-high-res disagreement signature) and produces a regime-weighted blend of the
raw model maxima, with fully transparent, CONFIGURABLE weights.

IMPORTANT HONESTY NOTE
----------------------
The weights are a **heuristic prior** grounded in a handful of live days + physical reasoning,
NOT a fitted/backtested model. By default this is **advisory only**: `predict` reports the
regime label and the regime-weighted estimate alongside the model output; it does not change
the point forecast unless `regime_weighting.enabled` is set. Validate against an accumulating
live record (track_record/) and a convective-day backtest before trusting it as more than a
tie-breaker. The current training archive (Aug–Jan) has few convective-stall days, which is
exactly why this lives as a documented prior rather than a learned feature.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

# Default heuristic weights per regime (source -> weight). Overridable via config.
DEFAULT_WEIGHTS = {
    "storm_convective": {"nbm": 0.60, "hrrr": 0.20, "gfs": 0.20},
    "clean_warm":       {"nbm": 0.20, "hrrr": 0.40, "gfs": 0.40},
    "neutral":          {"nbm": 0.50, "hrrr": 0.25, "gfs": 0.25},
}


@dataclass
class RegimeAssessment:
    regime: str                       # storm_convective | clean_warm | neutral
    suppression_score: float          # 0..1: higher => more convective/cloud suppression
    weights: dict[str, float]         # source -> weight actually used (only for present sources)
    weighted_tmax_f: Optional[float]  # regime-weighted blend of available model maxima
    rationale: str
    inputs: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "regime": self.regime,
            "regime_suppression_score": round(self.suppression_score, 3),
            "regime_weights": {k: round(v, 3) for k, v in self.weights.items()},
            "regime_weighted_tmax_f": (round(self.weighted_tmax_f, 2)
                                       if self.weighted_tmax_f is not None else None),
            "regime_rationale": self.rationale,
        }


def classify_regime(
    nbm_f: Optional[float],
    hrrr_f: Optional[float] = None,
    gfs_f: Optional[float] = None,
    pop_pct: Optional[float] = None,
    cloud_frac: Optional[float] = None,
    *,
    pop_storm_threshold: float = 50.0,
    nbm_cool_threshold_f: float = 2.0,
    pop_clean_threshold: float = 25.0,
    weights: Optional[dict] = None,
) -> RegimeAssessment:
    """Classify the day's regime and produce a regime-weighted blend of model maxima.

    Signals (any subset may be missing):
      * ``pop_pct``      : forecast probability of precipitation — high => suppression.
      * NBM-vs-high-res  : NBM much cooler than the HRRR/GFS mean is the convective-suppression
                           signature (NBM's post-processing suppresses; raw models don't).
      * ``cloud_frac``   : daytime cloud fraction — high => suppression.
    """
    weights = weights or DEFAULT_WEIGHTS
    highres = [v for v in (hrrr_f, gfs_f) if v is not None]
    highres_mean = float(np.mean(highres)) if highres else None
    nbm_minus_highres = (nbm_f - highres_mean) if (nbm_f is not None and highres_mean is not None) else None

    # --- suppression score components (each 0..1) ---
    comps = []
    if pop_pct is not None:
        # 0 below ~20% PoP, ramps to 1 by ~80%.
        comps.append(("pop", float(np.clip((pop_pct - 20.0) / 60.0, 0.0, 1.0))))
    if nbm_minus_highres is not None:
        # NBM cooler than high-res by nbm_cool_threshold_f => full suppression signal.
        comps.append(("nbm_cool", float(np.clip(-nbm_minus_highres / (2 * nbm_cool_threshold_f), 0.0, 1.0))))
    if cloud_frac is not None:
        comps.append(("cloud", float(np.clip((cloud_frac - 0.4) / 0.5, 0.0, 1.0))))

    suppression = float(np.mean([c for _, c in comps])) if comps else 0.0

    # --- categorical label ---
    # MOISTURE sets the direction (it is the physical suppression mechanism): a wet/cloudy day
    # suppresses the high (trust NBM/NWS); a dry/sunny day lets high-res warmth verify. The
    # NBM-vs-high-res gap only sets the *magnitude* of the bet and is used as a fallback when
    # no moisture information is available (a large NBM-cool gap has historically meant
    # suppression). We deliberately do NOT let "NBM cooler" veto a clean label on a dry day —
    # that is exactly the setup where NBM is too conservative and high-res wins.
    wet = (pop_pct is not None and pop_pct >= pop_storm_threshold) or \
          (cloud_frac is not None and cloud_frac >= 0.70)
    dry = (pop_pct is not None and pop_pct < pop_clean_threshold) or \
          (pop_pct is None and cloud_frac is not None and cloud_frac < 0.40)
    if wet:
        regime = "storm_convective"
    elif dry:
        regime = "clean_warm"
    elif pop_pct is None and cloud_frac is None and nbm_minus_highres is not None \
            and nbm_minus_highres <= -nbm_cool_threshold_f:
        # No moisture signal available, but NBM much cooler than high-res -> lean suppression.
        regime = "storm_convective"
    else:
        regime = "neutral"

    # --- regime-weighted blend over available sources ---
    src_vals = {"nbm": nbm_f, "hrrr": hrrr_f, "gfs": gfs_f}
    w = {k: weights[regime].get(k, 0.0) for k, v in src_vals.items() if v is not None}
    total = sum(w.values())
    weighted = None
    if total > 0:
        w = {k: v / total for k, v in w.items()}
        weighted = float(sum(w[k] * src_vals[k] for k in w))

    rationale = _rationale(regime, pop_pct, nbm_minus_highres, suppression)
    return RegimeAssessment(
        regime=regime, suppression_score=suppression, weights=w,
        weighted_tmax_f=weighted, rationale=rationale,
        inputs={"nbm_f": nbm_f, "hrrr_f": hrrr_f, "gfs_f": gfs_f, "pop_pct": pop_pct,
                "cloud_frac": cloud_frac, "nbm_minus_highres_f": nbm_minus_highres},
    )


def _rationale(regime: str, pop, nbm_minus_highres, suppression: float) -> str:
    if regime == "storm_convective":
        bits = []
        if pop is not None and pop >= 50:
            bits.append(f"PoP {pop:.0f}%")
        if nbm_minus_highres is not None and nbm_minus_highres <= -2:
            bits.append(f"NBM {abs(nbm_minus_highres):.1f}F cooler than high-res")
        return "suppression regime — trust NBM/NWS (" + ", ".join(bits or [f"score {suppression:.2f}"]) + ")"
    if regime == "clean_warm":
        return "clean/dry regime — respect high-res (HRRR/GFS) warmth"
    return "neutral regime — balanced weighting; defer to the ML model"


def blend_with_model(model_point_f: float, assessment: RegimeAssessment,
                     strength: float = 0.5) -> float:
    """Nudge the model point toward the regime-weighted estimate by ``strength`` (0..1).

    Only used when regime weighting is ENABLED. strength=0 => pure model (default advisory
    behavior); strength=1 => pure regime blend. Conservative default 0.5.
    """
    if assessment.weighted_tmax_f is None:
        return model_point_f
    s = float(np.clip(strength, 0.0, 1.0))
    return (1 - s) * model_point_f + s * assessment.weighted_tmax_f
