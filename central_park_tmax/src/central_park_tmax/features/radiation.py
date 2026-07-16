"""Cloud & solar-radiation features and documented radiation proxies.

Where direct shortwave radiation is unavailable (the common case for the NWS gridpoint and
several GRIB fields we extract), we build documented proxies from cloud cover, solar
elevation, and day length. Solar geometry uses a standard NOAA-style approximation.
"""
from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd

from ..constants import STATION
from ..time_utils import local_day_bounds_utc, to_local


def solar_declination_deg(d: date) -> float:
    doy = d.timetuple().tm_yday
    return -23.44 * np.cos(np.deg2rad(360.0 / 365.0 * (doy + 10)))


def day_length_hours(d: date, lat: float = STATION.latitude) -> float:
    decl = np.deg2rad(solar_declination_deg(d))
    phi = np.deg2rad(lat)
    x = -np.tan(phi) * np.tan(decl)
    x = np.clip(x, -1.0, 1.0)
    ha = np.arccos(x)
    return float(2 * np.rad2deg(ha) / 15.0)


def solar_elevation_deg(dt_local: datetime, lat: float = STATION.latitude,
                        lon: float = STATION.longitude) -> float:
    d = dt_local.date()
    decl = np.deg2rad(solar_declination_deg(d))
    phi = np.deg2rad(lat)
    hour = dt_local.hour + dt_local.minute / 60.0
    hour_angle = np.deg2rad(15.0 * (hour - 12.0))
    sin_elev = np.sin(phi) * np.sin(decl) + np.cos(phi) * np.cos(decl) * np.cos(hour_angle)
    return float(np.rad2deg(np.arcsin(np.clip(sin_elev, -1, 1))))


def cloud_radiation_features(hourly: pd.DataFrame, d: date,
                             cloud_col: str = "cloud_frac") -> dict:
    """Aggregate cloud cover and build clear-sky-weighted radiation proxies over the day."""
    out: dict[str, float] = {"day_length_hours": day_length_hours(d)}
    if hourly is None or hourly.empty or "valid_time_utc" not in hourly:
        return out
    ts = pd.to_datetime(hourly["valid_time_utc"], utc=True)
    local_hours = ts.apply(lambda t: to_local(t.to_pydatetime()).hour)
    cloud = (hourly[cloud_col].to_numpy(dtype=float) if cloud_col in hourly
             else np.full(len(hourly), np.nan))

    def _mean_between(h0, h1):
        mask = (local_hours >= h0) & (local_hours < h1)
        vals = cloud[mask.to_numpy()]
        vals = vals[~np.isnan(vals)]
        return float(np.mean(vals)) if vals.size else np.nan

    out["cloud_daylight_mean"] = _mean_between(6, 20)
    out["cloud_morning_mean"] = _mean_between(6, 12)
    out["cloud_noon_to_4pm_mean"] = _mean_between(12, 16)

    # Clear-sky insolation proxy: sum over daylight hours of sin(elevation)*(1 - cloud).
    proxy = 0.0
    proxy_prenoon = 0.0
    for t, c in zip(ts, cloud):
        local = to_local(t.to_pydatetime())
        elev = solar_elevation_deg(local)
        if elev <= 0:
            continue
        contrib = np.sin(np.deg2rad(elev)) * (1.0 - (0.0 if np.isnan(c) else c))
        proxy += contrib
        if local.hour < 12:
            proxy_prenoon += contrib
    out["insolation_proxy"] = float(proxy)
    out["insolation_proxy_prenoon"] = float(proxy_prenoon)
    return out
