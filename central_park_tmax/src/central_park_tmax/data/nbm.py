"""National Blend of Models (NBM) forecast source — preferred residual baseline.

NBM is already statistically post-processed, making it a strong benchmark. It provides a
direct daily maximum-temperature product (TMAX) plus hourly 2 m temperature. Archive on
AWS Open Data: noaa-nbm-grib2-pds. Requires the GRIB optional deps (see _herbie.py); when
missing, ``ForecastSourceUnavailable`` is raised and the pipeline falls back explicitly.
"""
from __future__ import annotations

from ._herbie import HerbieForecastSource


class NbmForecastSource(HerbieForecastSource):
    name = "nbm"
    model = "nbm"
    product = "co"          # CONUS blend product
    cycle_hours = 1         # NBM updates hourly
    latency_hours = 1.5
    tmp_search = ":TMP:2 m above ground:"
    is_ensemble = False
    max_fxx = 36            # hourly output extends to f036 for every cycle
