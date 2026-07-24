"""Sea-breeze / marine-cap risk for Central Park (KNYC) — advisory add-on.

Two independent instruments (see scripts/sea_breeze_classifier.py and SEA_BREEZE.md):

1. ``night_before_risk`` — a distilled logistic model fitted on 2015-2025 warm seasons
   (1,269 days): P(actual CP max underperforms the night-before guidance by >= 2.5 F).
   Honest performance: pooled out-of-sample AUC 0.61; top-15%-risk days bust at ~20%
   vs ~12% base rate (1.7x lift). This is an ADVISORY risk flag, not a point
   correction — on flagged days, widen the downside and avoid warm-tail bets.

2. ``coastal_divergence`` — the sharper *intraday* signal: live JFK/LGA obs vs CP.
   Marine air reaches the coastal airports 1-3 h before Central Park; JFK stalling
   or its wind backing onshore while CP still climbs is the early warning that the
   afternoon peak will be capped (this is what the 2026-07-23 bust looked like).

Missing inputs are mean-imputed in standardized space (z=0), so the score degrades
gracefully when e.g. no JFK forecast or SST is available.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping, Optional

# KNYC onshore (marine) sector, deg true — SE through S (features/wind.py convention).
ONSHORE_LO, ONSHORE_HI = 90, 200

# Distilled logistic fitted by scripts/sea_breeze_classifier.py on 2015-2025 warm
# seasons (backtest_datasets/sea_breeze_classifier.json). Features are standardized
# with the means/scales below; None inputs impute to the mean (z=0).
_FEATURES = ("mos_cp", "grad_fc", "wdr_pm", "wsp_pm", "onshore_pm", "contrast",
             "doy_sin", "doy_cos")
_MEANS = (79.5189, 0.8161, 186.5012, 4.7409, 0.2942, 11.706, -0.1703, -0.7218)
_SCALES = (8.4251, 1.9532, 89.0665, 2.5859, 0.4051, 7.1954, 0.6157, 0.2664)
_COEF = (0.2414, 0.6526, 0.2359, 0.2706, -0.0716, -0.8294, 0.0516, -0.0498)
_INTERCEPT = -2.0679
FLAG_THRESHOLD = 0.207          # top-15% of pooled OOS risk scores


@dataclass
class SeaBreezeRisk:
    probability: float
    flagged: bool
    inputs_used: dict = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> dict:
        return {"sea_breeze_risk": round(self.probability, 3),
                "sea_breeze_flagged": self.flagged,
                "sea_breeze_rationale": self.rationale}


def night_before_risk(*, forecast_cp_max_f: Optional[float],
                      forecast_jfk_max_f: Optional[float] = None,
                      afternoon_wind_dir_deg: Optional[float] = None,
                      afternoon_wind_speed_kt: Optional[float] = None,
                      sst_f: Optional[float] = None,
                      day_of_year: Optional[int] = None) -> SeaBreezeRisk:
    """P(marine-cap cool bust >= 2.5 F) for tomorrow's CP max, night-before inputs."""
    grad = (forecast_cp_max_f - forecast_jfk_max_f
            if forecast_cp_max_f is not None and forecast_jfk_max_f is not None else None)
    onshore = (float(ONSHORE_LO <= afternoon_wind_dir_deg <= ONSHORE_HI)
               if afternoon_wind_dir_deg is not None else None)
    contrast = (forecast_cp_max_f - sst_f
                if forecast_cp_max_f is not None and sst_f is not None else None)
    doy_sin = math.sin(2 * math.pi * day_of_year / 365.25) if day_of_year else None
    doy_cos = math.cos(2 * math.pi * day_of_year / 365.25) if day_of_year else None
    raw = {"mos_cp": forecast_cp_max_f, "grad_fc": grad, "wdr_pm": afternoon_wind_dir_deg,
           "wsp_pm": afternoon_wind_speed_kt, "onshore_pm": onshore, "contrast": contrast,
           "doy_sin": doy_sin, "doy_cos": doy_cos}
    z = _INTERCEPT
    used = {}
    for name, mean, scale, coef in zip(_FEATURES, _MEANS, _SCALES, _COEF):
        v = raw[name]
        if v is not None:
            z += coef * (v - mean) / scale
            used[name] = round(float(v), 2)
    prob = 1.0 / (1.0 + math.exp(-z))
    flagged = prob >= FLAG_THRESHOLD
    parts = []
    if grad is not None and grad > 2:
        parts.append(f"forecast CP-JFK gradient +{grad:.1f}F (marine erosion target)")
    if onshore:
        parts.append("onshore afternoon wind forecast")
    if flagged and not parts:
        parts.append("combination of guidance/season factors")
    rationale = ("ELEVATED marine-cap risk: " + "; ".join(parts)) if flagged else \
        "no elevated marine-cap signal"
    return SeaBreezeRisk(probability=prob, flagged=flagged, inputs_used=used,
                         rationale=rationale)


@dataclass
class CoastalDivergence:
    underway: bool
    score: float                 # 0..1 heuristic confidence
    rationale: str

    def to_dict(self) -> dict:
        return {"sea_breeze_underway": self.underway,
                "sea_breeze_divergence_score": round(self.score, 2),
                "sea_breeze_divergence_rationale": self.rationale}


def coastal_divergence(*, cp_temp_f: Optional[float],
                       jfk_temp_f: Optional[float] = None,
                       lga_temp_f: Optional[float] = None,
                       jfk_wind_dir_deg: Optional[float] = None,
                       cp_wind_dir_deg: Optional[float] = None) -> CoastalDivergence:
    """Intraday: is marine air already moving in? (JFK leads CP by 1-3 h.)"""
    if cp_temp_f is None:
        return CoastalDivergence(False, 0.0, "no CP observation")
    score = 0.0
    parts = []
    if jfk_temp_f is not None:
        gap = cp_temp_f - jfk_temp_f
        if gap >= 4:
            score += 0.45
            parts.append(f"JFK running {gap:.0f}F cooler than CP (marine air at the coast)")
        elif gap >= 2:
            score += 0.25
            parts.append(f"JFK {gap:.0f}F cooler than CP")
    if jfk_wind_dir_deg is not None and ONSHORE_LO <= jfk_wind_dir_deg <= ONSHORE_HI:
        score += 0.30
        parts.append("JFK wind onshore (SE-S)")
    if cp_wind_dir_deg is not None and ONSHORE_LO <= cp_wind_dir_deg <= ONSHORE_HI:
        score += 0.25
        parts.append("CP wind already onshore — intrusion reaching the park")
    if lga_temp_f is not None and jfk_temp_f is not None and lga_temp_f - jfk_temp_f >= 3:
        score += 0.10
        parts.append("LGA-JFK spread (front between airports)")
    score = min(score, 1.0)
    underway = score >= 0.5
    rationale = "; ".join(parts) if parts else "no coastal divergence signal"
    return CoastalDivergence(underway, score, rationale)


def parse_ndbc_realtime_sst_f(text: str) -> Optional[float]:
    """Latest water temp (F) from an NDBC realtime2 stdmet text payload."""
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        cols = line.split()
        if len(cols) >= 15:
            try:
                wtmp_c = float(cols[14])
            except ValueError:
                continue
            if -5 <= wtmp_c <= 40:
                return wtmp_c * 9 / 5 + 32
    return None
