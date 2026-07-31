"""Isotonic calibration of CONTRACT probabilities — with the renormalisation it needs.

Distinct from ``models/calibration.py``, which handles residual/reliability calibration
during training. This module applies the *post-hoc, market-fitted* correction measured in
`REAL_PRICE_BACKTEST.md`.

That study measured the integer PMF as **overconfident**: the raw model says 6 % where the
realised frequency is 20 %, and 93 % where it is 86 %. ``scripts/recalibrate_pmf.py`` fits a
per-city isotonic map from raw probability to realised frequency and stores the curve in
``backtest_datasets/recalibration.json``.

**The trap this module exists to close.** The isotonic curve is fitted on POOLED
(probability, outcome) pairs, one row per contract. Applying it independently to each
contract of a day does not preserve the sum-to-one constraint — the corrected numbers are
marginal frequencies, not a distribution. Measured live on 2026-07-31 KNYC, the six
mutually-exclusive contracts calibrated to **183.5 %**. Anything reading those as
probabilities is reading nonsense, and every "edge" computed from them is inflated.

**Honest limits the caller must respect:**

* Isotonic is a step function; it collapses distinct inputs onto identical outputs. On that
  same live board it mapped 8.9 %, 3.5 % and 2.3 % all to 17.4 % — it cannot tell those
  three tails apart. Calibration buys reliability at the cost of resolution.
* Renormalising a set that is NOT exhaustive rescales to the wrong total.
* Fitted on 68 warm-season days per city; it does not extend to other seasons.
* Most importantly: with calibrated probabilities the measured edge vanished
  (+8.3 % → +1.2 %, CI straddling zero). Calibration makes the numbers honest; it does not
  make them profitable. See `LESSONS.md` #11.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Mapping, Optional, Sequence

_CURVES = Path(__file__).resolve().parents[3] / "backtest_datasets" / "recalibration.json"

# Station shorthand -> Kalshi series key used in the fitted-curve file.
_SERIES_FOR_STATION = {"KNYC": "KXHIGHNY", "KPHX": "KXHIGHTPHX", "KLAS": "KXHIGHTLV"}


@lru_cache(maxsize=1)
def _curves() -> dict:
    if not _CURVES.exists():
        return {}
    return json.loads(_CURVES.read_text()).get("fitted_curves", {})


def _series(station_shorthand: Optional[str]) -> str:
    return _SERIES_FOR_STATION.get((station_shorthand or "").upper(), "")


def has_calibration(station_shorthand: Optional[str]) -> bool:
    return _series(station_shorthand) in _curves()


def calibrate_probability(station_shorthand: Optional[str], p: float) -> float:
    """Map one raw probability through the city's isotonic curve.

    Returns ``p`` unchanged when no curve is available. The result is a marginal frequency,
    NOT a component of a distribution — use :func:`calibrate_contract_set` for anything you
    intend to price against.
    """
    curve = _curves().get(_series(station_shorthand))
    if not curve:
        return float(p)
    grid, cal = curve["grid"], curve["calibrated"]
    if p <= grid[0]:
        return float(cal[0])
    if p >= grid[-1]:
        return float(cal[-1])
    for i in range(1, len(grid)):
        if p <= grid[i]:
            lo, hi = grid[i - 1], grid[i]
            w = 0.0 if hi == lo else (p - lo) / (hi - lo)
            return float(cal[i - 1] + w * (cal[i] - cal[i - 1]))
    return float(cal[-1])


def calibrate_contract_set(station_shorthand: Optional[str],
                           raw: Mapping[str, float]) -> dict[str, float]:
    """Calibrate a MUTUALLY EXCLUSIVE, EXHAUSTIVE contract set and renormalise.

    ``raw`` maps contract label -> raw model probability; values should already sum to ~1.
    Passing a partial board rescales to the wrong total and overstates every probability.
    """
    if not raw:
        return {}
    cal = {k: calibrate_probability(station_shorthand, float(v)) for k, v in raw.items()}
    total = sum(cal.values())
    if total <= 0:
        return {k: 1.0 / len(cal) for k in cal}
    return {k: v / total for k, v in cal.items()}


def calibration_report(station_shorthand: Optional[str], raw: Mapping[str, float]) -> dict:
    """Raw vs calibrated view of a board, including the pre-normalisation total.

    ``uncalibrated_total`` is diagnostic: the further from 1.0, the more a naive
    per-contract calibration would have distorted the board.
    """
    cal_unnorm = {k: calibrate_probability(station_shorthand, float(v)) for k, v in raw.items()}
    return {"raw": dict(raw),
            "calibrated": calibrate_contract_set(station_shorthand, raw),
            "uncalibrated_total": round(sum(cal_unnorm.values()), 4),
            "distinct_calibrated_values": len({round(v, 4) for v in cal_unnorm.values()}),
            "n_contracts": len(raw)}


def resolution_warning(report: Mapping) -> Optional[str]:
    """Flag boards where isotonic collapsed contracts into indistinguishable values."""
    n, d = report.get("n_contracts", 0), report.get("distinct_calibrated_values", 0)
    if n >= 4 and d <= n - 2:
        return (f"calibration collapsed {n} contracts onto {d} distinct values — the tails "
                "are not distinguishable after correction; do not read small differences")
    return None


def exhaustive(raw: Sequence[float], tol: float = 0.02) -> bool:
    """Does this look like a full partition (probabilities summing to ~1)?"""
    return abs(sum(raw) - 1.0) <= tol
