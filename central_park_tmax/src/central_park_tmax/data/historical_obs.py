"""Historical hourly/sub-hourly observation archive via the Iowa Environmental Mesonet.

The NWS observations API only serves ~1 week of history, which is insufficient for building
intraday training datasets. IEM's bulk ASOS download provides the full archive for KNYC
(station id ``NYC`` on the ``NY_ASOS`` network) including routine hourly obs, SPECIs, and the
raw METAR text (which carries the precise tenths-degree T-group and the 6-hour maximum
remark group). The temperature IEM returns already reflects the precise reading, so the
per-timestamp values capture between-hour peaks far better than :51-only hourly snapshots.

This is a research/observation archive (final observed values), used to reconstruct the
observed-max-so-far at each historical intraday forecast time. It is NEVER the contract
label and is always truncated at the forecast issue time (no lookahead).
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from ..constants import f_to_c
from ..logging_config import get_logger
from .storage import HttpClient

log = get_logger(__name__)

IEM_ASOS_URL = (
    "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
    "?station={station}&data=tmpf&data=metar&tz=UTC&format=comma&latlon=no"
    "&missing=empty&trace=empty"
    "&year1={y1}&month1={m1}&day1={d1}&year2={y2}&month2={m2}&day2={d2}"
)


@dataclass
class HistoricalObsLoader:
    http: HttpClient
    iem_station: str = "NYC"   # KNYC on the NY_ASOS network

    def download_csv(self, start: date, end: date, use_cache: bool = True) -> str:
        url = IEM_ASOS_URL.format(
            station=self.iem_station,
            y1=start.year, m1=start.month, d1=start.day,
            y2=end.year, m2=end.month, d2=end.day,
        )
        log.info("Downloading IEM ASOS archive %s..%s for %s", start, end, self.iem_station)
        return self.http.get_text(url, use_cache=use_cache)

    def load(self, start: date, end: date, use_cache: bool = True) -> pd.DataFrame:
        return self.parse_csv(self.download_csv(start, end, use_cache=use_cache))

    @staticmethod
    def parse_csv(csv_text: str) -> pd.DataFrame:
        # Strip IEM's leading '#DEBUG' comment lines.
        lines = [ln for ln in csv_text.splitlines() if not ln.startswith("#")]
        if not lines:
            return pd.DataFrame(columns=["timestamp_utc", "temp_f", "temp_c", "raw_metar"])
        raw = pd.read_csv(io.StringIO("\n".join(lines)), dtype=str, low_memory=False)
        if "valid" not in raw.columns or "tmpf" not in raw.columns:
            raise ValueError(f"Unexpected IEM columns: {list(raw.columns)[:8]}")
        out = pd.DataFrame()
        out["timestamp_utc"] = pd.to_datetime(raw["valid"], utc=True, errors="coerce")
        out["temp_f"] = pd.to_numeric(raw["tmpf"], errors="coerce")
        out["temp_c"] = out["temp_f"].apply(lambda v: f_to_c(v) if pd.notna(v) else np.nan)
        out["raw_metar"] = raw["metar"] if "metar" in raw.columns else ""
        out = out.dropna(subset=["timestamp_utc"]).sort_values("timestamp_utc").reset_index(drop=True)
        return out


def load_historical_obs(http: HttpClient, start: date, end: date,
                        iem_station: str = "NYC") -> pd.DataFrame:
    return HistoricalObsLoader(http=http, iem_station=iem_station).load(start, end)
