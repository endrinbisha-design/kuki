"""GEFS ensemble forecast source (31 members, 6-hourly). AWS: noaa-gefs-pds.

Provides ensemble spread used for EMOS-style probabilistic post-processing and inter-member
features (mean, median, std, percentiles). Requires GRIB optional deps (see _herbie.py).

This adapter fetches the ensemble mean product by default; full per-member extraction is a
documented extension point (``member`` parameter) and raises ForecastSourceUnavailable when
GRIB deps are missing.
"""
from __future__ import annotations

from ._herbie import HerbieForecastSource


class GefsForecastSource(HerbieForecastSource):
    name = "gefs"
    model = "gefs"
    product = "atmos.5"      # 0.5 deg atmos product
    cycle_hours = 6
    latency_hours = 5.0
    tmp_search = ":TMP:2 m above ground:"
    is_ensemble = True
    max_fxx = 120
