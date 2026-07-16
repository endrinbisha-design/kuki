"""Factory that builds forecast-source objects from configuration.

Maps source names in configs to concrete ForecastSource implementations, injecting the shared
HTTP / NWS clients as needed. GRIB sources are constructed lazily; they raise
ForecastSourceUnavailable at fetch time if their optional deps are missing (never here).
"""
from __future__ import annotations

from typing import Optional

from ..config import AppConfig
from ..logging_config import get_logger
from .forecast_base import ForecastSource
from .gefs import GefsForecastSource
from .gfs import GfsForecastSource
from .hrrr import HrrrForecastSource
from .nbm import NbmForecastSource
from .nws_api import NwsApiClient
from .nws_gridpoint import NwsGridpointForecastSource
from .storage import http_client_from_config
from .synthetic import SyntheticForecastSource

log = get_logger(__name__)


def build_source(name: str, cfg: AppConfig, nws: Optional[NwsApiClient] = None) -> ForecastSource:
    if name == "synthetic":
        return SyntheticForecastSource(label="synthetic")
    if name == "nws_gridpoint":
        client = nws or NwsApiClient(http_client_from_config(cfg))
        return NwsGridpointForecastSource(client)
    if name == "nbm":
        return NbmForecastSource()
    if name == "hrrr":
        return HrrrForecastSource()
    if name == "gfs":
        return GfsForecastSource()
    if name == "gefs":
        return GefsForecastSource()
    raise ValueError(f"Unknown forecast source: {name!r}")


def build_active_sources(cfg: AppConfig, nws: Optional[NwsApiClient] = None,
                         synthetic: bool = False) -> dict[str, ForecastSource]:
    if synthetic:
        return {"synthetic": build_source("synthetic", cfg, nws)}
    out: dict[str, ForecastSource] = {}
    for name in cfg.active_forecast_sources:
        try:
            out[name] = build_source(name, cfg, nws)
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not construct source %s: %s", name, exc)
    return out


def choose_baseline_source(cfg: AppConfig, available: dict[str, ForecastSource],
                           synthetic: bool = False) -> str:
    if synthetic:
        return "synthetic"
    for pref in cfg.baseline_source_preference:
        if pref in available:
            return pref
    if available:
        return next(iter(available))
    raise ValueError("No forecast sources available to serve as baseline.")
