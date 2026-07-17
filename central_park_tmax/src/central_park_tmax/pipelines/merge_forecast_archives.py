"""Join secondary-model point archives into the training dataset as inter-model features.

Reads ``forecast_archive_<source>.csv`` files produced by build-forecast-archive and
left-joins their Central Park daily maxima onto the dataset by (target_date, vintage),
then (re)computes inter-model disagreement features:

  * model_<src>_tmax_f          per secondary source
  * intermodel_mean_f / spread_f / range_f   across primary baseline + secondaries
  * baseline_minus_<src>_f      pairwise disagreement with the primary baseline

These are the strongest known predictors of *when* the primary baseline is wrong (small
spread on a well-forecast cooldown -> trust raw guidance; large spread -> wide error).
Secondary archives are point-in-time extracts built under the same no-leakage vintage
rules as the primary dataset.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from ..config import AppConfig
from ..logging_config import get_logger

log = get_logger(__name__)


def merge_forecast_archives(cfg: AppConfig, dataset: pd.DataFrame,
                            sources: Optional[list[str]] = None) -> pd.DataFrame:
    """Return the dataset with secondary-model columns + inter-model features merged in."""
    sources = sources or ["hrrr", "gfs"]
    df = dataset.copy()
    if "date" not in df.columns or "vintage" not in df.columns:
        raise ValueError("dataset must have 'date' and 'vintage' columns")

    merged_any = []
    for src in sources:
        path = Path(cfg.paths.forecasts_dir) / f"forecast_archive_{src}.csv"
        if not path.exists():
            log.warning("No forecast archive for %s at %s; skipping.", src, path)
            continue
        arch = pd.read_csv(path, dtype={"target_date": str})
        arch = arch.dropna(subset=["cp_tmax_f"])
        col = f"model_{src}_tmax_f"
        arch = arch.rename(columns={"target_date": "date", "cp_tmax_f": col})
        arch = arch[["date", "vintage", col]].drop_duplicates(subset=["date", "vintage"])
        before = df[col].notna().sum() if col in df.columns else 0
        if col in df.columns:
            df = df.drop(columns=[col])
        df = df.merge(arch, on=["date", "vintage"], how="left")
        log.info("Merged %s: %d/%d rows now have %s (was %d).",
                 src, int(df[col].notna().sum()), len(df), col, before)
        merged_any.append(col)

    if merged_any:
        model_cols = ["baseline_tmax_f"] + merged_any
        vals = df[model_cols].apply(pd.to_numeric, errors="coerce")
        counts = vals.notna().sum(axis=1)
        df["intermodel_mean_f"] = vals.mean(axis=1)
        df["intermodel_spread_f"] = vals.std(axis=1, ddof=0).where(counts >= 2)
        df["intermodel_range_f"] = (vals.max(axis=1) - vals.min(axis=1)).where(counts >= 2)
        for col in merged_any:
            df[f"baseline_minus_{col.replace('model_', '').replace('_tmax_f', '')}_f"] = (
                pd.to_numeric(df["baseline_tmax_f"], errors="coerce") - vals[col])
    return df
