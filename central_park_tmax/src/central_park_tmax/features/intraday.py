"""Intraday / forecast-vintage features for same-day forecasts.

For forecasts issued during the target day we incorporate the maximum observed so far, hours
remaining, expected remaining warming, and observed-vs-forecast error so far. These features
only use observations available at (<=) the forecast issue time.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import numpy as np
import pandas as pd

from ..time_utils import hours_remaining_in_local_day, is_in_local_day, to_utc


def intraday_features(
    obs: Optional[pd.DataFrame],
    target_date: date,
    issue_utc: datetime,
    forecast_remaining_max_f: Optional[float] = None,
    same_hour_forecast_temp_f: Optional[float] = None,
) -> dict:
    """Build intraday features from observations available up to ``issue_utc``.

    ``obs`` must have 'timestamp_utc' and 'temp_f'. Only obs within the local target day and
    at/before issue time are used (leakage-safe by construction).
    """
    out: dict[str, float] = {
        "hours_remaining_in_day": float(hours_remaining_in_local_day(issue_utc, target_date)),
    }
    if obs is None or obs.empty or "temp_f" not in obs.columns:
        out["is_intraday"] = 0.0
        return out

    ts = pd.to_datetime(obs["timestamp_utc"], utc=True, errors="coerce")
    temps, times = [], []
    for t, temp in zip(ts, obs["temp_f"]):
        if pd.isna(t) or pd.isna(temp):
            continue
        tt = to_utc(t.to_pydatetime())
        if tt <= issue_utc and is_in_local_day(tt, target_date):
            temps.append(float(temp))
            times.append(tt)
    if not temps:
        out["is_intraday"] = 0.0
        return out

    out["is_intraday"] = 1.0
    obs_max = max(temps)
    out["observed_max_so_far_f"] = obs_max
    out["current_temp_f"] = temps[-1]
    # Observed warming rate over the last few hours (F/hour).
    if len(temps) >= 3:
        span_h = max(1e-6, (times[-1] - times[0]).total_seconds() / 3600.0)
        out["observed_warming_rate_f_per_h"] = float((temps[-1] - temps[0]) / span_h)
    if same_hour_forecast_temp_f is not None:
        out["obs_minus_forecast_so_far_f"] = float(temps[-1] - same_hour_forecast_temp_f)
    if forecast_remaining_max_f is not None:
        out["expected_remaining_max_f"] = float(forecast_remaining_max_f)
        out["prob_exceed_current_proxy_f"] = float(forecast_remaining_max_f - obs_max)
    return out


def apply_observed_max_constraint(predicted_max_f: float, observed_max_so_far_f: Optional[float]) -> float:
    """Enforce final_daily_max = max(observed_max_so_far, predicted). Never below observed."""
    if observed_max_so_far_f is None or (isinstance(observed_max_so_far_f, float)
                                         and np.isnan(observed_max_so_far_f)):
        return predicted_max_f
    return float(max(observed_max_so_far_f, predicted_max_f))
