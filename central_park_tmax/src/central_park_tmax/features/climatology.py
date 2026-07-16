"""Calendar & climatology features: day-of-year harmonics, normals, anomalies.

Seasonality is encoded with sine/cosine of day-of-year (not month alone) so the annual
cycle is smooth. Climate-normal maximum comes from GHCN 1991-2020 (see ghcn_daily). Recent
observed anomalies (7/14/30-day) are computed leakage-safe from observations strictly before
the target date.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd


def calendar_features(d: date) -> dict:
    doy = d.timetuple().tm_yday
    frac = 2 * np.pi * doy / 365.25
    season = _season(d.month)
    return {
        "day_of_year": doy,
        "doy_sin": float(np.sin(frac)),
        "doy_cos": float(np.cos(frac)),
        "month": d.month,
        "season_winter": 1.0 if season == "winter" else 0.0,
        "season_spring": 1.0 if season == "spring" else 0.0,
        "season_summer": 1.0 if season == "summer" else 0.0,
        "season_autumn": 1.0 if season == "autumn" else 0.0,
    }


def _season(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def season_of(d: date) -> str:
    return _season(d.month)


def normal_max_f(normals: pd.DataFrame, d: date) -> float:
    """Look up the day-of-year climate normal maximum (F)."""
    doy = min(d.timetuple().tm_yday, 365)
    row = normals.loc[normals["doy"] == doy]
    if row.empty:
        return float(normals["normal_tmax_f"].mean())
    return float(row["normal_tmax_f"].iloc[0])


def recent_anomaly_features(daily_tmax: pd.Series, d: date, normals: pd.DataFrame) -> dict:
    """7/14/30-day observed TMAX anomaly vs normal, using ONLY dates strictly before d."""
    if daily_tmax is None or daily_tmax.empty:
        return {}
    idx = pd.to_datetime(daily_tmax.index)
    ser = pd.Series(daily_tmax.to_numpy(dtype=float), index=idx).sort_index()
    cutoff = pd.Timestamp(d)
    prior = ser[ser.index < cutoff]
    out: dict[str, float] = {}
    for win in (7, 14, 30):
        lo = cutoff - pd.Timedelta(days=win)
        chunk = prior[prior.index >= lo]
        if chunk.empty:
            continue
        anoms = []
        for ts, val in chunk.items():
            n = normal_max_f(normals, ts.date())
            anoms.append(val - n)
        out[f"recent_anom_{win}d_f"] = float(np.mean(anoms))
    # Heat-wave / warm-spell indicator: 3+ consecutive prior days >= 90F.
    last3 = prior.tail(3)
    out["recent_heatwave_flag"] = 1.0 if (len(last3) == 3 and (last3 >= 90).all()) else 0.0
    out["recent_warmspell_flag"] = 1.0 if (len(prior.tail(5)) == 5 and
                                           (prior.tail(5) >= prior.tail(5).mean() + 5).sum() >= 3) else 0.0
    return out
