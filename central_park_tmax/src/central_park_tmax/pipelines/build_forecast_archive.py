"""Archive numerical-forecast runs' extracted point features for a date range.

For GRIB sources this can require substantial storage; we extract and cache only the
per-location point features actually needed (not full grids). In synthetic mode this produces
a lightweight offline archive so the rest of the pipeline is exercised end-to-end.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from ..config import AppConfig
from ..data.forecast_base import ForecastSource
from ..data.storage import write_json
from ..logging_config import get_logger
from ..time_utils import resolve_vintage, to_utc

log = get_logger(__name__)


def build_forecast_archive(cfg: AppConfig, source: ForecastSource, start: date, end: date) -> Path:
    """Extract per-(date,vintage) point daily-max features and save a compact archive CSV."""
    rows = []
    d = start
    while d <= end:
        for vintage in cfg.forecast_vintages:
            vt = resolve_vintage(d, vintage.day, vintage.hour, vintage.minute, vintage.name)
            issue_utc = to_utc(vt.issue_local)
            run = source.select_and_fetch(d, issue_utc, cfg.locations)
            if run is None:
                log.warning("archive: no usable %s run for %s %s", source.name, d, vintage.name)
                continue
            meta = source.get_metadata(run)
            rows.append({
                "target_date": d.isoformat(),
                "vintage": vintage.name,
                "source": source.name,
                "init_utc": meta["init_utc"],
                "cp_tmax_f": run.daily_max_f(cfg.locations.primary.key, d),
                "model_version": meta.get("model_version"),
                "provenance": meta.get("provenance"),
            })
        d += timedelta(days=1)
    out = Path(cfg.paths.forecasts_dir) / f"forecast_archive_{source.name}.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    write_json(Path(cfg.paths.forecasts_dir) / f"forecast_archive_{source.name}_meta.json",
               {"n_rows": len(rows), "source": source.name,
                "range": [start.isoformat(), end.isoformat()]})
    log.info("Wrote forecast archive: %s (%d rows)", out, len(rows))
    return out
