"""METAR / hourly-observation helpers for maximum-temperature cross-checks.

Two reconstructed maxima are produced, kept SEPARATE from the NWS report maximum:
  * ``metar_hourly_max``  : max of routine hourly METAR air temperatures over the local day.
  * ``metar_6h_24h_max``  : max implied by the 6-hour (group 1s...) and 24-hour (group 4...)
                            maximum-temperature remark groups when present.

These are used only to (a) flag possible delayed-determination cases and (b) analyze
disagreement rates. They are never treated as equivalent to the CLI report maximum.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from ..constants import c_to_f
from ..logging_config import get_logger
from ..time_utils import is_in_local_day, to_utc

log = get_logger(__name__)

# 6-hour max temp remark group: T = tenths of deg C, sign digit s (0 positive, 1 negative).
_SIX_HOUR_MAX_RE = re.compile(r"\b1(?P<sign>[01])(?P<tenths>\d{3})\b")
# 24-hour max/min group: 4 s Tmax(3) s Tmin(3)
_TWENTYFOUR_RE = re.compile(r"\b4(?P<smax>[01])(?P<tmax>\d{3})(?P<smin>[01])(?P<tmin>\d{3})\b")


def _decode_tenths_c(sign: str, tenths: str) -> float:
    val = int(tenths) / 10.0
    return -val if sign == "1" else val


def six_hour_max_f(raw_metar: str) -> Optional[float]:
    m = _SIX_HOUR_MAX_RE.search(raw_metar or "")
    if not m:
        return None
    return c_to_f(_decode_tenths_c(m.group("sign"), m.group("tenths")))


def twentyfour_hour_max_f(raw_metar: str) -> Optional[float]:
    m = _TWENTYFOUR_RE.search(raw_metar or "")
    if not m:
        return None
    return c_to_f(_decode_tenths_c(m.group("smax"), m.group("tmax")))


@dataclass
class ReconstructedMaxima:
    target_date: date
    metar_hourly_max_f: Optional[float]
    metar_6h_max_f: Optional[float]
    metar_24h_max_f: Optional[float]
    n_obs: int

    def to_dict(self) -> dict:
        return {
            "target_date": self.target_date.isoformat(),
            "metar_hourly_max_f": self.metar_hourly_max_f,
            "metar_6h_max_f": self.metar_6h_max_f,
            "metar_24h_max_f": self.metar_24h_max_f,
            "n_obs": self.n_obs,
        }


def reconstruct_daily_maxima(obs: pd.DataFrame, target_date: date) -> ReconstructedMaxima:
    """Reconstruct maxima for ``target_date`` from an hourly observation frame.

    ``obs`` must have columns: 'timestamp_utc' (aware datetime), 'temp_f' (float), and
    optionally 'raw_metar' (str). Only observations within the local target day count.
    """
    if obs.empty:
        return ReconstructedMaxima(target_date, None, None, None, 0)

    df = obs.copy()
    ts = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
    in_day = ts.apply(lambda t: is_in_local_day(to_utc(t.to_pydatetime()), target_date)
                      if pd.notna(t) else False)
    day = df.loc[in_day.to_numpy()]
    if day.empty:
        return ReconstructedMaxima(target_date, None, None, None, 0)

    hourly_max = float(np.nanmax(day["temp_f"].to_numpy())) if "temp_f" in day else None

    six_vals, tf_vals = [], []
    if "raw_metar" in day.columns:
        for raw in day["raw_metar"].dropna():
            v6 = six_hour_max_f(raw)
            if v6 is not None:
                six_vals.append(v6)
            v24 = twentyfour_hour_max_f(raw)
            if v24 is not None:
                tf_vals.append(v24)

    return ReconstructedMaxima(
        target_date=target_date,
        metar_hourly_max_f=hourly_max,
        metar_6h_max_f=max(six_vals) if six_vals else None,
        metar_24h_max_f=max(tf_vals) if tf_vals else None,
        n_obs=len(day),
    )
