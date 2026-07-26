"""Post-peak settlement probabilities — the observation-anchored edge.

Live results (track_record/) are unambiguous: forecast-driven bucket bets went ~4/13,
while the one observation-anchored bet placed AFTER the peak won as designed. The reason
is structural — once the day's max is banked, the only remaining uncertainty is (a) how
much more the temperature can still rise and (b) integer rounding. Both are measurable,
neither needs a weather model.

This module answers: **given the observed max so far and the local hour, what is the
probability distribution of the settled integer max?**

The single empirical input is the "remaining rise" climatology measured from IEM ASOS
hourly observations, warm seasons 2021-2025, per city
(scripts/build_remaining_rise.py -> backtest_datasets/remaining_rise.json):

    remaining_rise(h) = daily_max - max(observations up to hour h)

e.g. NYC 16h local: P(rise = 0) = 95%, P(rise <= 1) = 98%; Phoenix 17h: P(rise = 0) =
100%. That is what makes a late bet near-riskless, and it is measured, not assumed.

Settlement convention: the NWS CLI reports whole degrees F, round-half-up (see
models/reporting_convention.py), so 116.60 F settles as 117 — a rounding boundary is a
real risk that this module prices explicitly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Mapping, Optional

_DATA = Path(__file__).resolve().parents[3] / "backtest_datasets" / "remaining_rise.json"

# Station shorthand -> remaining-rise city key.
_STATION_KEYS = {"KNYC": "nyc", "KPHX": "phoenix", "KLAS": "vegas"}


@lru_cache(maxsize=1)
def _rise_table() -> dict:
    if not _DATA.exists():
        return {}
    return json.loads(_DATA.read_text())


def resolve_city_key(station_shorthand: Optional[str]) -> Optional[str]:
    return _STATION_KEYS.get((station_shorthand or "").upper())


def remaining_rise_cdf(city: str, local_hour: int) -> Optional[list[float]]:
    """P(remaining rise <= k) for k = 0..10, or None when unavailable."""
    tbl = _rise_table().get(city, {})
    # Clamp to the measured hour range; before the first measured hour we cannot claim
    # anything, after the last the day is over.
    hours = sorted(int(h) for h in tbl)
    if not hours:
        return None
    h = min(max(local_hour, hours[0]), hours[-1])
    entry = tbl.get(str(h))
    return list(entry["cdf"]) if entry else None


@dataclass
class SettlementOutlook:
    determined: bool
    city: Optional[str]
    observed_max_f: Optional[float]
    local_hour: int
    integer_probabilities: dict[int, float] = field(default_factory=dict)
    top_bucket: Optional[int] = None
    top_probability: float = 0.0
    p_max_already_in: float = 0.0
    rationale: str = ""

    def to_dict(self) -> dict:
        return {"post_peak_determined": self.determined,
                "post_peak_top_integer": self.top_bucket,
                "post_peak_top_probability": round(self.top_probability, 4),
                "post_peak_p_max_already_in": round(self.p_max_already_in, 4),
                "post_peak_rationale": self.rationale}


def settlement_distribution(station_shorthand: Optional[str],
                            observed_max_f: Optional[float],
                            local_hour: int,
                            determined_threshold: float = 0.90) -> SettlementOutlook:
    """Distribution over the settled integer max, from live observations alone.

    Combines the measured remaining-rise CDF with round-half-up integer settlement.
    No forecast model is involved: this is deliberately observation-only.
    """
    city = resolve_city_key(station_shorthand)
    cdf = remaining_rise_cdf(city, local_hour) if city else None
    if city is None or observed_max_f is None or cdf is None:
        return SettlementOutlook(False, city, observed_max_f, local_hour,
                                 rationale="no remaining-rise climatology for this station/hour")

    # CDF -> PMF over integer rises.
    pmf_rise = [cdf[0]] + [max(cdf[k] - cdf[k - 1], 0.0) for k in range(1, len(cdf))]
    total = sum(pmf_rise)
    if total <= 0:
        return SettlementOutlook(False, city, observed_max_f, local_hour,
                                 rationale="degenerate remaining-rise distribution")
    pmf_rise = [p / total for p in pmf_rise]

    # Final max = observed max + rise; settle by round-half-up on whole degrees F.
    out: dict[int, float] = {}
    for rise, p in enumerate(pmf_rise):
        if p <= 0:
            continue
        settled = int((observed_max_f + rise) + 0.5)   # round-half-up
        out[settled] = out.get(settled, 0.0) + p

    top = max(out, key=lambda k: out[k])
    p_zero = pmf_rise[0]
    determined = out[top] >= determined_threshold
    boundary = abs((observed_max_f % 1) - 0.5) < 0.12
    note = (f"{observed_max_f:.1f}F banked at {local_hour}h local; "
            f"P(max already in)={p_zero*100:.0f}%")
    if boundary:
        note += " — WARNING: sits near a .5 rounding boundary, settlement integer is fragile"
    return SettlementOutlook(determined, city, observed_max_f, local_hour,
                             integer_probabilities=dict(sorted(out.items())),
                             top_bucket=top, top_probability=out[top],
                             p_max_already_in=p_zero, rationale=note)


def bucket_probability(outlook: SettlementOutlook, low: int, high: int) -> float:
    """P(settled integer falls in the inclusive [low, high] contract bucket)."""
    return sum(p for k, p in outlook.integer_probabilities.items() if low <= k <= high)


def edge_vs_price(outlook: SettlementOutlook, low: int, high: int,
                  yes_price_cents: float) -> dict:
    """Compare the observation-implied bucket probability to a market price.

    Returns model probability, edge in cents, and the Kalshi taker fee estimate
    (ceil(0.07 * C * P * (1-P)) per contract, C=1).
    """
    import math
    p = bucket_probability(outlook, low, high)
    price = yes_price_cents / 100.0
    fee_c = math.ceil(0.07 * price * (1 - price) * 100) / 100.0 * 100
    return {"bucket": f"{low}-{high}", "model_probability": round(p, 4),
            "yes_price_cents": yes_price_cents,
            "edge_cents": round(p * 100 - yes_price_cents, 2),
            "est_fee_cents": round(fee_c, 2),
            "net_edge_cents": round(p * 100 - yes_price_cents - fee_c, 2)}
