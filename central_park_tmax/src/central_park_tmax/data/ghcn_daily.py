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

from ..constants import GHCN_DAILY_CSV_URL, GHCN_DAILY_S3_CSV_URL, c_to_f
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

    def download_csv_text(self, use_cache: bool = True) -> tuple[str, str]:
        """Download the station CSV, trying NCEI first, then the AWS Open Data mirror.

        Returns (csv_text, format) where format is 'wide' (NCEI access CSV) or
        'long' (AWS by_station CSV: ID,DATE,ELEMENT,DATA_VALUE,M_FLAG,Q_FLAG,S_FLAG,OBS_TIME).
        """
        primary = GHCN_DAILY_CSV_URL.format(station_id=self.station_id)
        fallback = GHCN_DAILY_S3_CSV_URL.format(station_id=self.station_id)
        try:
            log.info("Downloading GHCN-Daily CSV (NCEI): %s", primary)
            # Single attempt for the primary: if NCEI is blocked/down we fall over to the
            # AWS mirror quickly instead of burning the full retry/backoff budget.
            import dataclasses
            quick = dataclasses.replace(self.http, max_retries=0)
            return quick.get_text(primary, use_cache=use_cache), "wide"
        except Exception as exc:  # noqa: BLE001
            log.warning("NCEI GHCN download failed (%s); trying AWS Open Data mirror.",
                        str(exc)[:200])
        log.info("Downloading GHCN-Daily CSV (AWS): %s", fallback)
        return self.http.get_text(fallback, use_cache=use_cache), "long"

    def load(self, csv_text: Optional[str] = None, use_cache: bool = True,
             csv_format: Optional[str] = None) -> pd.DataFrame:
        """Return a tidy daily frame indexed by local calendar date.

        Columns include tmax_c/tmax_f, tmin_c/tmin_f, prcp_mm, snow_mm, snwd_mm and the
        associated M/Q/S flag columns where present.
        """
        if csv_text is None:
            csv_text, csv_format = self.download_csv_text(use_cache=use_cache)
        if csv_format is None:
            # Sniff: the long format's header starts with 'ID,DATE,ELEMENT'.
            csv_format = "long" if csv_text[:30].startswith("ID,DATE,ELEMENT") else "wide"
        if csv_format == "long":
            return self.parse_long_csv(csv_text)
        return self.parse_csv(csv_text)

    def parse_long_csv(self, csv_text: str) -> pd.DataFrame:
        """Parse the AWS Open Data by-station long-format CSV into the same tidy frame."""
        raw = pd.read_csv(io.StringIO(csv_text), dtype=str, low_memory=False)
        required = {"DATE", "ELEMENT", "DATA_VALUE"}
        if not required.issubset(raw.columns):
            raise ObservationError(
                f"GHCN long CSV missing columns {required - set(raw.columns)}; "
                "schema may have changed."
            )
        raw = raw[raw["ELEMENT"].isin(CORE_ELEMENTS)].copy()
        raw["value"] = pd.to_numeric(raw["DATA_VALUE"], errors="coerce")
        raw["date"] = pd.to_datetime(raw["DATE"], format="%Y%m%d", errors="coerce").dt.date

        out = pd.DataFrame({"date": sorted(raw["date"].dropna().unique())})
        for elem in CORE_ELEMENTS:
            sub = raw[raw["ELEMENT"] == elem]
            if sub.empty:
                continue
            series = sub.set_index("date")["value"]
            series = series[~series.index.duplicated(keep="first")]
            vals = out["date"].map(series)
            if elem in TENTHS_C_ELEMENTS:
                celsius = vals / 10.0
                out[f"{elem.lower()}_c"] = celsius
                out[f"{elem.lower()}_f"] = celsius.apply(
                    lambda v: c_to_f(v) if pd.notna(v) else np.nan)
            elif elem in TENTHS_MM_ELEMENTS:
                out[f"{elem.lower()}_mm"] = vals / 10.0
            for flag_col, fname in (("M_FLAG", "mflag"), ("Q_FLAG", "qflag"), ("S_FLAG", "sflag")):
                if flag_col in sub.columns:
                    fseries = sub.set_index("date")[flag_col]
                    fseries = fseries[~fseries.index.duplicated(keep="first")]
                    out[f"{elem.lower()}_{fname}"] = out["date"].map(fseries).replace("", np.nan)

        out = out.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        out["station_id"] = self.station_id
        out["provenance"] = "ghcn_daily_final"
        return out

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
