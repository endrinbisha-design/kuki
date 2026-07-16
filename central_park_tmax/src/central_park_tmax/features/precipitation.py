"""Precipitation-timing and moisture features.

Precipitation is represented with explicit timing windows (not just a 24-hour total), plus
antecedent-moisture context (recent observed precip over 1/3/7/14 days, dry-spell length).
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from ..time_utils import to_local


def precip_timing_features(hourly: pd.DataFrame, d: date,
                           pop_col: str = "prob_precip_pct",
                           qpf_col: str = "qpf_in") -> dict:
    out: dict[str, float] = {}
    if hourly is None or hourly.empty or "valid_time_utc" not in hourly:
        return out
    ts = pd.to_datetime(hourly["valid_time_utc"], utc=True)
    local_hours = ts.apply(lambda t: to_local(t.to_pydatetime()).hour).to_numpy()

    if pop_col in hourly:
        pop = hourly[pop_col].to_numpy(dtype=float)
        out["pop_day_max_pct"] = float(np.nanmax(pop)) if np.isfinite(pop).any() else np.nan
        out["pop_day_mean_pct"] = float(np.nanmean(pop))
    if qpf_col in hourly:
        qpf = np.nan_to_num(hourly[qpf_col].to_numpy(dtype=float))
        windows = {"pre9am": (0, 9), "pre_noon": (0, 12),
                   "noon_to_5pm": (12, 17), "after_5pm": (17, 24)}
        for name, (h0, h1) in windows.items():
            mask = (local_hours >= h0) & (local_hours < h1)
            out[f"qpf_{name}_in"] = float(np.sum(qpf[mask]))
        out["qpf_total_in"] = float(np.sum(qpf))
    return out


def antecedent_moisture_features(daily_prcp_mm: pd.Series, d: date) -> dict:
    """Recent observed precipitation and dry-spell length using ONLY dates before d."""
    if daily_prcp_mm is None or daily_prcp_mm.empty:
        return {}
    idx = pd.to_datetime(daily_prcp_mm.index)
    ser = pd.Series(daily_prcp_mm.to_numpy(dtype=float), index=idx).sort_index()
    cutoff = pd.Timestamp(d)
    prior = ser[ser.index < cutoff]
    out: dict[str, float] = {}
    for win in (1, 3, 7, 14):
        lo = cutoff - pd.Timedelta(days=win)
        chunk = prior[prior.index >= lo]
        out[f"precip_prev_{win}d_mm"] = float(np.nansum(chunk.to_numpy())) if not chunk.empty else 0.0
    out["wet_ground_flag"] = 1.0 if out.get("precip_prev_3d_mm", 0.0) > 5.0 else 0.0
    # Antecedent dry-spell length (consecutive prior days with < 0.2 mm).
    dry = 0
    for val in reversed(prior.to_numpy()):
        if np.isnan(val) or val < 0.2:
            dry += 1
        else:
            break
    out["dry_spell_days"] = float(dry)
    return out
