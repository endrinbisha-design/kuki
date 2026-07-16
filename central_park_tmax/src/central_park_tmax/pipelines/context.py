"""Shared helpers for assembling observation history and climate normals for pipelines."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from ..data.ghcn_daily import climate_normals_1991_2020
from ..data.synthetic import WeatherState, _climate_normal_max_f


def synthetic_daily_history(start: date, end: date) -> dict:
    """Build a synthetic daily TMAX/PRCP history + climate normals for offline runs.

    Returns dict with 'tmax_f' (date-indexed Series), 'prcp_mm' (Series), and 'normals'
    (doy -> normal_tmax_f DataFrame). Deterministic per date via the synthetic generator.
    """
    dates, tmax, prcp = [], [], []
    d = start
    while d <= end:
        st = WeatherState(d)
        dates.append(pd.Timestamp(d))
        tmax.append(st.true_max_f)
        prcp.append(st.precip_in * 25.4)  # inches -> mm
        d += timedelta(days=1)
    tmax_s = pd.Series(tmax, index=pd.DatetimeIndex(dates), name="tmax_f")
    prcp_s = pd.Series(prcp, index=pd.DatetimeIndex(dates), name="prcp_mm")

    # Normals directly from the smooth synthetic climatology function.
    doys = list(range(1, 367))
    normals = pd.DataFrame({
        "doy": doys,
        "normal_tmax_f": [_climate_normal_max_f(date(2021, 1, 1) + timedelta(days=i - 1))
                          for i in doys],
    })
    return {"tmax_f": tmax_s, "prcp_mm": prcp_s, "normals": normals}


def daily_history_from_ghcn(ghcn_df: pd.DataFrame) -> dict:
    """Extract date-indexed TMAX(F)/PRCP(mm) series and 1991-2020 normals from GHCN frame."""
    df = ghcn_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    tmax_s = df.set_index("date")["tmax_f"].dropna()
    prcp_s = df.set_index("date")["prcp_mm"].dropna() if "prcp_mm" in df else pd.Series(dtype=float)
    normals = climate_normals_1991_2020(ghcn_df)
    return {"tmax_f": tmax_s, "prcp_mm": prcp_s, "normals": normals}
