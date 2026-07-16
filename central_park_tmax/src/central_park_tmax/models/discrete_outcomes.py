"""Convert a continuous predictive distribution into integer NWS-report probabilities.

The continuous distribution is represented by Monte-Carlo samples of the latent maximum.
Samples can be produced from (a) empirical residual bootstrap around a point forecast, or
(b) inverse-CDF interpolation of predicted quantiles. Each sample is mapped through the
configured reporting convention (see reporting_convention.py) to the integer the NWS would
publish, and the empirical frequencies form a probability mass function over integers.

Guarantees:
  * probabilities sum to 1 (within numerical tolerance),
  * support covers all integers observed in the samples (no gaps inside the range).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .reporting_convention import apply_reporting_convention


def simulate_from_residuals(point: float, residuals: np.ndarray, n: int,
                            rng: Optional[np.random.Generator] = None) -> np.ndarray:
    """Bootstrap latent-max samples: point + resampled out-of-sample residuals."""
    rng = rng or np.random.default_rng(0)
    r = np.asarray(residuals, dtype=float)
    r = r[~np.isnan(r)]
    if r.size == 0:
        r = np.array([0.0])
    draws = rng.choice(r, size=n, replace=True)
    return point + draws


def simulate_from_quantiles(levels: list[float], values: list[float], n: int,
                            rng: Optional[np.random.Generator] = None) -> np.ndarray:
    """Sample via piecewise-linear inverse CDF from (level, value) quantile pairs.

    Tails beyond the outer quantiles are extrapolated linearly using the outer slopes so the
    distribution has finite, sensible support.
    """
    rng = rng or np.random.default_rng(0)
    levels = np.asarray(levels, dtype=float)
    values = np.asarray(values, dtype=float)
    order = np.argsort(levels)
    levels, values = levels[order], np.sort(values[order])
    u = rng.uniform(0, 1, size=n)
    samples = np.interp(u, levels, values)
    # Linear tail extrapolation outside [min level, max level].
    if len(levels) >= 2:
        lo_slope = (values[1] - values[0]) / max(1e-6, (levels[1] - levels[0]))
        hi_slope = (values[-1] - values[-2]) / max(1e-6, (levels[-1] - levels[-2]))
        below = u < levels[0]
        above = u > levels[-1]
        samples[below] = values[0] - lo_slope * (levels[0] - u[below])
        samples[above] = values[-1] + hi_slope * (u[above] - levels[-1])
    return samples


@dataclass
class IntegerReportDistribution:
    """A probability mass function over integer report values."""
    pmf: dict[int, float]

    def normalize(self) -> "IntegerReportDistribution":
        total = sum(self.pmf.values())
        if total <= 0:
            raise ValueError("Integer PMF has non-positive total mass.")
        self.pmf = {k: v / total for k, v in self.pmf.items()}
        return self

    def as_str_keys(self) -> dict[str, float]:
        return {str(k): float(v) for k, v in sorted(self.pmf.items())}

    def total(self) -> float:
        return float(sum(self.pmf.values()))

    def mode(self) -> int:
        return max(self.pmf.items(), key=lambda kv: kv[1])[0]

    def top_two(self) -> list[int]:
        return [k for k, _ in sorted(self.pmf.items(), key=lambda kv: kv[1], reverse=True)[:2]]


def integer_report_distribution(
    samples: np.ndarray,
    convention: str = "round_half_up",
    fill_gaps: bool = True,
) -> IntegerReportDistribution:
    """Empirical integer-report PMF from latent-max samples under a reporting convention."""
    ints = np.array([apply_reporting_convention(float(s), method=convention) for s in samples])
    lo, hi = int(ints.min()), int(ints.max())
    support = range(lo, hi + 1) if fill_gaps else np.unique(ints)
    counts = {k: 0 for k in support}
    for v in ints:
        counts[int(v)] = counts.get(int(v), 0) + 1
    n = len(ints)
    pmf = {k: c / n for k, c in counts.items()}
    return IntegerReportDistribution(pmf=pmf).normalize()
