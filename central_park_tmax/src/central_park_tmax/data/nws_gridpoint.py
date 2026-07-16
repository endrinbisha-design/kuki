"""Fully-implemented NWS gridpoint forecast source (current data, credential-free JSON).

This is the reference forecast source that works with no GRIB dependencies. It fetches the
hourly gridpoint forecast from api.weather.gov for each configured location and builds
per-location hourly temperature frames. It is CURRENT-DATA ONLY: api.weather.gov does not
serve historical point-in-time runs, so ``list_available_runs`` only offers a run when the
prediction time is near 'now'. For historical backtests, use the GRIB archive sources or
the synthetic source.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from ..constants import c_to_f
from ..logging_config import get_logger
from ..time_utils import now_utc
from . import DataSourceError, ForecastSourceUnavailable
from .forecast_base import ForecastRun, ForecastSource, RunHandle
from .nws_api import NwsApiClient

log = get_logger(__name__)


class NwsGridpointForecastSource(ForecastSource):
    name = "nws_gridpoint"

    def __init__(self, nws: NwsApiClient, freshness_hours: float = 3.0):
        self.nws = nws
        self.freshness_hours = freshness_hours

    def list_available_runs(self, target_date: date, issued_before_utc: datetime) -> list[RunHandle]:
        # Current-data only: usable when the prediction time is within freshness of now.
        now = now_utc()
        if abs((issued_before_utc - now).total_seconds()) > self.freshness_hours * 3600:
            return []
        init = issued_before_utc.replace(minute=0, second=0, microsecond=0)
        return [RunHandle(source=self.name, init_utc=init,
                          cycle=init.strftime("%Y-%m-%dT%HZ"),
                          availability_estimate_utc=init, model_version="nws_gridpoint")]

    def fetch_run(self, run: RunHandle, locations, target_date: date) -> ForecastRun:
        per_loc: dict[str, pd.DataFrame] = {}
        grid_coords: dict[str, tuple[float, float]] = {}
        for p in locations.all_points():
            try:
                gj = self.nws.gridpoint_forecast_hourly(p.latitude, p.longitude)
            except DataSourceError as exc:
                log.warning("NWS gridpoint fetch failed for %s: %s", p.key, exc)
                continue
            df = _hourly_geojson_to_frame(gj)
            if not df.empty:
                per_loc[p.key] = df
                grid_coords[p.key] = (p.latitude, p.longitude)
        if not per_loc:
            raise ForecastSourceUnavailable(
                "NWS gridpoint returned no usable data for any location (network/API issue)."
            )
        return ForecastRun(
            source=self.name, init_utc=run.init_utc, cycle=run.cycle,
            per_location_hourly=per_loc, availability_estimate_utc=run.availability_estimate_utc,
            model_version="nws_gridpoint", variable_units={"temp_f": "degF"},
            grid_coords=grid_coords, provenance="nws_gridpoint_json",
        )


def _hourly_geojson_to_frame(gj: dict) -> pd.DataFrame:
    periods = gj.get("properties", {}).get("periods", [])
    rows = []
    for pr in periods:
        temp = pr.get("temperature")
        unit = pr.get("temperatureUnit", "F")
        if temp is None:
            continue
        temp_f = float(temp) if unit == "F" else c_to_f(float(temp))
        wind_speed = _parse_wind_speed(pr.get("windSpeed"))
        rows.append({
            "valid_time_utc": pr.get("startTime"),
            "temp_f": temp_f,
            "wind_dir_cardinal": pr.get("windDirection"),
            "wind_speed_mph": wind_speed,
            "prob_precip_pct": (pr.get("probabilityOfPrecipitation") or {}).get("value"),
            "dewpoint_c": (pr.get("dewpoint") or {}).get("value"),
            "rh_pct": (pr.get("relativeHumidity") or {}).get("value"),
            "short_forecast": pr.get("shortForecast"),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["valid_time_utc"] = pd.to_datetime(df["valid_time_utc"], utc=True, errors="coerce")
        df = df.sort_values("valid_time_utc").reset_index(drop=True)
    return df


def _parse_wind_speed(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    nums = [int(tok) for tok in s.replace("mph", "").replace("to", " ").split() if tok.isdigit()]
    return float(np.mean(nums)) if nums else None
