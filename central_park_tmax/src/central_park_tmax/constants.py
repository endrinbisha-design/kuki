"""Project constants: station identity, enumerations, units, provenance categories.

Everything here is static and time-invariant. Time-varying values live in config or
are computed at runtime.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass

# --------------------------------------------------------------------------------------
# Station identity (also mirrored in configs/default.yaml; this is the code-level source
# of truth for tests and for modules that must not depend on a loaded config).
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class StationInfo:
    name: str
    shorthand: str
    noaa_station_id: str
    wban: str
    icao: str
    latitude: float
    longitude: float
    elevation_m: float
    timezone: str


STATION = StationInfo(
    name="NY CITY CENTRAL PARK, NY US",
    shorthand="KNYC",
    noaa_station_id="USW00094728",
    wban="94728",
    icao="KNYC",
    latitude=40.77898,
    longitude=-73.96925,
    elevation_m=42.7,
    timezone="America/New_York",
)

TIMEZONE = STATION.timezone


# --------------------------------------------------------------------------------------
# Provenance categories for the contract target label. NEVER mix categories silently.
# --------------------------------------------------------------------------------------
class TargetProvenance(str, enum.Enum):
    NWS_AT_EXPIRATION = "nws_climate_report_at_expiration"
    NWS_PRE_EXPIRATION_REVISION = "nws_climate_report_pre_expiration_revision"
    NWS_LATER_REVISION = "nws_climate_report_later_revision"
    GHCN_DAILY_FINAL = "ghcn_daily_final"
    RECONSTRUCTED = "reconstructed_from_observations"
    MISSING = "missing_or_unresolved"


# --------------------------------------------------------------------------------------
# Settlement state machine states.
# --------------------------------------------------------------------------------------
class SettlementState(str, enum.Enum):
    FORECAST_OPEN = "forecast_open"
    TRADING_CLOSED = "trading_closed"
    AWAITING_REPORT = "awaiting_report"
    PRELIMINARY_REPORT_AVAILABLE = "preliminary_report_available"
    CONSISTENCY_REVIEW = "consistency_review"
    EXPIRATION_VALUE_LOCKED = "expiration_value_locked"
    LATER_REVISION_IGNORED = "later_revision_ignored_for_settlement"
    OUTCOME_UNDER_REVIEW = "outcome_under_review"


class ReportStatus(str, enum.Enum):
    PRELIMINARY = "preliminary"
    CORRECTED = "corrected"
    FINAL = "final"
    UNKNOWN = "unknown"


# --------------------------------------------------------------------------------------
# Operational fallback hierarchy (lower number = richer model).
# --------------------------------------------------------------------------------------
class FallbackLevel(int, enum.Enum):
    FULL_MODEL = 1              # all active forecast sources + residual ML
    RESIDUAL_PRIMARY = 2        # primary baseline + residual ML
    PRIMARY_PLUS_BIAS = 3       # primary baseline + rolling bias correction
    RAW_PRIMARY = 4             # raw primary numerical forecast
    NWS_POINT = 5               # NWS point forecast only
    CLIMATE_NORMAL = 6          # climate normal (last resort)


# --------------------------------------------------------------------------------------
# Units & conversions. Kept trivial and dependency-free for use everywhere.
# --------------------------------------------------------------------------------------
ABSOLUTE_ZERO_C = -273.15
# QC sanity bounds for a daily max (a parse/QC guard, not a per-station climatology).
# Wide enough to admit desert-Southwest city highs (Phoenix routinely 116-118F) while
# still catching absurd parse errors; Central Park never approaches either bound.
MIN_PLAUSIBLE_TMAX_F = -40.0
MAX_PLAUSIBLE_TMAX_F = 130.0


def c_to_f(celsius: float) -> float:
    return celsius * 9.0 / 5.0 + 32.0


def f_to_c(fahrenheit: float) -> float:
    return (fahrenheit - 32.0) * 5.0 / 9.0


# GHCN-Daily bulk CSV endpoints (final QC daily values; NOT the contract label).
# Primary: NCEI 'access' wide CSV. Fallback: NOAA Open Data on AWS (long format), which is
# reachable from more network environments (no credentials required for either).
GHCN_DAILY_CSV_URL = (
    "https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/"
    "{station_id}.csv"
)
GHCN_DAILY_S3_CSV_URL = (
    "https://noaa-ghcn-pds.s3.amazonaws.com/csv/by_station/{station_id}.csv"
)
GHCN_DAILY_DLY_URL = (
    "https://www.ncei.noaa.gov/pub/data/ghcn/daily/all/{station_id}.dly"
)

# NWS text-product API (Daily Climate Report). CLI product for the NYC area.
NWS_API_BASE = "https://api.weather.gov"
NWS_CLI_PRODUCT_CODE = "CLI"          # Daily Climate Report product type
NWS_CLI_ISSUING_OFFICE = "OKX"        # NWS New York, NY (Upton) — the issuing WFO
# The text-products API indexes CLI by LOCATION code, which for the Central Park report is
# "NYC" (NOT the office "OKX"; /products/types/CLI/locations/OKX returns empty). Verified
# live: the NYC location returns the CLINYC products incl. the intraday preliminary.
NWS_CLI_LOCATION = "NYC"
NWS_CLI_PRODUCT_ID_HINT = "CLINYC"    # AWIPS/product id substring for Central Park CLI

# Reporting-convention version tag default.
DEFAULT_REPORTING_CONVENTION_VERSION = "nws_cli_v1"
DEFAULT_CONTRACT_RULE_VERSION = "nhigh_v1"
