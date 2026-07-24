"""HRRR hourly afternoon-shape extraction (sea-breeze piece 4; see SEA_BREEZE.md).

HRRR at 3 km partially resolves the NYC sea breeze, but the daily-max pipeline throws
that away by extracting only Tmax. This module pulls the HOURLY afternoon trace of
2 m temperature and 10 m wind at Central Park + JFK from a single HRRR run and distills
it into shape features:

  * does HRRR itself flatten CP's curve after midday (early peak / small afternoon range)?
  * how many afternoon hours does HRRR turn the CP wind onshore (SE-S, 90-200 deg)?
  * how big is HRRR's own CP-JFK afternoon gap (marine air at the coast)?

Byte-range GRIB subsetting via Herbie (same machinery as data/_herbie.py); ~9 forecast
hours x 1 combined TMP+UGRD+VGRD subset each. Advisory-only and opt-in at predict time
(env CPT_HRRR_SHAPE=1) because it costs ~1-2 min of downloads per call.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd

from ..logging_config import get_logger
from ._herbie import _extract_points_kelvin, _require_herbie
from .hrrr import HrrrForecastSource

log = get_logger(__name__)

ONSHORE_LO, ONSHORE_HI = 90, 200
LOCAL_HOURS = list(range(10, 19))        # 10:00-18:00 local: the cap window


def _wind_dir_speed(u: float, v: float) -> tuple[float, float]:
    """Meteorological direction (deg FROM) and speed (kt) from u/v in m/s."""
    spd_kt = math.hypot(u, v) * 1.94384
    direction = (math.degrees(math.atan2(-u, -v))) % 360
    return direction, spd_kt


def fetch_afternoon_trace(cfg, target_date: date,
                          issued_before_utc: Optional[datetime] = None) -> Optional[pd.DataFrame]:
    """Hourly CP+JFK afternoon trace (temp_f, wind dir/speed) from the newest usable HRRR run.

    Returns a DataFrame indexed by local hour with columns
    cp_temp_f, jfk_temp_f, cp_wdir, cp_wspd_kt, or None when HRRR/Herbie is unavailable.
    """
    _require_herbie()
    from herbie import Herbie

    tz = ZoneInfo(cfg.station.timezone)
    src = HrrrForecastSource()
    issued = issued_before_utc or datetime.now(timezone.utc)
    run = src.select_run(target_date, issued)
    if run is None:
        return None
    init = run.init_utc
    pts = [("cp", cfg.locations.primary.latitude, cfg.locations.primary.longitude)]
    jfk = next((n for n in cfg.locations.neighbors if n.key == "jfk"), None)
    if jfk is not None:
        pts.append(("jfk", jfk.latitude, jfk.longitude))

    rows = []
    for hour in LOCAL_HOURS:
        valid_local = datetime(target_date.year, target_date.month, target_date.day,
                               hour, tzinfo=tz)
        fxx = int((valid_local.astimezone(timezone.utc) - init).total_seconds() // 3600)
        if fxx < 1 or fxx > src.max_fxx:
            continue
        try:
            H = Herbie(init.replace(tzinfo=None), model="hrrr", product="sfc", fxx=fxx,
                       priority=["aws"], verbose=False)
            if H.grib is None:
                raise FileNotFoundError("no GRIB on aws")
            row = {"hour_local": hour}
            t = H.xarray(":TMP:2 m above ground:", remove_grib=True)
            kel = _extract_points_kelvin(t, pts)
            for k, v in kel.items():
                row[f"{k}_temp_f"] = (v - 273.15) * 9 / 5 + 32
            t.close()
            w = H.xarray(":(?:UGRD|VGRD):10 m above ground:", remove_grib=True)
            wds = w if not isinstance(w, list) else w[0]
            uvar = next(v for v in wds.data_vars if v.startswith("u"))
            vvar = next(v for v in wds.data_vars if v.startswith("v"))
            u = _extract_points_kelvin(wds[[uvar]], pts)
            v = _extract_points_kelvin(wds[[vvar]], pts)
            wds.close()
            d, s = _wind_dir_speed(u["cp"], v["cp"])
            row["cp_wdir"], row["cp_wspd_kt"] = d, s
            rows.append(row)
        except Exception as exc:  # noqa: BLE001
            log.warning("hrrr_hourly f%03d failed: %s", fxx, str(exc)[:120])
    if len(rows) < 5:
        return None
    return pd.DataFrame(rows).set_index("hour_local").sort_index()


def afternoon_shape_features(trace: pd.DataFrame) -> dict:
    """Distill an afternoon trace into sea-breeze shape features (pure function)."""
    out: dict = {}
    t = trace["cp_temp_f"].dropna()
    if len(t) >= 5:
        out["hrrr_peak_hour_local"] = int(t.idxmax())
        pm = t[(t.index >= 12) & (t.index <= 17)]
        if len(pm) >= 3:
            out["hrrr_afternoon_range_f"] = round(float(pm.max() - pm.iloc[0]), 2)
        out["hrrr_sees_cap"] = bool(out["hrrr_peak_hour_local"] <= 13
                                    or out.get("hrrr_afternoon_range_f", 9) <= 1.0)
    if "cp_wdir" in trace:
        wd = trace["cp_wdir"].dropna()
        pm = wd[(wd.index >= 11) & (wd.index <= 17)]
        out["hrrr_onshore_hours"] = int(((pm >= ONSHORE_LO) & (pm <= ONSHORE_HI)).sum())
    if "jfk_temp_f" in trace:
        gap = (trace["cp_temp_f"] - trace["jfk_temp_f"]).dropna()
        pm = gap[(gap.index >= 13) & (gap.index <= 17)]
        if len(pm):
            out["hrrr_cp_jfk_gap_pm_f"] = round(float(pm.mean()), 2)
    return out


def hrrr_shape_advisory(cfg, target_date: date,
                        issued_before_utc: Optional[datetime] = None) -> dict:
    """Fetch + distill; {} on any unavailability (advisory-only, never blocks)."""
    try:
        trace = fetch_afternoon_trace(cfg, target_date, issued_before_utc)
    except Exception as exc:  # noqa: BLE001
        log.debug("hrrr shape advisory unavailable: %s", exc)
        return {}
    if trace is None:
        return {}
    return afternoon_shape_features(trace)
