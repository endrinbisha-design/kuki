"""HRRR forecast source (high-resolution, hourly cycles). AWS: noaa-hrrr-bdp-pds.

Requires GRIB optional deps (see _herbie.py). Fallback baseline when NBM is unavailable.
"""
from __future__ import annotations

from ._herbie import HerbieForecastSource


class HrrrForecastSource(HerbieForecastSource):
    name = "hrrr"
    model = "hrrr"
    product = "sfc"
    cycle_hours = 6         # use synoptic cycles, which extend to f048
    latency_hours = 2.0
    tmp_search = ":TMP:2 m above ground:"
    is_ensemble = False
    max_fxx = 48
