"""Quantile forecasting for the continuous maximum + non-crossing enforcement.

Two uncertainty methods are provided:
  1. ``QuantileBoosting`` : one gradient-boosted quantile regressor per quantile level
     (predicts residual quantiles; reconstructs baseline + residual). Quantiles are sorted
     to guarantee non-crossing (monotone in level).
  2. ``EmpiricalResidualQuantiles`` : add out-of-sample residual empirical quantiles to a
     point prediction. Calibrated ONLY on prior/out-of-sample residuals (see calibration).

``enforce_monotone`` sorts each row's quantile vector ascending so q10 <= q25 <= ... always.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .features_frame import FeatureMatrix


def enforce_monotone(quantile_matrix: np.ndarray) -> np.ndarray:
    """Sort each row ascending so quantiles never cross."""
    return np.sort(quantile_matrix, axis=1)


@dataclass
class QuantileBoosting:
    quantiles: list[float] = field(default_factory=lambda: [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95])
    learning_rate: float = 0.05
    n_estimators: int = 400
    max_depth: int = 3
    random_state: int = 20240101
    name: str = "quantile_gbm"

    def __post_init__(self):
        self.models: dict[float, object] = {}
        self.feature_names: Optional[list[str]] = None

    def fit(self, fm: FeatureMatrix) -> "QuantileBoosting":
        from sklearn.ensemble import GradientBoostingRegressor
        self.feature_names = fm.feature_names
        X = fm.X.to_numpy()
        resid = fm.residual_target().to_numpy()
        for q in self.quantiles:
            gbr = GradientBoostingRegressor(
                loss="quantile", alpha=q, learning_rate=self.learning_rate,
                n_estimators=self.n_estimators, max_depth=self.max_depth,
                random_state=self.random_state,
            )
            gbr.fit(X, resid)
            self.models[q] = gbr
        return self

    def predict_quantiles(self, fm: FeatureMatrix) -> pd.DataFrame:
        X = fm.X_for(self.feature_names).to_numpy()
        base = fm.baseline.to_numpy(dtype=float)
        cols = []
        for q in self.quantiles:
            cols.append(base + self.models[q].predict(X))
        mat = np.column_stack(cols)
        mat = enforce_monotone(mat)
        return pd.DataFrame(mat, columns=[f"q{int(q*100):02d}" for q in self.quantiles])


@dataclass
class EmpiricalResidualQuantiles:
    """Empirical residual bands added to a point forecast. Fit on out-of-sample residuals."""
    quantiles: list[float] = field(default_factory=lambda: [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95])
    name: str = "empirical_residual"

    def __post_init__(self):
        self._residual_quantiles: Optional[np.ndarray] = None

    def fit(self, oos_residuals: np.ndarray) -> "EmpiricalResidualQuantiles":
        r = np.asarray(oos_residuals, dtype=float)
        r = r[~np.isnan(r)]
        if r.size == 0:
            r = np.array([0.0])
        self._residual_quantiles = np.quantile(r, self.quantiles)
        return self

    def predict_quantiles(self, point_prediction: np.ndarray) -> pd.DataFrame:
        if self._residual_quantiles is None:
            raise RuntimeError("EmpiricalResidualQuantiles not fitted.")
        p = np.asarray(point_prediction, dtype=float).reshape(-1, 1)
        mat = p + self._residual_quantiles.reshape(1, -1)
        mat = enforce_monotone(mat)
        return pd.DataFrame(mat, columns=[f"q{int(q*100):02d}" for q in self.quantiles])

    @property
    def residual_quantiles(self) -> Optional[np.ndarray]:
        return self._residual_quantiles
