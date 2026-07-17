"""Archive numerical-forecast runs' extracted point features for a date range.

For GRIB sources this can require substantial storage; we extract and cache only the
per-location point features actually needed (not full grids). In synthetic mode this produces
a lightweight offline archive so the rest of the pipeline is exercised end-to-end.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from ..config import AppConfig
from ..data.forecast_base import ForecastSource
from ..data.storage import write_json
from ..logging_config import get_logger
from ..time_utils import resolve_vintage, to_utc

log = get_logger(__name__)


def build_forecast_archive(cfg: AppConfig, source: ForecastSource, start: date, end: date,
                           vintages: Optional[list[str]] = None) -> Path:
    """Extract per-(date,vintage) point daily-max features and save a compact archive CSV.

    Resumable like build_dataset: existing (target_date, vintage) rows in the output CSV
    are kept and skipped; progress checkpoints after every date.
    """
    out = Path(cfg.paths.forecasts_dir) / f"forecast_archive_{source.name}.csv"
    active = [v for v in cfg.forecast_vintages if vintages is None or v.name in vintages]
    rows: list[dict] = []
    done: set[tuple[str, str]] = set()
    if out.exists():
        try:
            existing = pd.read_csv(out, dtype={"target_date": str})
            rows = existing.to_dict("records")
            done = {(r["target_date"], r["vintage"]) for r in rows}
            log.info("Resuming forecast archive: %d rows", len(rows))
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not resume %s (%s); rebuilding.", out, exc)
    d = start
    while d <= end:
        wrote = False
        for vintage in active:
            if (d.isoformat(), vintage.name) in done:
                continue
            wrote = True
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
            done.add((d.isoformat(), vintage.name))
        if wrote and rows:
            pd.DataFrame(rows).to_csv(out, index=False)
        d += timedelta(days=1)
    pd.DataFrame(rows).to_csv(out, index=False)
    write_json(Path(cfg.paths.forecasts_dir) / f"forecast_archive_{source.name}_meta.json",
               {"n_rows": len(rows), "source": source.name,
                "range": [start.isoformat(), end.isoformat()]})
    log.info("Wrote forecast archive: %s (%d rows)", out, len(rows))
    return out
