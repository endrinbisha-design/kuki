"""Hourly / sub-hourly observation retrieval and normalization.

Primary implemented source: the NWS observations API (api.weather.gov/stations/KNYC),
which returns METAR-derived hourly observations with temperature, dew point, wind, etc.

Local Climatological Data (LCD) and ISD bulk archives are declared but not fully wired
here; ``load_lcd`` raises a documented NotImplementedError explaining how to enable it.
The rest of the pipeline runs without them.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from ..constants import c_to_f
from ..logging_config import get_logger
from .nws_api import NwsApiClient

log = get_logger(__name__)


def _c_or_none(props: dict, key: str) -> Optional[float]:
    node = props.get(key) or {}
    val = node.get("value")
    unit = node.get("unitCode", "")
    if val is None:
        return None
    if "degC" in unit:
        return float(val)
    if "degF" in unit:
        return (float(val) - 32.0) * 5.0 / 9.0
    return float(val)


def observations_to_frame(geojson: dict) -> pd.DataFrame:
    """Normalize NWS observations GeoJSON into a tidy hourly frame."""
    feats = geojson.get("features", [])
    rows = []
    for f in feats:
        p = f.get("properties", {})
        temp_c = _c_or_none(p, "temperature")
        dew_c = _c_or_none(p, "dewpoint")
        rows.append({
            "timestamp_utc": p.get("timestamp"),
            "temp_c": temp_c,
            "temp_f": c_to_f(temp_c) if temp_c is not None else np.nan,
            "dewpoint_c": dew_c,
            "dewpoint_f": c_to_f(dew_c) if dew_c is not None else np.nan,
            "wind_dir_deg": (p.get("windDirection") or {}).get("value"),
            "wind_speed_kmh": (p.get("windSpeed") or {}).get("value"),
            "wind_gust_kmh": (p.get("windGust") or {}).get("value"),
            "sea_level_pressure_pa": (p.get("seaLevelPressure") or {}).get("value"),
            "relative_humidity_pct": (p.get("relativeHumidity") or {}).get("value"),
            "visibility_m": (p.get("visibility") or {}).get("value"),
            "raw_metar": p.get("rawMessage"),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("timestamp_utc").reset_index(drop=True)
    return df


def fetch_recent_observations(nws: NwsApiClient, station_icao: str, start_iso: str) -> pd.DataFrame:
    geojson = nws.observations_since(station_icao, start_iso)
    return observations_to_frame(geojson)


def observed_max_so_far_f(obs: pd.DataFrame, target_date, tz_now_utc: datetime) -> Optional[float]:
    """Maximum observed temperature so far within the local target day, up to now.

    Only observations at/ before ``tz_now_utc`` and within the local target day count.
    """
    from ..time_utils import is_in_local_day, to_utc
    if obs.empty or "temp_f" not in obs.columns:
        return None
    ts = pd.to_datetime(obs["timestamp_utc"], utc=True, errors="coerce")
    keep = []
    for t, temp in zip(ts, obs["temp_f"]):
        if pd.isna(t) or pd.isna(temp):
            continue
        tt = to_utc(t.to_pydatetime())
        if tt <= tz_now_utc and is_in_local_day(tt, target_date):
            keep.append(float(temp))
    return max(keep) if keep else None


def load_lcd(*args, **kwargs):  # pragma: no cover - documented stub
    raise NotImplementedError(
        "LCD bulk loader is not wired in this build. To enable: download NOAA LCD CSV for "
        "WBAN 94728 from https://www.ncei.noaa.gov/data/local-climatological-data/ and add a "
        "parser here. The NWS observations API path is used by default and requires no setup."
    )
