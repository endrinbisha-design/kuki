"""Out-of-sample residual calibration and probability calibration helpers.

Residual calibration collects prediction errors from validation folds ONLY (never the test
period being scored) and exposes them for empirical-residual quantiles / integer simulation.
Probability calibration provides an isotonic reliability mapping used for contract Brier
improvement, again fit only on validation data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class ResidualCalibrator:
    """Accumulates out-of-sample residuals (actual - predicted) for empirical uncertainty."""
    residuals: list[float] = field(default_factory=list)

    def add(self, actual: np.ndarray, predicted: np.ndarray) -> None:
        a = np.asarray(actual, dtype=float)
        p = np.asarray(predicted, dtype=float)
        r = a - p
        self.residuals.extend([float(x) for x in r[~np.isnan(r)]])

    def array(self) -> np.ndarray:
        return np.asarray(self.residuals, dtype=float) if self.residuals else np.array([0.0])

    def std(self) -> float:
        arr = self.array()
        return float(np.std(arr)) if arr.size > 1 else 1.0


@dataclass
class IsotonicProbabilityCalibrator:
    """Monotone reliability mapping for binary contract probabilities (fit on validation)."""
    name: str = "isotonic"

    def __post_init__(self):
        self._iso = None

    def fit(self, prob: np.ndarray, outcome: np.ndarray) -> "IsotonicProbabilityCalibrator":
        from sklearn.isotonic import IsotonicRegression
        p = np.asarray(prob, dtype=float)
        y = np.asarray(outcome, dtype=float)
        mask = ~(np.isnan(p) | np.isnan(y))
        if mask.sum() < 5 or len(np.unique(y[mask])) < 2:
            self._iso = None
            return self
        self._iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self._iso.fit(p[mask], y[mask])
        return self

    def transform(self, prob: np.ndarray) -> np.ndarray:
        p = np.asarray(prob, dtype=float)
        if self._iso is None:
            return p
        return self._iso.predict(p)
