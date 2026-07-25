"""Hot-day tail calibration: city-specific correction of the bucket distribution.

Motivation (see HOT_DAY_CALIBRATION.md). Live losses on 2026-07-23/24 suggested that
"bet the model's centre bucket" was failing in Phoenix. Measuring it on the 3,283-day
multi-year MOS backtest per city showed the real structure, and it is NOT what two
anecdotes implied: what differs between cities on HOT days is the *shape and offset of
the error distribution*, and it differs in SIGN.

Hot days = forecast at/above the city's 90th-percentile forecast (n≈400 per city,
2015-2025). err = actual - forecast (positive => guidance ran COOL):

    city      median err   P(err>=+2)   P(err<=-2)   read
    Phoenix     +0.9 F        24%           7%       guidance runs COOL; fat WARM tail
    NYC          0.0 F        23%          17%       centred but WIDE both ways
    Vegas       -1.0 F         6%          28%       guidance runs WARM; fat COOL tail

Consequences for bucket selection on hot days:
  * Phoenix: shift the point up ~+0.9 F and give the bucket ABOVE centre real weight
    (~24% of hot days come in >=2 F above guidance). Declining the warm bucket on
    principle — the rule imported from NYC — is wrong here.
  * Vegas: the opposite. Shift DOWN ~1 F; the warm bucket is a trap (6%).
  * NYC: do not shift; widen. Both tails are live (23%/17%).

This module is advisory and additive: it returns a recommended point shift and a
re-weighted integer PMF. It does not modify the trained model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

# Per-city hot-day error statistics, measured on backtest_datasets/{city}_mos_multiyear.csv
# (see scripts/hot_day_calibration_fit.py). hot_threshold_f is the city's 90th-pct forecast.
HOT_DAY_STATS: dict[str, dict] = {
    "phoenix": {"hot_threshold_f": 108.6, "median_err_f": 0.9,
                "p_warm_2f": 0.24, "p_cool_2f": 0.07, "n": 402},
    "nyc":     {"hot_threshold_f": 86.0, "median_err_f": 0.0,
                "p_warm_2f": 0.23, "p_cool_2f": 0.17, "n": 407},
    "vegas":   {"hot_threshold_f": 107.0, "median_err_f": -1.0,
                "p_warm_2f": 0.06, "p_cool_2f": 0.28, "n": 425},
}

# Station shorthand -> stats key, so callers can pass cfg.station.shorthand directly.
_STATION_KEYS = {"KNYC": "nyc", "KPHX": "phoenix", "KLAS": "vegas"}


def resolve_city_key(station_shorthand: Optional[str]) -> Optional[str]:
    return _STATION_KEYS.get((station_shorthand or "").upper())


@dataclass
class HotDayAdjustment:
    applies: bool
    city: Optional[str]
    point_shift_f: float
    p_warm_2f: float
    p_cool_2f: float
    rationale: str

    def to_dict(self) -> dict:
        return {"hot_day_calibration_applies": self.applies,
                "hot_day_point_shift_f": round(self.point_shift_f, 2),
                "hot_day_p_warm_2f": self.p_warm_2f,
                "hot_day_p_cool_2f": self.p_cool_2f,
                "hot_day_rationale": self.rationale}


def assess_hot_day(station_shorthand: Optional[str],
                   forecast_tmax_f: Optional[float]) -> HotDayAdjustment:
    """Is this a hot day for this station, and what does the measured tail imply?"""
    city = resolve_city_key(station_shorthand)
    if city is None or forecast_tmax_f is None:
        return HotDayAdjustment(False, city, 0.0, 0.0, 0.0,
                                "no hot-day calibration for this station")
    s = HOT_DAY_STATS[city]
    if forecast_tmax_f < s["hot_threshold_f"]:
        return HotDayAdjustment(False, city, 0.0, 0.0, 0.0,
                                f"{forecast_tmax_f:.0f}F below {city} hot threshold "
                                f"{s['hot_threshold_f']:.0f}F")
    direction = ("guidance runs COOL here; the bucket ABOVE centre carries real weight"
                 if s["median_err_f"] > 0.3 else
                 "guidance runs WARM here; fade the warm bucket" if s["median_err_f"] < -0.3
                 else "centred but wide; both tails live")
    return HotDayAdjustment(
        True, city, s["median_err_f"], s["p_warm_2f"], s["p_cool_2f"],
        f"HOT day for {city} (fc {forecast_tmax_f:.0f}F >= {s['hot_threshold_f']:.0f}F): "
        f"median err {s['median_err_f']:+.1f}F, P(>=+2F)={s['p_warm_2f']*100:.0f}%, "
        f"P(<=-2F)={s['p_cool_2f']*100:.0f}% — {direction}")


def reweight_integer_pmf(pmf: Mapping[int, float],
                         adj: HotDayAdjustment,
                         strength: float = 1.0) -> dict[int, float]:
    """Shift/re-skew an integer-temperature PMF by the measured hot-day tail.

    Implemented as a probability transfer along the temperature axis: mass is moved by
    ``point_shift_f`` (linear interpolation between adjacent integers) and then the
    >=+2F / <=-2F tails are nudged toward the measured frequencies. Returns a new
    normalized PMF; the input is untouched. ``strength`` in [0,1] scales the effect.
    """
    if not pmf:
        return {}
    if not adj.applies or strength <= 0:
        return dict(pmf)

    shift = adj.point_shift_f * strength
    lo = int(shift // 1)
    frac = shift - lo
    shifted: dict[int, float] = {}
    for k, v in pmf.items():
        shifted[k + lo] = shifted.get(k + lo, 0.0) + v * (1 - frac)
        shifted[k + lo + 1] = shifted.get(k + lo + 1, 0.0) + v * frac

    # Tail nudge: scale mass in each tail toward the measured probability.
    centre = max(shifted, key=lambda k: shifted[k])
    warm = {k: v for k, v in shifted.items() if k >= centre + 2}
    cool = {k: v for k, v in shifted.items() if k <= centre - 2}
    out = dict(shifted)
    for tail, target in ((warm, adj.p_warm_2f), (cool, adj.p_cool_2f)):
        cur = sum(tail.values())
        if cur > 1e-9 and target > 0:
            factor = 1.0 + strength * ((target / cur) - 1.0)
            factor = min(max(factor, 0.25), 4.0)     # keep the nudge sane
            for k in tail:
                out[k] *= factor

    total = sum(out.values())
    return {k: v / total for k, v in sorted(out.items())} if total > 0 else dict(pmf)
