"""Gradient-boosted residual model with a graceful backend hierarchy.

Backend selection ('auto'): XGBoost -> LightGBM -> sklearn HistGradientBoostingRegressor.
The model predicts the baseline model error (report_tmax - baseline_tmax) and reconstructs
predicted_tmax = baseline_tmax + predicted_residual. Early stopping is used when a
validation split is supplied and the backend supports it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from ..logging_config import get_logger
from .features_frame import FeatureMatrix

log = get_logger(__name__)


def _select_backend(pref: str) -> str:
    if pref in ("xgboost", "lightgbm", "sklearn"):
        return pref
    try:
        import xgboost  # noqa: F401
        return "xgboost"
    except Exception:  # noqa: BLE001
        pass
    try:
        import lightgbm  # noqa: F401
        return "lightgbm"
    except Exception:  # noqa: BLE001
        pass
    return "sklearn"


@dataclass
class BoostingResidualModel:
    backend: str = "auto"
    n_estimators: int = 600
    learning_rate: float = 0.03
    max_depth: int = 4
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    reg_lambda: float = 1.0
    min_child_weight: float = 5.0
    early_stopping_rounds: int = 50
    random_state: int = 20240101
    name: str = "boosting_residual"

    def __post_init__(self):
        self._backend = _select_backend(self.backend)
        self.name = f"boosting_residual_{self._backend}"
        self.model = None
        self.feature_names: Optional[list[str]] = None

    def fit(self, fm: FeatureMatrix, valid: Optional[FeatureMatrix] = None) -> "BoostingResidualModel":
        self.feature_names = fm.feature_names
        X, y = fm.X.to_numpy(), fm.residual_target().to_numpy()
        if self._backend == "xgboost":
            self._fit_xgb(X, y, valid)
        elif self._backend == "lightgbm":
            self._fit_lgb(X, y, valid)
        else:
            self._fit_sklearn(X, y, valid)
        return self

    def _fit_xgb(self, X, y, valid):
        import xgboost as xgb
        params = dict(
            n_estimators=self.n_estimators, learning_rate=self.learning_rate,
            max_depth=self.max_depth, subsample=self.subsample,
            colsample_bytree=self.colsample_bytree, reg_lambda=self.reg_lambda,
            min_child_weight=self.min_child_weight, random_state=self.random_state,
            objective="reg:squarederror", n_jobs=0,
        )
        eval_set = None
        if valid is not None and len(valid) > 0:
            params["early_stopping_rounds"] = self.early_stopping_rounds
            eval_set = [(valid.X_for(self.feature_names).to_numpy(),
                         valid.residual_target().to_numpy())]
        self.model = xgb.XGBRegressor(**params)
        self.model.fit(X, y, eval_set=eval_set, verbose=False)

    def _fit_lgb(self, X, y, valid):
        import lightgbm as lgb
        self.model = lgb.LGBMRegressor(
            n_estimators=self.n_estimators, learning_rate=self.learning_rate,
            max_depth=self.max_depth, subsample=self.subsample,
            colsample_bytree=self.colsample_bytree, reg_lambda=self.reg_lambda,
            min_child_weight=self.min_child_weight, random_state=self.random_state,
            n_jobs=-1, verbosity=-1,
        )
        callbacks = None
        eval_set = None
        if valid is not None and len(valid) > 0:
            eval_set = [(valid.X_for(self.feature_names).to_numpy(),
                         valid.residual_target().to_numpy())]
            callbacks = [lgb.early_stopping(self.early_stopping_rounds, verbose=False)]
        self.model.fit(X, y, eval_set=eval_set, callbacks=callbacks)

    def _fit_sklearn(self, X, y, valid):
        from sklearn.ensemble import HistGradientBoostingRegressor
        self.model = HistGradientBoostingRegressor(
            max_iter=self.n_estimators, learning_rate=self.learning_rate,
            max_depth=self.max_depth, l2_regularization=self.reg_lambda,
            min_samples_leaf=max(5, int(self.min_child_weight)),
            validation_fraction=0.15 if valid is None else None,
            early_stopping=True if valid is None else False,
            random_state=self.random_state,
        )
        self.model.fit(X, y)

    def predict(self, fm: FeatureMatrix) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Model not fitted.")
        resid = self.model.predict(fm.X_for(self.feature_names).to_numpy())
        return fm.baseline.to_numpy(dtype=float) + resid

    def predict_residual(self, fm: FeatureMatrix) -> np.ndarray:
        return self.model.predict(fm.X_for(self.feature_names).to_numpy())

    def feature_importance(self) -> dict[str, float]:
        if self.model is None or self.feature_names is None:
            return {}
        imp = getattr(self.model, "feature_importances_", None)
        if imp is None:
            return {}
        return dict(sorted(zip(self.feature_names, [float(x) for x in imp]),
                           key=lambda kv: kv[1], reverse=True))
