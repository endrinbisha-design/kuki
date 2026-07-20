"""FeatureMatrix: a small container standardizing model inputs/targets.

Bundles the numeric design matrix, the target (report/meteorological max), the baseline
model daily max (for residual reconstruction), and the target dates. All models consume a
FeatureMatrix so the residual convention (predict target - baseline; reconstruct baseline +
prediction) is applied consistently and leakage-safe scaling is trivial to enforce.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

# Non-feature/bookkeeping columns that must never enter the design matrix.
RESERVED_COLUMNS = {
    "date", "target_date", "target", "target_report_max_f", "target_ghcn_max_f",
    "baseline_tmax_f", "settlement_eligible_max_f", "vintage", "provenance",
    "forecast_issue_local", "forecast_issue_utc", "source",
    "observed_max_so_far_source", "target_provenance", "forecast_init_utc",
    "forecast_source", "forecast_model_version",
}


@dataclass
class FeatureMatrix:
    X: pd.DataFrame
    y: pd.Series
    baseline: pd.Series
    dates: pd.Series
    feature_names: list[str]

    @classmethod
    def from_frame(cls, df: pd.DataFrame, target_col: str = "target_report_max_f",
                   baseline_col: str = "baseline_tmax_f",
                   feature_names: Optional[list[str]] = None) -> "FeatureMatrix":
        if feature_names is None:
            feature_names = [c for c in df.columns
                             if c not in RESERVED_COLUMNS
                             and pd.api.types.is_numeric_dtype(df[c])]
        X = df[feature_names].apply(pd.to_numeric, errors="coerce")
        # Simple, leakage-safe median imputation is applied per-fold by the trainer; here we
        # just fill any residual NaN with column medians computed on THIS matrix (callers pass
        # train-only frames when fitting).
        X = X.fillna(X.median(numeric_only=True)).fillna(0.0)
        y = pd.to_numeric(df[target_col], errors="coerce")
        baseline = pd.to_numeric(df[baseline_col], errors="coerce")
        dates = pd.to_datetime(df["date"]) if "date" in df.columns else pd.Series(range(len(df)))
        return cls(X=X.reset_index(drop=True), y=y.reset_index(drop=True),
                   baseline=baseline.reset_index(drop=True), dates=dates.reset_index(drop=True),
                   feature_names=list(feature_names))

    def residual_target(self) -> pd.Series:
        return self.y - self.baseline

    def X_for(self, feature_names: Optional[list[str]]) -> pd.DataFrame:
        if not feature_names:
            return self.X
        cols = {}
        for name in feature_names:
            cols[name] = self.X[name] if name in self.X.columns else 0.0
        return pd.DataFrame(cols)

    def __len__(self) -> int:
        return len(self.X)
