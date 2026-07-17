"""Shared Herbie/cfgrib-backed forecast source logic for NBM/HRRR/GFS/GEFS.

These models are distributed as GRIB2 on NOAA Open Data (AWS). Reading them requires
``herbie-data`` + ``cfgrib`` + ecCodes (pip wheels bundle the library). When unavailable we
raise ``ForecastSourceUnavailable`` with actionable guidance rather than silently
substituting anything.

Implementation notes:
  * ``priority=['aws']`` — only NOAA Open Data on AWS is used (NOMADS is often blocked and
    slower); byte-range subsetting via .idx files downloads only the 2 m temperature message.
  * Point extraction is self-contained (no cartopy): nearest grid point on 2D curvilinear
    grids (NBM/HRRR) or 1D rectilinear grids (GFS/GEFS), with longitude 0..360 handling.
  * Downloaded GRIB subsets are deleted after extraction by default (``keep_grib=False``)
    so multi-date archive builds do not exhaust disk.
  * ``fxx_step`` controls the forecast-hour stride (3 h default for archive builds; the
    daily maximum is well captured at 3 h resolution and it cuts downloads by 3x).
"""
from __future__ import annotations

import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from ..logging_config import get_logger
from ..time_utils import local_day_bounds_utc
from . import ForecastSourceUnavailable
from .forecast_base import ForecastRun, ForecastSource, RunHandle

log = get_logger(__name__)


def _require_herbie():
    try:
        from herbie import Herbie  # noqa: F401
        import xarray  # noqa: F401
        import cfgrib  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        raise ForecastSourceUnavailable(
            "GRIB forecast sources require optional deps not installed in this environment. "
            "Install with:  pip install 'central_park_tmax[grib]'  (pip eccodes wheels bundle "
            "the ecCodes library; conda-forge eccodes/cfgrib/herbie-data also works). Until "
            "then, the NWS gridpoint source and the explicit fallback hierarchy are used."
        ) from exc


def _extract_points_kelvin(ds, points: list[tuple[str, float, float]]) -> dict[str, float]:
    """Nearest-grid-point extraction for each (key, lat, lon). Returns {key: kelvin}.

    Handles 2D curvilinear (NBM/HRRR) and 1D rectilinear (GFS/GEFS) grids without cartopy.
    """
    var = next(iter(ds.data_vars))
    da = ds[var]
    out: dict[str, float] = {}

    lat = ds.coords.get("latitude", ds.coords.get("lat"))
    lon = ds.coords.get("longitude", ds.coords.get("lon"))
    if lat is None or lon is None:
        raise ForecastSourceUnavailable("GRIB dataset lacks latitude/longitude coordinates.")

    if lat.ndim == 2:
        lat2d = lat.values
        lon2d = lon.values
        lon2d = np.where(lon2d > 180, lon2d - 360, lon2d)
        vals = da.values
        for key, plat, plon in points:
            # Equirectangular metric is fine at ~3 km grid spacing.
            d2 = (lat2d - plat) ** 2 + ((lon2d - plon) * np.cos(np.deg2rad(plat))) ** 2
            j, i = np.unravel_index(np.argmin(d2), d2.shape)
            out[key] = float(vals[..., j, i]) if vals.ndim > 2 else float(vals[j, i])
    else:
        lon_vals = lon.values
        wraps = float(np.nanmax(lon_vals)) > 180.0
        for key, plat, plon in points:
            q_lon = plon % 360 if wraps else plon
            sel = da.sel({lat.name: plat, lon.name: q_lon}, method="nearest")
            out[key] = float(np.ravel(sel.values)[0])
    return out


class HerbieForecastSource(ForecastSource):
    """Base for AWS-Open-Data GRIB models. Subclasses set model/product/cycle cadence."""

    model: str = "gfs"
    product: str = "pgrb2.0p25"
    cycle_hours: int = 6          # hours between model cycles
    latency_hours: float = 4.0    # typical init -> availability delay
    tmp_search: str = ":TMP:2 m above ground:"
    is_ensemble: bool = False
    fxx_step: int = 3             # forecast-hour stride when sampling the target day
    max_fxx: int = 60
    keep_grib: bool = False       # delete GRIB subsets after extraction (disk safety)
    save_dir: Optional[str] = None

    def list_available_runs(self, target_date: date, issued_before_utc: datetime) -> list[RunHandle]:
        start, _ = local_day_bounds_utc(target_date)
        earliest = start - timedelta(days=2)
        cycles: list[RunHandle] = []
        c = earliest.replace(minute=0, second=0, microsecond=0, tzinfo=earliest.tzinfo)
        c = c.replace(hour=(c.hour // self.cycle_hours) * self.cycle_hours)
        while c <= issued_before_utc:
            avail = c + timedelta(hours=self.latency_hours)
            if avail <= issued_before_utc:
                cycles.append(RunHandle(
                    source=self.name, init_utc=c, cycle=c.strftime("%Y-%m-%dT%HZ"),
                    availability_estimate_utc=avail, model_version=self.model,
                ))
            c = c + timedelta(hours=self.cycle_hours)
        return cycles

    def fetch_run(self, run: RunHandle, locations, target_date: date) -> ForecastRun:
        _require_herbie()
        from herbie import Herbie

        start, end = local_day_bounds_utc(target_date)
        init = run.init_utc
        fxx_start = max(1, int((start - init).total_seconds() // 3600))
        fxx_end = min(self.max_fxx, int((end - init).total_seconds() // 3600))
        if fxx_end <= fxx_start:
            raise ForecastSourceUnavailable(
                f"{self.name} run {run.cycle} does not reach target day {target_date} "
                f"within max_fxx={self.max_fxx}."
            )
        fxx_list = list(range(fxx_start, fxx_end + 1, self.fxx_step))
        if fxx_list[-1] != fxx_end:
            fxx_list.append(fxx_end)

        points = [(p.key, p.latitude, p.longitude) for p in locations.all_points()]
        acc: dict[str, list[tuple[datetime, float]]] = {k: [] for k, _, _ in points}
        grid_coords: dict[str, tuple[float, float]] = {}
        n_ok = 0
        init_naive = init.replace(tzinfo=None)

        for fxx in fxx_list:
            grib_path = None
            try:
                H = Herbie(init_naive, model=self.model, product=self.product,
                           fxx=fxx, priority=["aws"], verbose=False,
                           save_dir=self.save_dir) if self.save_dir else \
                    Herbie(init_naive, model=self.model, product=self.product,
                           fxx=fxx, priority=["aws"], verbose=False)
                if H.grib is None:
                    raise FileNotFoundError(f"no GRIB on aws for {self.model} {run.cycle} f{fxx:03d}")
                ds = H.xarray(self.tmp_search, remove_grib=not self.keep_grib)
                kelvin = _extract_points_kelvin(ds, points)
                valid = init + timedelta(hours=fxx)
                for key, k in kelvin.items():
                    temp_f = (k - 273.15) * 9 / 5 + 32
                    acc[key].append((valid, temp_f))
                for p in locations.all_points():
                    grid_coords.setdefault(p.key, (p.latitude, p.longitude))
                n_ok += 1
                try:
                    ds.close()
                except Exception:  # noqa: BLE001
                    pass
            except ForecastSourceUnavailable:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("%s %s f%03d fetch failed: %s", self.name, run.cycle, fxx,
                            str(exc)[:200])
            finally:
                if grib_path and not self.keep_grib:
                    Path(grib_path).unlink(missing_ok=True)

        if n_ok < max(2, len(fxx_list) // 3):
            raise ForecastSourceUnavailable(
                f"{self.name}: only {n_ok}/{len(fxx_list)} forecast hours retrieved for "
                f"{run.cycle} -> {target_date}; treating run as unusable."
            )

        per_loc = {
            key: pd.DataFrame(series, columns=["valid_time_utc", "temp_f"])
                   .sort_values("valid_time_utc").reset_index(drop=True)
            for key, series in acc.items() if series
        }
        return ForecastRun(
            source=self.name, init_utc=init, cycle=run.cycle,
            per_location_hourly=per_loc,
            availability_estimate_utc=run.availability_estimate_utc,
            model_version=self.model, variable_units={"temp_f": "degF"},
            grid_coords=grid_coords, provenance=f"{self.name}_grib_aws",
        )
