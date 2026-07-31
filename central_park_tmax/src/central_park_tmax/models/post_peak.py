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
real risk that this module prices explicitly. The corollary, learned the expensive way
(track_record 2026-07-25 Phoenix, 2026-07-30 Vegas): **the distance that matters is the
distance to the nearest .5 boundary, never to the next whole degree.** A bucket labelled
"112-113" wins at a true max of 111.5 F, not 112.0 F.

Conditioning caveat (fixed 2026-07-29): the remaining-rise CDF is UNCONDITIONAL
climatology for an hour of day. It answers "across all days, how much more did the
temperature rise after this hour?" — which is the wrong question on a day that is still
rising right now. On 2026-07-29 the raw flag read ``determined=True`` simultaneously in
all three cities while every one of them was still climbing. ``settlement_distribution``
therefore accepts the recent observation trace and refuses to declare the max determined
while the temperature is flat-or-rising.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Mapping, Optional, Sequence

_BACKTESTS = Path(__file__).resolve().parents[3] / "backtest_datasets"
_DATA = _BACKTESTS / "remaining_rise.json"
_GAP_DATA = _BACKTESTS / "snapshot_gap.json"

# Station shorthand -> remaining-rise city key.
_STATION_KEYS = {"KNYC": "nyc", "KPHX": "phoenix", "KLAS": "vegas"}
# City key -> IEM station id used by the snapshot-gap study.
_GAP_KEYS = {"nyc": "NYC", "phoenix": "PHX", "vegas": "LAS"}

# Observed-max provenance that already reflects the CONTINUOUS trace (no snapshot gap).
CONTINUOUS_SOURCES = {"metar_6h_group", "cli", "intraday_cli", "twentyfour_hour_group"}


@lru_cache(maxsize=1)
def _rise_table() -> dict:
    if not _DATA.exists():
        return {}
    return json.loads(_DATA.read_text())


@lru_cache(maxsize=1)
def _gap_table() -> dict:
    if not _GAP_DATA.exists():
        return {}
    return json.loads(_GAP_DATA.read_text())


def snapshot_gap_percentiles(city: Optional[str]) -> Optional[list[float]]:
    """Measured afternoon under-read of hourly snapshots vs the continuous trace.

    101 equally-weighted percentiles in F (scripts/snapshot_gap_study.py). Median is
    ~1.0 F in all three cities: an hourly-snapshot max taken during the trading window is
    typically a FULL DEGREE below what the CLI will settle on.
    """
    entry = _gap_table().get(_GAP_KEYS.get(city or "", ""), {})
    p = entry.get("afternoon_gap_percentiles_f")
    return list(p) if p else None


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
    still_rising: bool = False
    near_rounding_boundary: bool = False
    distance_to_boundary_f: Optional[float] = None

    def to_dict(self) -> dict:
        return {"post_peak_determined": self.determined,
                "post_peak_top_integer": self.top_bucket,
                "post_peak_top_probability": round(self.top_probability, 4),
                "post_peak_p_max_already_in": round(self.p_max_already_in, 4),
                "post_peak_still_rising": self.still_rising,
                "post_peak_near_boundary": self.near_rounding_boundary,
                "post_peak_distance_to_boundary_f": self.distance_to_boundary_f,
                "post_peak_rationale": self.rationale}


# A trace this shallow is inside sensor noise (ASOS reports to 0.1 C ~ 0.18 F), so a
# "fall" smaller than this does not count as evidence that the peak has passed.
_FALL_EPSILON_F = 0.2


def is_still_rising(recent_temps_f: Optional[Sequence[float]]) -> bool:
    """True when the latest observations are flat-or-rising (peak not yet demonstrated).

    ``recent_temps_f`` is the instantaneous temperature trace in CHRONOLOGICAL order. With
    fewer than two usable observations we cannot show a decline, so we assume the day is
    still live — the conservative direction, since the failure this guards against is
    declaring a max banked while it is still climbing.
    """
    vals = [float(t) for t in (recent_temps_f or []) if t is not None]
    if len(vals) < 2:
        return True
    return (vals[-1] - vals[-2]) > -_FALL_EPSILON_F


def settlement_distribution(station_shorthand: Optional[str],
                            observed_max_f: Optional[float],
                            local_hour: int,
                            determined_threshold: float = 0.90,
                            recent_temps_f: Optional[Sequence[float]] = None,
                            observed_max_source: Optional[str] = None,
                            ) -> SettlementOutlook:
    """Distribution over the settled integer max, from live observations alone.

    Combines the measured remaining-rise CDF with round-half-up integer settlement.
    No forecast model is involved: this is deliberately observation-only.

    ``recent_temps_f`` is the recent instantaneous trace (chronological). When it shows
    the temperature flat-or-rising, ``determined`` is forced False no matter what the
    hourly climatology says — see the conditioning caveat in the module docstring. Passing
    nothing is treated as "still rising", i.e. never determined; callers that genuinely
    have no trace should not be claiming a locked max.

    ``observed_max_source`` names the provenance of ``observed_max_f``. Anything not in
    ``CONTINUOUS_SOURCES`` is assumed to be an hourly-snapshot reading and gets the
    measured snapshot-gap distribution convolved in — without this the tool treats a
    snapshot max as exact and reads roughly a full degree low.
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

    # The observed max may itself UNDER-READ the settlement value: hourly :51 snapshots
    # miss spikes between observations, and the 6-hour group covering the afternoon is not
    # transmitted until 23:51Z. Convolve in the measured gap unless the observed max
    # already comes from a continuous source. See snapshot_gap_study.py / LESSONS.md #10.
    gap_pcts = (snapshot_gap_percentiles(city)
                if (observed_max_source or "").lower() not in CONTINUOUS_SOURCES else None)
    gaps: list[float] = list(gap_pcts) if gap_pcts else [0.0]
    gap_weight = 1.0 / len(gaps)

    # Final max = observed max + snapshot gap + further rise; settle by round-half-up.
    out: dict[int, float] = {}
    for rise, p in enumerate(pmf_rise):
        if p <= 0:
            continue
        for g in gaps:
            settled = int((observed_max_f + max(g, 0.0) + rise) + 0.5)   # round-half-up
            out[settled] = out.get(settled, 0.0) + p * gap_weight

    top = max(out, key=lambda k: out[k])
    p_zero = pmf_rise[0]
    rising = is_still_rising(recent_temps_f)
    determined = out[top] >= determined_threshold and not rising
    # Distance to the .5 boundary ABOVE the current max: that, not the next whole degree,
    # is what has to be climbed for the settled integer to tick up.
    frac = observed_max_f % 1
    to_boundary = (0.5 - frac) if frac < 0.5 else (1.5 - frac)
    boundary = abs(frac - 0.5) < 0.12
    note = (f"{observed_max_f:.1f}F banked at {local_hour}h local; "
            f"P(max already in)={p_zero*100:.0f}%; "
            f"{to_boundary:.2f}F to the next .5 settlement boundary")
    if rising:
        note += (" — NOT DETERMINED: latest observations are flat-or-rising, so the "
                 "hourly climatology does not apply to this day yet")
    if boundary:
        note += " — WARNING: sits near a .5 rounding boundary, settlement integer is fragile"
    return SettlementOutlook(determined, city, observed_max_f, local_hour,
                             integer_probabilities=dict(sorted(out.items())),
                             top_bucket=top, top_probability=out[top],
                             p_max_already_in=p_zero, rationale=note,
                             still_rising=rising, near_rounding_boundary=boundary,
                             distance_to_boundary_f=round(to_boundary, 2))


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
