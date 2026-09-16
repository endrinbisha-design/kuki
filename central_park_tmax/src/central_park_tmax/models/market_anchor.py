"""Experimental market-anchored probability model, not an execution strategy.

Learn a single convex weight on weather probabilities using settled prior events.
Zero weight is a valid result: a forecasting model need not add information to prices.
Full-board coherence is retained ONLY when both inputs are coherent distributions and
the same weight is applied to every bucket. Partial-board marginal predictions must
never be renormalized into a fabricated full board.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def probabilities(values) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    if not np.isfinite(x).all() or ((x < 0) | (x > 1)).any():
        raise ValueError("Probabilities must be finite and within [0, 1].")
    return x


@dataclass
class MarketAnchoredBlend:
    """Minimize date-balanced Brier loss + penalty * weather_weight**2.

    A fixed nonnegative penalty shrinks toward the market benchmark. It is not
    tuned on the evaluation window. Prices remain noisy market proxies, not known
    true probabilities. This class does not claim calibrated or profitable output.
    """

    penalty: float = 0.01
    min_dates: int = 20
    weather_weight: float = 0.0

    def fit(self, weather, market, outcomes, dates) -> "MarketAnchoredBlend":
        if not np.isfinite(self.penalty) or self.penalty < 0 or self.min_dates < 1:
            raise ValueError("Invalid penalty or min_dates.")
        p, m, y = map(probabilities, (weather, market, outcomes))
        d = pd.Series(pd.to_datetime(dates)).dt.normalize().reset_index(drop=True)
        if p.ndim != 1 or p.shape != m.shape or p.shape != y.shape or len(p) != len(d):
            raise ValueError("Training arrays must be matching one-dimensional vectors.")
        if d.isna().any() or not np.isin(y, [0, 1]).all():
            raise ValueError("Dates must exist and outcomes must be binary.")
        self.train_end = d.max() if len(d) else None
        self.n_dates = d.nunique()
        self.weather_weight = 0.0
        if self.n_dates < self.min_dates:
            return self
        # Equal contribution per date despite unequal numbers of quotes/buckets.
        w = (1.0 / d.map(d.value_counts())).to_numpy()
        w /= w.sum()
        delta = p - m
        denominator = np.sum(w * delta**2) + self.penalty
        if denominator > 0:
            self.weather_weight = float(np.clip(
                np.sum(w * delta * (y - m)) / denominator, 0, 1))
        return self

    def predict(self, weather, market, *, forecast_date=None) -> np.ndarray:
        if not hasattr(self, "train_end"):
            raise RuntimeError("Fit the model first.")
        if forecast_date is not None and self.train_end is not None:
            if pd.Timestamp(forecast_date).normalize() <= self.train_end:
                raise ValueError("Prediction date must be after all training dates.")
        p, m = probabilities(weather), probabilities(market)
        if p.shape != m.shape:
            raise ValueError("Weather and market shapes differ.")
        return m + self.weather_weight * (p - m)
