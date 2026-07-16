"""Baseline models: climate normal, persistence, observed-max, raw primary, rolling bias.

All baselines share a minimal fit/predict interface and operate on a feature frame that
contains at least a 'baseline_tmax_f' column (the primary numerical model's daily max for
the target day) and, where relevant, 'normal_tmax_f', 'prev_day_observed_max_f',
'observed_max_so_far_f'.

Rolling-bias correction is implemented leakage-safe: the correction applied to a row uses
ONLY forecast errors from strictly earlier target dates (a shifted rolling mean).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


class Baseline:
    name = "baseline"

    def fit(self, df: pd.DataFrame, target: pd.Series) -> "Baseline":
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:  # pragma: no cover - abstract
        raise NotImplementedError


class ClimateNormalBaseline(Baseline):
    name = "climate_normal"

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return df["normal_tmax_f"].to_numpy(dtype=float)


class PersistenceBaseline(Baseline):
    name = "persistence_prev_day"

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return df["prev_day_observed_max_f"].to_numpy(dtype=float)


class ObservedMaxSoFarBaseline(Baseline):
    """Intraday baseline: predict the maximum already observed today (a hard lower bound)."""
    name = "observed_max_so_far"

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if "observed_max_so_far_f" not in df.columns:
            return np.full(len(df), np.nan)
        return df["observed_max_so_far_f"].to_numpy(dtype=float)


class RawPrimaryBaseline(Baseline):
    name = "raw_primary_model"

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return df["baseline_tmax_f"].to_numpy(dtype=float)


def rolling_bias_series(dates: pd.Series, baseline: pd.Series, target: pd.Series,
                        window_days: int) -> np.ndarray:
    """Leakage-safe rolling bias correction added to baseline.

    For each row i (ordered by date), the bias is the mean of (target - baseline) over the
    prior ``window_days`` calendar days, using ONLY rows with a strictly earlier date. The
    current row's own error is never used.
    """
    order = np.argsort(dates.to_numpy())
    d = pd.to_datetime(dates.to_numpy())[order]
    b = baseline.to_numpy(dtype=float)[order]
    t = target.to_numpy(dtype=float)[order]
    err = t - b
    corrected = np.full(len(d), np.nan)
    for i in range(len(d)):
        lo = d[i] - pd.Timedelta(days=window_days)
        mask = (d < d[i]) & (d >= lo)
        prior = err[mask]
        prior = prior[~np.isnan(prior)]
        bias = float(np.mean(prior)) if prior.size else 0.0
        corrected[i] = b[i] + bias
    # unsort back to original order
    out = np.empty_like(corrected)
    out[order] = corrected
    return out


@dataclass
class RollingBiasBaseline(Baseline):
    window_days: int = 30

    def __post_init__(self):
        self.name = f"rolling_bias_{self.window_days}d"
        self._hist_dates: Optional[np.ndarray] = None
        self._hist_err: Optional[np.ndarray] = None

    def fit(self, df: pd.DataFrame, target: pd.Series) -> "RollingBiasBaseline":
        d = pd.to_datetime(df["date"]).to_numpy()
        err = target.to_numpy(dtype=float) - df["baseline_tmax_f"].to_numpy(dtype=float)
        keep = ~np.isnan(err)
        self._hist_dates = d[keep]
        self._hist_err = err[keep]
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        b = df["baseline_tmax_f"].to_numpy(dtype=float)
        d = pd.to_datetime(df["date"]).to_numpy()
        out = np.copy(b)
        if self._hist_dates is None:
            return out
        for i in range(len(d)):
            lo = d[i] - np.timedelta64(self.window_days, "D")
            mask = (self._hist_dates < d[i]) & (self._hist_dates >= lo)
            prior = self._hist_err[mask]
            bias = float(np.mean(prior)) if prior.size else 0.0
            out[i] = b[i] + bias
        return out
