"""GHCN-Daily loader for station USW00094728 (Central Park).

Provides final, quality-controlled daily values: TMAX, TMIN, PRCP, SNOW, SNWD with
measurement (M), quality (Q), and source (S) flags. These are the *final* research
labels and long-term climatology source. They are explicitly NOT the contract label:
the contract underlying is the contemporaneous NWS Daily Climate Report maximum.

Temperatures in the NCEI CSV are in tenths of degrees C. We keep both C and F.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from ..constants import GHCN_DAILY_CSV_URL, c_to_f
from ..logging_config import get_logger
from . import ObservationError
from .storage import HttpClient

log = get_logger(__name__)

# Elements we retain from the wide GHCN CSV.
CORE_ELEMENTS = ["TMAX", "TMIN", "PRCP", "SNOW", "SNWD"]
# Elements stored in tenths of a degree C (need /10).
TENTHS_C_ELEMENTS = {"TMAX", "TMIN"}
# Elements in tenths of mm (need /10 to get mm).
TENTHS_MM_ELEMENTS = {"PRCP", "SNOW", "SNWD"}


@dataclass
class GhcnDailyLoader:
    http: HttpClient
    station_id: str = "USW00094728"

    def download_csv_text(self, use_cache: bool = True) -> str:
        url = GHCN_DAILY_CSV_URL.format(station_id=self.station_id)
        log.info("Downloading GHCN-Daily CSV: %s", url)
        return self.http.get_text(url, use_cache=use_cache)

    def load(self, csv_text: Optional[str] = None, use_cache: bool = True) -> pd.DataFrame:
        """Return a tidy daily frame indexed by local calendar date.

        Columns include tmax_c/tmax_f, tmin_c/tmin_f, prcp_mm, snow_mm, snwd_mm and the
        associated M/Q/S flag columns where present.
        """
        if csv_text is None:
            csv_text = self.download_csv_text(use_cache=use_cache)
        return self.parse_csv(csv_text)

    def parse_csv(self, csv_text: str) -> pd.DataFrame:
        raw = pd.read_csv(io.StringIO(csv_text), dtype=str, low_memory=False)
        if "DATE" not in raw.columns:
            raise ObservationError(
                "GHCN-Daily CSV missing DATE column; schema may have changed. "
                f"Columns seen: {list(raw.columns)[:12]}"
            )
        out = pd.DataFrame()
        out["date"] = pd.to_datetime(raw["DATE"], errors="coerce").dt.date

        for elem in CORE_ELEMENTS:
            if elem not in raw.columns:
                log.warning("GHCN element %s absent for station %s", elem, self.station_id)
                continue
            vals = pd.to_numeric(raw[elem], errors="coerce")
            if elem in TENTHS_C_ELEMENTS:
                celsius = vals / 10.0
                out[f"{elem.lower()}_c"] = celsius
                out[f"{elem.lower()}_f"] = celsius.apply(lambda v: c_to_f(v) if pd.notna(v) else np.nan)
            elif elem in TENTHS_MM_ELEMENTS:
                out[f"{elem.lower()}_mm"] = vals / 10.0
            # Preserve flags if present (e.g. TMAX_ATTRIBUTES => "M,Q,S,time").
            attr_col = f"{elem}_ATTRIBUTES"
            if attr_col in raw.columns:
                flags = raw[attr_col].fillna("").str.split(",", expand=True)
                for i, fname in enumerate(["mflag", "qflag", "sflag"]):
                    if flags.shape[1] > i:
                        out[f"{elem.lower()}_{fname}"] = flags[i].replace("", np.nan)

        out = out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        out["station_id"] = self.station_id
        out["provenance"] = "ghcn_daily_final"
        return out


def load_ghcn_daily(http: HttpClient, station_id: str = "USW00094728",
                    csv_text: Optional[str] = None) -> pd.DataFrame:
    return GhcnDailyLoader(http=http, station_id=station_id).load(csv_text=csv_text)


def tmax_series(df: pd.DataFrame) -> pd.Series:
    """Convenience: date-indexed final TMAX (F) series for climatology/QC (not contract)."""
    s = df.set_index("date")["tmax_f"]
    s.name = "ghcn_tmax_f"
    return s


def climate_normals_1991_2020(df: pd.DataFrame) -> pd.DataFrame:
    """Day-of-year 1991-2020 normal maximum (F) computed from GHCN final TMAX.

    A smoothed day-of-year climatology used as the climate-normal baseline / anomaly ref.
    Feb 29 is folded into day-of-year 59/60 handling via a 15-day centered smoother.
    """
    d = df.dropna(subset=["tmax_f"]).copy()
    d["date"] = pd.to_datetime(d["date"])
    mask = (d["date"].dt.year >= 1991) & (d["date"].dt.year <= 2020)
    base = d.loc[mask]
    if base.empty:
        base = d  # fall back to whatever range exists
    base = base.assign(doy=base["date"].dt.dayofyear)
    raw = base.groupby("doy")["tmax_f"].mean()
    full = raw.reindex(range(1, 367))
    # Circular 15-day smoothing.
    vals = full.to_numpy(dtype=float)
    n = len(vals)
    sm = np.copy(vals)
    for i in range(n):
        window = [vals[(i + k) % n] for k in range(-7, 8)]
        window = [w for w in window if not np.isnan(w)]
        sm[i] = np.mean(window) if window else np.nan
    return pd.DataFrame({"doy": range(1, 367), "normal_tmax_f": sm})
