"""Out-of-distribution guard: shrink residual corrections outside the training envelope.

Motivating failure (observed live): a model trained on Aug-Jan applied its learned warm
correction (+3.95 F) to a July frontal-cooldown day, while NBM/HRRR/GFS all agreed on the
raw baseline and the market priced accordingly. Gradient-boosted trees extrapolate their
training-region corrections *flat* into unseen feature space, so the correction keeps its
full magnitude exactly where it deserves the least trust.

The guard computes, at predict time, how far the row's most important features sit outside
the training distribution, and shrinks the correction toward zero (i.e. toward the raw
baseline) proportionally. It never *adds* anything — it only attenuates the learned
correction where the model has no support. The shrink factor and score are reported in the
prediction record so a shrunk forecast is visibly flagged.

Score: over the top-K features by importance, the fraction whose value lies outside the
training [min, max] OR beyond ``z_limit`` training standard deviations from the mean.
Shrink: 1.0 (no change) at score <= ``score_floor``; linear down to ``min_shrink`` at
score >= ``score_ceil``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class FeatureStats:
    """Per-feature training distribution summary stored with each trained model."""
    mean: dict[str, float]
    std: dict[str, float]
    min: dict[str, float]
    max: dict[str, float]

    @classmethod
    def from_frame(cls, X: pd.DataFrame) -> "FeatureStats":
        num = X.apply(pd.to_numeric, errors="coerce")
        return cls(
            mean={c: float(num[c].mean()) for c in num.columns},
            std={c: float(num[c].std(ddof=0)) for c in num.columns},
            min={c: float(num[c].min()) for c in num.columns},
            max={c: float(num[c].max()) for c in num.columns},
        )


@dataclass
class OodAssessment:
    score: float                    # fraction of checked features out of envelope
    shrink: float                   # multiplier applied to the residual correction
    offending: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"ood_score": round(self.score, 3),
                "ood_shrink": round(self.shrink, 3),
                "ood_offending_features": self.offending[:8]}


def assess_ood(
    row: dict | pd.Series,
    stats: FeatureStats,
    importance: dict[str, float],
    top_k: int = 15,
    z_limit: float = 3.0,
    score_floor: float = 0.15,
    score_ceil: float = 0.60,
    min_shrink: float = 0.25,
) -> OodAssessment:
    """Score a prediction row against the training envelope and derive a shrink factor."""
    ranked = [f for f, _ in sorted(importance.items(), key=lambda kv: kv[1], reverse=True)
              if f in stats.mean][:top_k]
    if not ranked:
        return OodAssessment(score=0.0, shrink=1.0)

    offending: list[str] = []
    for f in ranked:
        val = row.get(f) if isinstance(row, dict) else row.get(f, None)
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        if np.isnan(v):
            continue
        lo, hi = stats.min[f], stats.max[f]
        sd = stats.std[f]
        outside_range = v < lo or v > hi
        outside_z = sd > 0 and abs(v - stats.mean[f]) > z_limit * sd
        if outside_range or outside_z:
            offending.append(f)

    score = len(offending) / len(ranked)
    if score <= score_floor:
        shrink = 1.0
    elif score >= score_ceil:
        shrink = min_shrink
    else:
        frac = (score - score_floor) / (score_ceil - score_floor)
        shrink = 1.0 - frac * (1.0 - min_shrink)
    return OodAssessment(score=score, shrink=shrink, offending=offending)


def apply_shrink(baseline: float, point: float, shrink: float) -> float:
    """Attenuate the correction (point - baseline) by ``shrink``, keeping the baseline."""
    return baseline + (point - baseline) * shrink


@dataclass
class ConsensusAssessment:
    spread_f: float                 # stdev of available model daily maxima
    cap_f: float                    # correction magnitude cap implied by the spread
    applied: bool
    correction_before_f: float
    correction_after_f: float

    def to_dict(self) -> dict:
        return {"consensus_spread_f": round(self.spread_f, 2),
                "consensus_cap_f": round(self.cap_f, 2),
                "consensus_cap_applied": self.applied}


def consensus_cap(
    baseline: float,
    point: float,
    secondary_tmax_f: dict[str, float],
    spread_multiple: float = 2.0,
    min_cap_f: float = 1.5,
) -> tuple[float, ConsensusAssessment]:
    """Bound the learned correction by live inter-model disagreement.

    Rationale (observed failure): when independent NWP models tightly agree on the
    daily maximum (spread ~1 F), a statistical correction several degrees outside that
    envelope has no physical support — the observed live case was a +4 F correction on
    a day NBM/HRRR/GFS all placed within 0.9 F. The correction is clipped to
    ``spread_multiple * max(spread, min_cap_f/spread_multiple)``: tight consensus caps
    hard, genuine model disagreement leaves the correction untouched.

    Never applied when fewer than 2 total model values are available.
    """
    vals = [baseline] + [v for v in secondary_tmax_f.values()
                         if v is not None and not np.isnan(v)]
    correction = point - baseline
    if len(vals) < 2:
        a = ConsensusAssessment(spread_f=float("nan"), cap_f=float("inf"), applied=False,
                                correction_before_f=correction,
                                correction_after_f=correction)
        return point, a
    spread = float(np.std(vals))
    cap = max(spread_multiple * spread, min_cap_f)
    capped = float(np.clip(correction, -cap, cap))
    applied = abs(capped - correction) > 1e-9
    return baseline + capped, ConsensusAssessment(
        spread_f=spread, cap_f=cap, applied=applied,
        correction_before_f=correction, correction_after_f=capped)
