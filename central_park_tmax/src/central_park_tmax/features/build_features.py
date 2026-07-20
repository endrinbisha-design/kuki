"""Assemble a single leakage-safe feature row from a forecast run + observations + climatology.

A feature row corresponds to one (target_date, forecast_vintage) example. It combines:
  * direct guidance (primary baseline daily max, inter-model spread when multiple sources),
  * temperature trajectory at configured local hours + warming/cooling features,
  * wind (vector components / onshore flow), radiation/cloud, precipitation timing,
  * spatial gradients + neighborhood stats,
  * calendar & recent-anomaly climatology,
  * intraday features (only for same-day issue times).

The row also carries bookkeeping columns (date, baseline_tmax_f, provenance, issue times) that
are excluded from the design matrix by FeatureMatrix.RESERVED_COLUMNS.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import numpy as np
import pandas as pd

from ..time_utils import isoformat_local, isoformat_utc, local_datetime, to_local, to_utc
from . import climatology, precipitation, radiation, spatial, wind
from .intraday import intraday_features


def _trajectory_temps(run, target_date: date, location_key: str, hours_local: list[int]) -> dict:
    df = run.per_location_hourly.get(location_key)
    out: dict[str, float] = {}
    if df is None or df.empty or "temp_f" not in df.columns:
        return out
    ts = pd.to_datetime(df["valid_time_utc"], utc=True)
    temps = pd.to_numeric(df["temp_f"], errors="coerce").to_numpy()
    local_hours = ts.apply(lambda t: to_local(t.to_pydatetime()).hour).to_numpy()
    local_dates = ts.apply(lambda t: to_local(t.to_pydatetime()).date()).to_numpy()
    for h in hours_local:
        mask = (local_hours == h) & (local_dates == target_date)
        vals = temps[mask]
        if vals.size:
            out[f"fc_temp_{h:02d}z_local_f"] = float(vals[0])
    # Warming/cooling structure.
    def _g(h):
        return out.get(f"fc_temp_{h:02d}z_local_f")
    if _g(6) is not None and _g(12) is not None:
        out["warming_6_to_12_f"] = _g(12) - _g(6)
    if _g(9) is not None and _g(15) is not None:
        out["warming_9_to_15_f"] = _g(15) - _g(9)
    if _g(12) is not None and _g(15) is not None:
        out["warming_12_to_15_f"] = _g(15) - _g(12)
    if _g(15) is not None and _g(21) is not None:
        out["late_afternoon_cooling_f"] = _g(15) - _g(21)
    # Forecast hour of maximum + overnight minimum within the local day.
    day_mask = (local_dates == target_date)
    if day_mask.any():
        day_temps = temps[day_mask]
        day_hours = local_hours[day_mask]
        if day_temps.size:
            out["fc_hour_of_max_local"] = float(day_hours[int(np.nanargmax(day_temps))])
            out["fc_overnight_min_f"] = float(np.nanmin(day_temps[day_hours <= 8])) if (day_hours <= 8).any() else float(np.nanmin(day_temps))
    return out


def build_feature_row(
    target_date: date,
    vintage_name: str,
    issue_local: datetime,
    primary_run,
    locations,
    normals: pd.DataFrame,
    daily_tmax_f: Optional[pd.Series] = None,
    daily_prcp_mm: Optional[pd.Series] = None,
    obs: Optional[pd.DataFrame] = None,
    extra_runs: Optional[dict] = None,
    trajectory_hours: Optional[list[int]] = None,
    reporting_method: str = "round_half_up",
    intraday_report_max_f: Optional[float] = None,
) -> dict:
    trajectory_hours = trajectory_hours or [0, 3, 6, 9, 12, 15, 18, 21]
    issue_utc = to_utc(issue_local)
    primary_key = locations.primary.key

    row: dict = {
        "date": target_date.isoformat(),
        "target_date": target_date.isoformat(),
        "vintage": vintage_name,
        "forecast_issue_local": isoformat_local(issue_local),
        "forecast_issue_utc": isoformat_utc(issue_utc),
        "forecast_init_utc": isoformat_utc(primary_run.init_utc),
        "forecast_source": primary_run.source,
        "forecast_model_version": primary_run.model_version or "",
        "provenance": primary_run.provenance,
    }

    # --- direct guidance ---
    baseline = primary_run.daily_max_f(primary_key, target_date)
    row["baseline_tmax_f"] = baseline
    row["primary_lead_hours"] = primary_run.lead_time_hours(target_date)

    # inter-model features
    model_maxes = {primary_run.source: baseline}
    if extra_runs:
        for src, r in extra_runs.items():
            model_maxes[src] = r.daily_max_f(primary_key, target_date)
    valid_maxes = [v for v in model_maxes.values() if v is not None]
    if len(valid_maxes) >= 2:
        row["intermodel_spread_f"] = float(np.std(valid_maxes))
        row["intermodel_range_f"] = float(np.max(valid_maxes) - np.min(valid_maxes))
        row["intermodel_mean_f"] = float(np.mean(valid_maxes))
    for src, v in model_maxes.items():
        if v is not None:
            row[f"model_{src}_tmax_f"] = float(v)

    # --- trajectory ---
    row.update(_trajectory_temps(primary_run, target_date, primary_key, trajectory_hours))

    # --- wind (from primary run hourly at Central Park) ---
    cp_hourly = primary_run.per_location_hourly.get(primary_key)
    row.update(wind.summarize_wind(cp_hourly))

    # --- radiation / cloud ---
    row.update(radiation.cloud_radiation_features(cp_hourly, target_date))

    # --- precipitation ---
    row.update(precipitation.precip_timing_features(cp_hourly, target_date))
    if daily_prcp_mm is not None:
        row.update(precipitation.antecedent_moisture_features(daily_prcp_mm, target_date))

    # --- spatial ---
    row.update(spatial.gradient_features(primary_run, target_date, locations))
    neigh_keys = [p.key for p in locations.neighbors]
    row.update(spatial.neighborhood_temperature_stats(primary_run, target_date, neigh_keys))

    # --- calendar & climatology ---
    row.update(climatology.calendar_features(target_date))
    row["normal_tmax_f"] = climatology.normal_max_f(normals, target_date)
    if baseline is not None:
        row["baseline_minus_normal_f"] = float(baseline - row["normal_tmax_f"])
    if daily_tmax_f is not None:
        row.update(climatology.recent_anomaly_features(daily_tmax_f, target_date, normals))
        # previous day's observed max
        idx = pd.to_datetime(daily_tmax_f.index)
        ser = pd.Series(daily_tmax_f.to_numpy(dtype=float), index=idx).sort_index()
        prev = ser[ser.index < pd.Timestamp(target_date)]
        if not prev.empty:
            row["prev_day_observed_max_f"] = float(prev.iloc[-1])

    # --- intraday ---
    same_hour_fc = _trajectory_temps(primary_run, target_date, primary_key,
                                     [to_local(issue_utc).hour]).get(
        f"fc_temp_{to_local(issue_utc).hour:02d}z_local_f")
    remaining_max = _remaining_forecast_max(primary_run, primary_key, target_date, issue_utc)
    row.update(intraday_features(obs, target_date, issue_utc,
                                 forecast_remaining_max_f=remaining_max,
                                 same_hour_forecast_temp_f=same_hour_fc,
                                 intraday_report_max_f=intraday_report_max_f))
    return row


def _remaining_forecast_max(run, key: str, target_date: date, issue_utc: datetime) -> Optional[float]:
    from ..time_utils import is_in_local_day
    df = run.per_location_hourly.get(key)
    if df is None or df.empty or "temp_f" not in df.columns:
        return None
    ts = pd.to_datetime(df["valid_time_utc"], utc=True)
    temps = pd.to_numeric(df["temp_f"], errors="coerce").to_numpy()
    keep = []
    for t, temp in zip(ts, temps):
        tt = to_utc(t.to_pydatetime())
        if tt >= issue_utc and is_in_local_day(tt, target_date) and not np.isnan(temp):
            keep.append(float(temp))
    return max(keep) if keep else None
