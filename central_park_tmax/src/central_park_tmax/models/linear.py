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

# Features a LINEAR model must never see raw: they are unbounded or wrap across the
# calendar (day_of_year jumps 366 -> 1), so linear extrapolation beyond the training
# window produces catastrophic drift (observed: -54 F mean error when training
# Aug-Oct and testing across New Year). The bounded harmonics (doy_sin/doy_cos)
# carry the same signal safely. Tree models are unaffected and keep these features.
LINEAR_EXCLUDED_FEATURES = {"day_of_year", "month"}

# Physically-motivated bound on a residual correction to a numerical baseline: no
# defensible MOS correction for KNYC exceeds this magnitude.
MAX_ABS_RESIDUAL_F = 15.0


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
        if n_samples < 2 * n_features:
            est = Ridge(alpha=max(self.alpha, 10.0 * n_features / max(n_samples, 1)))
        else:
            est = LinearRegression()
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
        self.feature_names = [c for c in fm.feature_names if c not in LINEAR_EXCLUDED_FEATURES]
        n_samples, n_features = len(fm.X), len(self.feature_names)
        use_ridge = self.ridge or n_samples < 2 * n_features
        # Scale the penalty with how underdetermined the fit is: with ~85 standardized
        # features on ~60 rows, alpha=1 still lets coefficients extrapolate wildly on
        # seasonally-drifting features. alpha ~ 10 * p/n keeps the baseline sane.
        alpha = max(self.alpha, 10.0 * n_features / max(n_samples, 1)) if use_ridge else self.alpha
        if use_ridge and not self.ridge:
            from ..logging_config import get_logger
            get_logger(__name__).warning(
                "linear_residual: %d samples for %d features is underdetermined; "
                "using ridge(alpha=%.1f).", n_samples, n_features, alpha)
        est = Ridge(alpha=alpha) if use_ridge else LinearRegression()
        self.model = Pipeline([("scale", StandardScaler()), ("lm", est)])
        self.model.fit(fm.X_for(self.feature_names), fm.residual_target())
        return self

    def predict(self, fm: FeatureMatrix) -> np.ndarray:
        resid = self.model.predict(fm.X_for(self.feature_names))
        # A residual correction beyond +-15 F is physically indefensible for KNYC;
        # clipping bounds the damage from extrapolation instead of emitting nonsense.
        resid = np.clip(resid, -MAX_ABS_RESIDUAL_F, MAX_ABS_RESIDUAL_F)
        return fm.baseline.to_numpy(dtype=float) + resid
