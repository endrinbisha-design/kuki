"""Linear baselines: continuous-TMAX regression and residual (model-error) regressions.

The residual variants predict (report_tmax - baseline_tmax) and reconstruct the final
prediction as baseline_tmax + predicted_residual, matching the primary MOS strategy.
Standardization is fit on the training fold only (leakage-safe) inside a Pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .features_frame import FeatureMatrix


@dataclass
class LinearContinuous:
    """Ordinary least squares predicting continuous TMAX directly."""
    name: str = "linear_continuous"

    def __post_init__(self):
        self.model = Pipeline([("scale", StandardScaler()), ("lm", LinearRegression())])
        self.feature_names: Optional[list[str]] = None

    def fit(self, fm: FeatureMatrix) -> "LinearContinuous":
        self.feature_names = fm.feature_names
        self.model.fit(fm.X, fm.y)
        return self

    def predict(self, fm: FeatureMatrix) -> np.ndarray:
        return self.model.predict(fm.X_for(self.feature_names))


@dataclass
class LinearResidual:
    """Linear (or ridge) regression predicting the baseline model error (residual)."""
    ridge: bool = False
    alpha: float = 1.0

    def __post_init__(self):
        self.name = "ridge_residual" if self.ridge else "linear_residual"
        est = Ridge(alpha=self.alpha) if self.ridge else LinearRegression()
        self.model = Pipeline([("scale", StandardScaler()), ("lm", est)])
        self.feature_names: Optional[list[str]] = None

    def fit(self, fm: FeatureMatrix) -> "LinearResidual":
        self.feature_names = fm.feature_names
        self.model.fit(fm.X, fm.residual_target())
        return self

    def predict(self, fm: FeatureMatrix) -> np.ndarray:
        resid = self.model.predict(fm.X_for(self.feature_names))
        return fm.baseline.to_numpy(dtype=float) + resid
