"""Daily strategy selector: which play is actually reliable for THIS day.

Live trading this week produced a clear split — forecast-driven bucket bets went 5/16,
while observation-anchored post-peak bets won. But "wait for the peak" is not the whole
answer: the right strategy depends on the day's regime, and the regime effects are
measurable rather than anecdotal.

Measured on the 9-year MOS series joined to GHCN precipitation (warm season, May-Sep;
scripts/regime_stats_fit.py). ``err = actual - forecast``; positive = guidance ran COOL:

    city      regime         n     bias    MAE   P(err>=+2)  P(err<=-2)
    NYC       wet (prcp>0)  583   +0.49   2.53      30%         23%
    NYC       dry          1097   +0.43   1.88      26%         15%
    Phoenix   wet           146   -0.37   2.74      26%         31%
    Phoenix   dry          1534   +0.75   1.46      25%          6%
    Vegas     wet            86   -1.54   2.89      12%         41%
    Vegas     dry          1594   -0.47   1.67      10%         24%

Three findings drive the rules below:

1. **Wet days are much harder everywhere** — MAE rises 35% (NYC), 88% (Phoenix),
   73% (Vegas). Both tails fatten. Narrow bucket bets should simply be avoided — but
   "avoid" applies to the *instrument*, not the day. Live on 2026-07-30 this selector
   said WET_DAY_AVOID for NYC and the correct trade was still available: a WIDE one-sided
   range (<=77F) fading the whole warm side, which cashed. A fat cool tail is untradeable
   as a 2-degree bucket and very tradeable as a half-line.
2. **Phoenix's bias FLIPS SIGN with moisture.** Dry: guidance runs cool (+0.75, cool
   tail only 6%) so the warm bucket carries weight. Wet: guidance runs slightly warm
   (-0.37) and the cool tail explodes 6% -> 31%. A rule learned on dry desert days is
   actively wrong on a monsoon day.
3. **Vegas guidance runs warm in every regime** (-0.47 dry, -1.54 wet) with a persistently
   fat cool tail — the mirror image of Phoenix, 300 miles away.

The selector is advisory: it names a strategy, a confidence, and the reasoning. It never
sizes a position.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Measured warm-season regime statistics (see module docstring).
REGIME_STATS: dict[str, dict[str, dict]] = {
    "nyc": {"wet": {"n": 583, "bias": 0.49, "mae": 2.53, "p_warm2": 0.30, "p_cool2": 0.23},
            "dry": {"n": 1097, "bias": 0.43, "mae": 1.88, "p_warm2": 0.26, "p_cool2": 0.15}},
    "phoenix": {"wet": {"n": 146, "bias": -0.37, "mae": 2.74, "p_warm2": 0.26, "p_cool2": 0.31},
                "dry": {"n": 1534, "bias": 0.75, "mae": 1.46, "p_warm2": 0.25, "p_cool2": 0.06}},
    "vegas": {"wet": {"n": 86, "bias": -1.54, "mae": 2.89, "p_warm2": 0.12, "p_cool2": 0.41},
              "dry": {"n": 1594, "bias": -0.47, "mae": 1.67, "p_warm2": 0.10, "p_cool2": 0.24}},
}

_STATION_KEYS = {"KNYC": "nyc", "KPHX": "phoenix", "KLAS": "vegas"}

# PoP at/above this is treated as a wet/convective day.
WET_POP_THRESHOLD = 40.0


@dataclass
class StrategyAdvice:
    strategy: str
    confidence: str            # high | medium | low | none
    city: Optional[str]
    regime: str
    lean: str                  # warm | cool | neutral
    expected_mae_f: Optional[float]
    p_warm_2f: Optional[float]
    p_cool_2f: Optional[float]
    rationale: str
    actions: list[str]

    def to_dict(self) -> dict:
        return {"strategy": self.strategy, "strategy_confidence": self.confidence,
                "strategy_regime": self.regime, "strategy_lean": self.lean,
                "strategy_expected_mae_f": self.expected_mae_f,
                "strategy_rationale": self.rationale,
                "strategy_actions": self.actions}


def recommend_strategy(*, station_shorthand: Optional[str],
                       local_hour: int,
                       pop_pct: Optional[float] = None,
                       observed_max_f: Optional[float] = None,
                       forecast_tmax_f: Optional[float] = None,
                       determined: Optional[bool] = None,
                       model_spread_f: Optional[float] = None) -> StrategyAdvice:
    """Pick the day's playbook from regime + time of day + how settled the max is.

    Priority order, reflecting what actually worked live:
      1. POST_PEAK_LOCK  — the max is banked; bet arithmetic, not weather.
      2. WET_DAY_AVOID   — convective day; errors are ~2x, both tails fat.
      3. DRY_LEAN_*      — dry day with a measured directional bias worth expressing.
      4. WAIT_FOR_PEAK   — pre-peak with no measured edge.
    """
    city = _STATION_KEYS.get((station_shorthand or "").upper())
    if city is None:
        return StrategyAdvice("NO_COVERAGE", "none", None, "unknown", "neutral", None,
                              None, None,
                              "no measured regime statistics for this station", [])

    wet = pop_pct is not None and pop_pct >= WET_POP_THRESHOLD
    regime = "wet" if wet else "dry"
    st = REGIME_STATS[city][regime]

    # 1) The max is in — the reliable edge regardless of regime.
    if determined:
        return StrategyAdvice(
            "POST_PEAK_LOCK", "high", city, regime, "neutral", st["mae"],
            st["p_warm2"], st["p_cool2"],
            f"max already banked ({observed_max_f:.1f}F at {local_hour}h local) — the "
            "outcome is arithmetic plus rounding, not a forecast",
            ["buy the banked bucket if it prices below its settlement probability",
             "measure the margin to the nearest .5 SETTLEMENT boundary, not to the next "
             "whole degree — a 112-113 bucket flips at 111.5F",
             "expect a grind: these price 85-95c, so risk/reward is ~9:1"])

    # 2) Convective day — measured to be roughly twice as hard.
    if wet:
        return StrategyAdvice(
            "WET_DAY_AVOID", "low", city, regime, "neutral", st["mae"],
            st["p_warm2"], st["p_cool2"],
            f"convective regime (PoP {pop_pct:.0f}%): measured MAE {st['mae']:.2f}F vs "
            f"{REGIME_STATS[city]['dry']['mae']:.2f}F on dry days, with fat tails both "
            f"ways (P>=+2F {st['p_warm2']:.0%}, P<=-2F {st['p_cool2']:.0%})",
            ["avoid NARROW bucket bets entirely — this is the worst regime for them",
             "DO express the fat cool tail as a WIDE one-sided range (<= a strike well "
             f"below the model centre): P(<=-2F) is {st['p_cool2']:.0%} here and the "
             "market prices the point forecast, not the tail",
             "fade any bucket the market prices above ~85%: overconfidence is the edge",
             "if trading at all, wait for the post-peak lock"])

    # 3) Dry day with a measured directional bias.
    bias = st["bias"]
    if bias >= 0.6:                      # guidance runs cool -> warm side carries weight
        return StrategyAdvice(
            "DRY_LEAN_WARM", "medium", city, regime, "warm", st["mae"],
            st["p_warm2"], st["p_cool2"],
            f"dry {city} day: guidance runs COOL by {bias:+.2f}F on average, and only "
            f"{st['p_cool2']:.0%} of days finish 2F+ below it vs {st['p_warm2']:.0%} above",
            ["give the bucket at/above the model centre real weight",
             "do NOT buy two buckets above centre — the bias is ~1F, not 3F",
             "prefer to confirm with the trajectory before the peak"])
    if bias <= -0.4:                     # guidance runs warm -> fade the warm bucket
        return StrategyAdvice(
            "DRY_LEAN_COOL", "medium", city, regime, "cool", st["mae"],
            st["p_warm2"], st["p_cool2"],
            f"dry {city} day: guidance runs WARM by {bias:+.2f}F, with a fat cool tail "
            f"({st['p_cool2']:.0%} finish 2F+ below vs {st['p_warm2']:.0%} above)",
            ["fade the warm bucket — it is the market's trap here",
             "lean the bucket at or one below the model centre"])

    # 4) No measured edge yet.
    spread_note = ""
    if model_spread_f is not None and model_spread_f >= 3.0:
        spread_note = (f"; model spread {model_spread_f:.1f}F is wide — genuine "
                       "uncertainty, so bucket tails are fatter than the market prices")
    return StrategyAdvice(
        "WAIT_FOR_PEAK", "low", city, regime, "neutral", st["mae"],
        st["p_warm2"], st["p_cool2"],
        f"pre-peak at {local_hour}h with no measured directional bias for a dry {city} "
        f"day (bias {bias:+.2f}F){spread_note}",
        ["no trade yet — pre-peak bets are forecast bets",
         "re-check when the post-peak window opens (~15h NYC, ~16h desert)"])
