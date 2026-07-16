"""Shared Herbie/cfgrib-backed forecast source logic for NBM/HRRR/GFS/GEFS.

These models are distributed as GRIB2 on NOAA Open Data (AWS). Reading them requires
``herbie-data`` + ``cfgrib`` + the system ecCodes library. When those are unavailable we
raise ``ForecastSourceUnavailable`` with actionable guidance rather than silently
substituting anything. This keeps the rest of the pipeline operational via the fallback
hierarchy (see pipelines/predict.py).

Point extraction supports nearest / bilinear via xarray selection. Neighborhood stats are
computed by the base ForecastSource from per-location daily maxima.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

from ..logging_config import get_logger
from ..time_utils import local_day_bounds_utc, now_utc
from . import ForecastSourceUnavailable
from .forecast_base import ForecastRun, ForecastSource, RunHandle

log = get_logger(__name__)


def _require_herbie():
    try:
        from herbie import Herbie  # noqa: F401
        import xarray  # noqa: F401
        import cfgrib  # noqa: F401
        return True
    except Exception as exc:  # noqa: BLE001
        raise ForecastSourceUnavailable(
            "GRIB forecast sources require optional deps not installed in this environment. "
            "Install with:  pip install 'central_park_tmax[grib]'  (needs the system ecCodes "
            "library, e.g. `apt-get install libeccodes0` or `conda install -c conda-forge "
            "eccodes cfgrib herbie-data`). Until then, the NWS gridpoint source and the "
            "explicit fallback hierarchy are used instead."
        ) from exc


class HerbieForecastSource(ForecastSource):
    """Base for AWS-Open-Data GRIB models. Subclasses set model/product/cycle cadence."""

    model: str = "gfs"
    product: str = "pgrb2.0p25"
    #: hours between model cycles
    cycle_hours: int = 6
    #: typical time from init to availability
    latency_hours: float = 4.0
    #: GRIB search string for 2 m temperature
    tmp_search: str = ":TMP:2 m above ground:"
    is_ensemble: bool = False

    def list_available_runs(self, target_date: date, issued_before_utc: datetime) -> list[RunHandle]:
        start, _ = local_day_bounds_utc(target_date)
        # Consider cycles from 2 days before the target day start up to the issue time.
        earliest = start - timedelta(days=2)
        cycles: list[RunHandle] = []
        c = earliest.replace(minute=0, second=0, microsecond=0)
        c = c.replace(hour=(c.hour // self.cycle_hours) * self.cycle_hours)
        while c <= issued_before_utc:
            avail = c + timedelta(hours=self.latency_hours)
            cycles.append(RunHandle(
                source=self.name, init_utc=c, cycle=c.strftime("%Y-%m-%dT%HZ"),
                availability_estimate_utc=avail, model_version=self.model,
            ))
            c = c + timedelta(hours=self.cycle_hours)
        return cycles

    def fetch_run(self, run: RunHandle, locations, target_date: date) -> ForecastRun:
        _require_herbie()
        from herbie import Herbie
        import numpy as np

        per_loc: dict[str, pd.DataFrame] = {}
        grid_coords: dict[str, tuple[float, float]] = {}
        start, end = local_day_bounds_utc(target_date)
        # Forecast hours covering the target local day.
        fxx_start = max(0, int((start - run.init_utc).total_seconds() // 3600) - 1)
        fxx_end = int((end - run.init_utc).total_seconds() // 3600) + 1

        points = locations.all_points()
        # Prepare an accumulation dict keyed by location -> list of (valid_time, temp_f)
        acc: dict[str, list[tuple[datetime, float]]] = {p.key: [] for p in points}
        for fxx in range(fxx_start, fxx_end + 1):
            try:
                H = Herbie(run.init_utc, model=self.model, product=self.product, fxx=fxx)
                ds = H.xarray(self.tmp_search)
            except Exception as exc:  # noqa: BLE001
                log.warning("%s fxx=%d fetch failed: %s", self.name, fxx, exc)
                continue
            valid = run.init_utc + timedelta(hours=fxx)
            tvar = _first_data_var(ds)
            for p in points:
                try:
                    val = ds[tvar].herbie.nearest_points(
                        points=[(p.longitude, p.latitude)]
                    ) if hasattr(ds[tvar], "herbie") else _xr_nearest(ds[tvar], p.latitude, p.longitude)
                    tval_k = float(np.ravel(np.asarray(val))[0])
                    temp_f = (tval_k - 273.15) * 9 / 5 + 32 if tval_k > 200 else tval_k * 9 / 5 + 32
                    acc[p.key].append((valid, temp_f))
                    grid_coords.setdefault(p.key, (p.latitude, p.longitude))
                except Exception as exc:  # noqa: BLE001
                    log.debug("point extract failed %s %s: %s", self.name, p.key, exc)

        for key, series in acc.items():
            if series:
                df = pd.DataFrame(series, columns=["valid_time_utc", "temp_f"])
                per_loc[key] = df.sort_values("valid_time_utc").reset_index(drop=True)

        if not per_loc:
            raise ForecastSourceUnavailable(
                f"{self.name}: no data extracted for {target_date} (archive gap or fetch error)."
            )
        return ForecastRun(
            source=self.name, init_utc=run.init_utc, cycle=run.cycle,
            per_location_hourly=per_loc,
            availability_estimate_utc=run.availability_estimate_utc,
            model_version=self.model, variable_units={"temp_f": "degF"},
            grid_coords=grid_coords, provenance=f"{self.name}_grib",
        )


def _first_data_var(ds):
    for v in ds.data_vars:
        return v
    raise ForecastSourceUnavailable("GRIB dataset had no data variables.")


def _xr_nearest(da, lat: float, lon: float):
    # xarray nearest selection fallback (grids vary; try common coordinate names).
    for latname, lonname in (("latitude", "longitude"), ("lat", "lon")):
        if latname in da.coords and lonname in da.coords:
            lon_q = lon % 360 if float(da[lonname].max()) > 180 else lon
            return da.sel({latname: lat, lonname: lon_q}, method="nearest").values
    raise ForecastSourceUnavailable("Could not identify lat/lon coords in GRIB dataset.")
