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
    NOTE: this is the *hourly-snapshot* max, which under-samples the true daily peak
    (peaks between hourly obs are missed). For a floor/feature that matches the NWS
    report, use ``max_so_far_with_provenance`` instead.
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


def max_so_far_with_provenance(
    obs: Optional[pd.DataFrame],
    target_date,
    tz_now_utc: datetime,
    intraday_report_max_f: Optional[float] = None,
) -> tuple[Optional[float], str]:
    """Best-available max-so-far for the local target day, up to ``tz_now_utc``, + its source.

    Combines three sources and returns the maximum (the true peak can only be >= any of
    them), tagged with the winning source:
      * ``metar_hourly``  : max of routine hourly 2 m temperatures (under-samples peaks),
      * ``metar_6h_group``: max of the METAR 6-hour maximum-temperature remark groups,
        which record the true peak between hourly obs (the KNYC 1:25 PM peak my hourly
        pull missed on 2026-07-20 lives here),
      * ``nws_cli_intraday``: the maximum from an intraday CLI report (the authoritative
        settlement source), when one has been issued and is available at prediction time.

    ``intraday_report_max_f`` must be supplied ONLY when a CLI issued at/before
    ``tz_now_utc`` is genuinely available (no lookahead in backtests).
    """
    from ..time_utils import is_in_local_day, to_utc
    from .metar import six_hour_max_f

    candidates: dict[str, float] = {}
    if obs is not None and not obs.empty and "temp_f" in obs.columns:
        ts = pd.to_datetime(obs["timestamp_utc"], utc=True, errors="coerce")
        hourly, six_group = [], []
        raws = obs["raw_metar"] if "raw_metar" in obs.columns else [None] * len(obs)
        for t, temp, raw in zip(ts, obs["temp_f"], raws):
            if pd.isna(t):
                continue
            tt = to_utc(t.to_pydatetime())
            if not (tt <= tz_now_utc and is_in_local_day(tt, target_date)):
                continue
            if pd.notna(temp):
                hourly.append(float(temp))
            if isinstance(raw, str) and raw:
                v6 = six_hour_max_f(raw)
                if v6 is not None:
                    six_group.append(v6)
        if hourly:
            candidates["metar_hourly"] = max(hourly)
        if six_group:
            candidates["metar_6h_group"] = max(six_group)
    if intraday_report_max_f is not None and not (
            isinstance(intraday_report_max_f, float) and np.isnan(intraday_report_max_f)):
        candidates["nws_cli_intraday"] = float(intraday_report_max_f)

    if not candidates:
        return None, "none"
    source = max(candidates, key=candidates.get)
    return candidates[source], source


def load_lcd(*args, **kwargs):  # pragma: no cover - documented stub
    raise NotImplementedError(
        "LCD bulk loader is not wired in this build. To enable: download NOAA LCD CSV for "
        "WBAN 94728 from https://www.ncei.noaa.gov/data/local-climatological-data/ and add a "
        "parser here. The NWS observations API path is used by default and requires no setup."
    )
