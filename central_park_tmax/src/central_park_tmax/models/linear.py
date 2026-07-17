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
    """Least squares predicting continuous TMAX directly (auto-ridge when underdetermined)."""
    name: str = "linear_continuous"
    alpha: float = 1.0

    def __post_init__(self):
        self.model: Optional[Pipeline] = None
        self.feature_names: Optional[list[str]] = None

    def fit(self, fm: FeatureMatrix) -> "LinearContinuous":
        self.feature_names = fm.feature_names
        n_samples, n_features = fm.X.shape
        est = Ridge(alpha=self.alpha) if n_samples < 2 * n_features else LinearRegression()
        self.model = Pipeline([("scale", StandardScaler()), ("lm", est)])
        self.model.fit(fm.X, fm.y)
        return self

    def predict(self, fm: FeatureMatrix) -> np.ndarray:
        return self.model.predict(fm.X_for(self.feature_names))


@dataclass
class LinearResidual:
    """Linear (or ridge) regression predicting the baseline model error (residual).

    Guard: plain OLS is catastrophically ill-posed when the training sample is not
    comfortably larger than the feature count (coefficients explode, predictions reach
    thousands of degrees). If n_samples < 2 * n_features we automatically substitute a
    ridge penalty and log it — the baseline stays defined and sane on small folds.
    """
    ridge: bool = False
    alpha: float = 1.0

    def __post_init__(self):
        self.name = "ridge_residual" if self.ridge else "linear_residual"
        self.feature_names: Optional[list[str]] = None
        self.model: Optional[Pipeline] = None

    def fit(self, fm: FeatureMatrix) -> "LinearResidual":
        self.feature_names = fm.feature_names
        n_samples, n_features = fm.X.shape
        use_ridge = self.ridge or n_samples < 2 * n_features
        if use_ridge and not self.ridge:
            from ..logging_config import get_logger
            get_logger(__name__).warning(
                "linear_residual: %d samples for %d features is underdetermined; "
                "using ridge(alpha=%.1f) regularization.", n_samples, n_features, self.alpha)
        est = Ridge(alpha=self.alpha) if use_ridge else LinearRegression()
        self.model = Pipeline([("scale", StandardScaler()), ("lm", est)])
        self.model.fit(fm.X, fm.residual_target())
        return self

    def predict(self, fm: FeatureMatrix) -> np.ndarray:
        resid = self.model.predict(fm.X_for(self.feature_names))
        return fm.baseline.to_numpy(dtype=float) + resid
