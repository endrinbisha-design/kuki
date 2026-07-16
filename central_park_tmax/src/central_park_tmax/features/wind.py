"""Meteorologically-correct wind features.

Wind direction reported by NWS/METAR is the direction FROM WHICH the wind blows (the
'meteorological' convention). Raw degrees must NEVER be used as an ordinary linear feature
because 359 deg and 1 deg are ~2 deg apart, not ~358. We convert (direction, speed) to
signed vector components and to physically-meaningful projections (onshore/offshore, etc.).

For NYC / Central Park the marine ('onshore') sector is broadly from the south-southeast to
east (the ocean lies to the S/SE and the harbor/sound to the S/E). We use an onshore
reference bearing of 150 deg (SSE); the onshore component is the projection of the wind's
source-direction unit vector onto that reference.
"""
from __future__ import annotations

import numpy as np

# Reference bearing (deg, FROM which onshore marine air arrives at Central Park).
ONSHORE_REFERENCE_DEG = 150.0


def _dir_to_radians(direction_deg):
    return np.deg2rad(np.asarray(direction_deg, dtype=float))


def wind_components(direction_deg, speed):
    """Return (u, v) meteorological wind components.

    u = zonal (positive eastward wind => wind blowing TO the east, i.e. a westerly),
    v = meridional (positive northward). Using the meteorological FROM-direction:
        u = -speed * sin(dir),   v = -speed * cos(dir).
    A wind FROM 270 deg (west) has u = -speed*sin(270)= +speed (blowing east) => westerly. OK.
    """
    d = _dir_to_radians(direction_deg)
    s = np.asarray(speed, dtype=float)
    u = -s * np.sin(d)
    v = -s * np.cos(d)
    return u, v


def direction_unit_vector(direction_deg):
    """Unit vector pointing in the FROM-direction (for circular similarity/gradients)."""
    d = _dir_to_radians(direction_deg)
    return np.cos(d), np.sin(d)


def angular_difference_deg(a_deg, b_deg):
    """Smallest signed angular difference a-b in (-180, 180]. 359 vs 1 -> -2."""
    diff = (np.asarray(a_deg, dtype=float) - np.asarray(b_deg, dtype=float) + 180.0) % 360.0 - 180.0
    return diff


def onshore_component(direction_deg, speed, reference_deg: float = ONSHORE_REFERENCE_DEG):
    """Positive => onshore (marine) flow; negative => offshore.

    Projection of the source-direction unit vector onto the onshore reference unit vector,
    scaled by wind speed. Wind FROM the reference bearing gives the maximum onshore value.
    """
    du, dv = direction_unit_vector(direction_deg)
    ru, rv = direction_unit_vector(reference_deg)
    proj = du * ru + dv * rv
    return proj * np.asarray(speed, dtype=float)


def offshore_component(direction_deg, speed, reference_deg: float = ONSHORE_REFERENCE_DEG):
    return -onshore_component(direction_deg, speed, reference_deg)


def southerly_component(direction_deg, speed):
    """Positive for winds from the south (v < 0 means from north; from-south => positive)."""
    _, v = wind_components(direction_deg, speed)
    return -v  # wind FROM south blows northward (v>0); 'southerly component' positive for southerly


def easterly_component(direction_deg, speed):
    u, _ = wind_components(direction_deg, speed)
    return -u  # wind FROM east blows westward (u<0); easterly component positive for easterly


def calm_indicator(speed, threshold: float = 2.0):
    return (np.asarray(speed, dtype=float) < threshold).astype(float)


def summarize_wind(hourly, dir_col: str = "wind_dir_deg", speed_col: str = "wind_speed_mph",
                   gust_col: str = "wind_gust_mph") -> dict:
    """Aggregate hourly wind into daily features via vector means (never scalar-averaging deg)."""
    import pandas as pd
    if hourly is None or len(hourly) == 0 or dir_col not in hourly:
        return {}
    d = hourly[dir_col].to_numpy(dtype=float)
    s = (hourly[speed_col].to_numpy(dtype=float) if speed_col in hourly
         else np.ones_like(d))
    u, v = wind_components(d, s)
    on = onshore_component(d, s)
    out = {
        "wind_u_mean": float(np.nanmean(u)),
        "wind_v_mean": float(np.nanmean(v)),
        "wind_speed_mean_mph": float(np.nanmean(s)),
        "wind_speed_max_mph": float(np.nanmax(s)),
        "onshore_component_mean": float(np.nanmean(on)),
        "onshore_component_max": float(np.nanmax(on)),
        "offshore_component_mean": float(-np.nanmean(on)),
        "southerly_component_mean": float(np.nanmean(southerly_component(d, s))),
        "easterly_component_mean": float(np.nanmean(easterly_component(d, s))),
        "calm_fraction": float(np.nanmean(calm_indicator(s))),
    }
    if gust_col in hourly:
        out["wind_gust_max_mph"] = float(np.nanmax(hourly[gust_col].to_numpy(dtype=float)))
    # Onset hour of onshore flow (first hour with positive onshore component), local hour.
    if "valid_time_utc" in hourly:
        from ..time_utils import to_local
        onshore_pos = on > 0
        if onshore_pos.any():
            ts = pd.to_datetime(hourly["valid_time_utc"], utc=True)
            first = ts[onshore_pos].iloc[0] if hasattr(ts[onshore_pos], "iloc") else None
            if first is not None:
                out["onshore_onset_hour_local"] = float(to_local(first.to_pydatetime()).hour)
    return out
