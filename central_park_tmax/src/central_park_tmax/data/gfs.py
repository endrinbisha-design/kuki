"""GFS forecast source (global, 6-hourly cycles, 0.25 deg). AWS: noaa-gfs-bdp-pds.

Requires GRIB optional deps (see _herbie.py). Deterministic global fallback baseline.
"""
from __future__ import annotations

from ._herbie import HerbieForecastSource


class GfsForecastSource(HerbieForecastSource):
    name = "gfs"
    model = "gfs"
    product = "pgrb2.0p25"
    cycle_hours = 6
    latency_hours = 4.0
    tmp_search = ":TMP:2 m above ground:"
    is_ensemble = False
