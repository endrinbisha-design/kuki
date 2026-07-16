"""Thin client for api.weather.gov: CLI text products, gridpoint forecasts, observations.

Credential-free JSON API. Used for:
  * live retrieval of the Central Park Daily Climate Report (CLI) text product,
  * the fully-implemented NWS gridpoint forecast source (see forecast sources),
  * current station observations (temperature so far today, METAR-derived fields).

Network access is required; when unavailable the calling pipeline records the source as
missing and falls back explicitly (never silently substitutes fabricated data).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from ..constants import NWS_API_BASE, NWS_CLI_ISSUING_OFFICE
from ..logging_config import get_logger
from ..time_utils import now_utc
from . import DataSourceError
from .storage import HttpClient

log = get_logger(__name__)


class NwsApiClient:
    def __init__(self, http: HttpClient, base: str = NWS_API_BASE):
        self.http = http
        self.base = base.rstrip("/")

    # ---- CLI text products -----------------------------------------------------------
    def list_cli_products(self, office: str = NWS_CLI_ISSUING_OFFICE) -> list[dict[str, Any]]:
        """List recent CLI (Daily Climate Report) products from an issuing office."""
        url = f"{self.base}/products/types/CLI/locations/{office}"
        data = self.http.get_json(url, use_cache=False)
        return data.get("@graph", data.get("products", []))

    def get_product_text(self, product_id: str) -> tuple[str, Optional[str]]:
        """Fetch a product by its @id or product id; returns (text, issuance_iso)."""
        url = product_id if product_id.startswith("http") else f"{self.base}/products/{product_id}"
        data = self.http.get_json(url, use_cache=False)
        text = data.get("productText")
        if not text:
            raise DataSourceError(f"No productText in NWS product response for {product_id}")
        return text, data.get("issuanceTime")

    def latest_central_park_cli(self, office: str = NWS_CLI_ISSUING_OFFICE) -> tuple[str, Optional[str]]:
        """Fetch the most recent Central Park CLI product text.

        The OKX office issues CLI for several sites; we select the Central Park (NYC)
        product by AWIPS/product id hint, else the newest.
        """
        products = self.list_cli_products(office=office)
        if not products:
            raise DataSourceError(f"No CLI products returned for office {office}")
        # Prefer product ids that reference NYC/Central Park.
        def _score(p: dict) -> tuple[int, str]:
            pid = (p.get("productCode", "") + p.get("id", "") + p.get("productName", "")).upper()
            wmo = p.get("wmoCollectiveId", "")
            issued = p.get("issuanceTime", "")
            return (0 if "NYC" in pid else 1, issued)
        products_sorted = sorted(products, key=lambda p: p.get("issuanceTime", ""), reverse=True)
        chosen = min(products_sorted, key=_score)
        return self.get_product_text(chosen.get("@id") or chosen.get("id"))

    # ---- Gridpoint forecast (fully-implemented forecast source) ----------------------
    def points(self, lat: float, lon: float) -> dict[str, Any]:
        url = f"{self.base}/points/{lat:.4f},{lon:.4f}"
        return self.http.get_json(url, use_cache=True)

    def gridpoint_forecast_hourly(self, lat: float, lon: float) -> dict[str, Any]:
        """Return the hourly gridpoint forecast (temperature, wind, etc.) as GeoJSON."""
        meta = self.points(lat, lon)
        props = meta.get("properties", {})
        url = props.get("forecastHourly")
        if not url:
            raise DataSourceError("No forecastHourly URL in /points response.")
        return self.http.get_json(url, use_cache=True)

    def gridpoint_raw(self, lat: float, lon: float) -> dict[str, Any]:
        """Raw gridpoint data (all variables incl. skyCover, dewpoint, quantitativePrecip)."""
        meta = self.points(lat, lon)
        url = meta.get("properties", {}).get("forecastGridData")
        if not url:
            raise DataSourceError("No forecastGridData URL in /points response.")
        return self.http.get_json(url, use_cache=True)

    # ---- Current observations --------------------------------------------------------
    def latest_observation(self, station_icao: str) -> dict[str, Any]:
        url = f"{self.base}/stations/{station_icao}/observations/latest"
        return self.http.get_json(url, use_cache=False)

    def observations_since(self, station_icao: str, start_iso: str) -> dict[str, Any]:
        url = f"{self.base}/stations/{station_icao}/observations?start={start_iso}"
        return self.http.get_json(url, use_cache=False)


def retrieved_at() -> datetime:
    return now_utc()
