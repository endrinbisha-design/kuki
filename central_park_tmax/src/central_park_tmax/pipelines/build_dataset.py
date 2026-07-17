"""Build a leakage-safe training dataset of (target_date, vintage) feature rows.

For each target date and forecast vintage, this selects the latest baseline model run
available at the forecast issue time (no future runs), extracts features, and attaches the
label: the NWS Daily Climate Report integer maximum (contract/reporting target). GHCN final
TMAX is attached separately as the meteorological target and is NEVER silently used as the
contract label.

Two operating modes:
  * synthetic=True : fully offline; forecasts/labels/observations come from the synthetic
    generator (clearly tagged provenance). Enables end-to-end runs and tests without network.
  * synthetic=False: uses real sources. Labels come from the report archive when present;
    otherwise the row's contract label is left missing (provenance 'missing_or_unresolved')
    rather than fabricated.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd

from ..config import AppConfig
from ..constants import TargetProvenance, c_to_f, f_to_c
from ..data.forecast_base import ForecastSource
from ..data.report_archive import ReportArchive
from ..data.storage import write_json, write_manifest
from ..data.synthetic import (WeatherState, synthetic_observation_frame,
                              synthetic_report_max_f)
from ..features.build_features import build_feature_row
from ..logging_config import get_logger
from ..time_utils import resolve_vintage, to_utc
from .context import daily_history_from_ghcn, synthetic_daily_history

log = get_logger(__name__)


def _date_range(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def build_dataset(
    cfg: AppConfig,
    source: ForecastSource,
    start: date,
    end: date,
    synthetic: bool = False,
    normals: Optional[pd.DataFrame] = None,
    daily_tmax_f: Optional[pd.Series] = None,
    daily_prcp_mm: Optional[pd.Series] = None,
    report_archive: Optional[ReportArchive] = None,
    save: bool = True,
    vintages: Optional[list[str]] = None,
) -> pd.DataFrame:
    if normals is None or daily_tmax_f is None:
        if synthetic:
            hist = synthetic_daily_history(cfg.archive_start - timedelta(days=40), end)
            normals = normals if normals is not None else hist["normals"]
            daily_tmax_f = daily_tmax_f if daily_tmax_f is not None else hist["tmax_f"]
            daily_prcp_mm = daily_prcp_mm if daily_prcp_mm is not None else hist["prcp_mm"]
        else:
            raise ValueError("Non-synthetic dataset build requires normals and daily history.")

    active_vintages = [v for v in cfg.forecast_vintages
                       if vintages is None or v.name in vintages]

    # Resumable builds: reuse rows already present in the output CSV (matched on
    # (date, vintage)) and checkpoint after every date, so an interrupted multi-hour
    # archive build restarts where it left off instead of re-downloading everything.
    out_path = Path(cfg.paths.processed_dir) / ("dataset_synthetic.csv" if synthetic else "dataset.csv")
    rows: list[dict] = []
    done: set[tuple[str, str]] = set()
    if save and out_path.exists():
        try:
            existing = pd.read_csv(out_path, dtype={"date": str})
            rows = existing.to_dict("records")
            done = {(r["date"], r["vintage"]) for r in rows}
            log.info("Resuming dataset build: %d existing rows in %s", len(rows), out_path)
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not resume from %s (%s); rebuilding.", out_path, exc)

    for target_date in _date_range(start, end):
        date_had_new = False
        for vintage in active_vintages:
            if (target_date.isoformat(), vintage.name) in done:
                continue
            date_had_new = True
            vt = resolve_vintage(target_date, vintage.day, vintage.hour, vintage.minute, vintage.name)
            issue_utc = to_utc(vt.issue_local)
            run = source.select_and_fetch(target_date, issue_utc, cfg.locations)
            if run is None:
                log.warning("no usable %s run for target=%s vintage=%s",
                            source.name, target_date, vintage.name)
                continue

            obs = None
            if synthetic:
                obs = synthetic_observation_frame(target_date, up_to_utc=issue_utc)

            row = build_feature_row(
                target_date=target_date, vintage_name=vintage.name, issue_local=vt.issue_local,
                primary_run=run, locations=cfg.locations, normals=normals,
                daily_tmax_f=daily_tmax_f, daily_prcp_mm=daily_prcp_mm, obs=obs,
                trajectory_hours=cfg.trajectory_hours_local,
                reporting_method=cfg.reporting_convention.method,
            )

            # --- labels ---
            report_max, ghcn_max, provenance = _resolve_labels(
                target_date, synthetic, report_archive, daily_tmax_f)
            row["target_report_max_f"] = report_max
            row["target_ghcn_max_f"] = ghcn_max
            row["target_provenance"] = provenance.value
            rows.append(row)
            done.add((target_date.isoformat(), vintage.name))

        # Checkpoint after each date that added rows (atomic replace; cheap at this scale).
        if save and date_had_new and rows:
            pd.DataFrame(rows).to_csv(out_path, index=False)

    df = pd.DataFrame(rows)
    if save and not df.empty:
        df.to_csv(out_path, index=False)
        _write_schema(cfg, df, synthetic)
        write_manifest(Path(cfg.paths.processed_dir) / "dataset_manifest.json", [out_path],
                       extra={"n_rows": len(df), "synthetic": synthetic,
                              "date_range": [start.isoformat(), end.isoformat()]})
        log.info("Wrote dataset: %s (%d rows)", out_path, len(df))
    return df


def _resolve_labels(target_date, synthetic, report_archive, daily_tmax_f):
    ghcn_max = None
    if daily_tmax_f is not None:
        idx = pd.to_datetime(daily_tmax_f.index)
        ser = pd.Series(daily_tmax_f.to_numpy(dtype=float), index=idx)
        key = pd.Timestamp(target_date)
        if key in ser.index:
            ghcn_max = float(ser.loc[key])
    if synthetic:
        return synthetic_report_max_f(target_date), ghcn_max, TargetProvenance.RECONSTRUCTED
    # Real mode: archived NWS report is the preferred contract label.
    if report_archive is not None:
        versions = report_archive.versions_for(target_date)
        if versions:
            return int(versions[-1]["reported_max_f"]), ghcn_max, TargetProvenance.NWS_AT_EXPIRATION
    # Fallback RESEARCH label: GHCN final (explicitly tagged; never conflated with the
    # contemporaneous report). Rounded to the integer the report would publish.
    if ghcn_max is not None and not np.isnan(ghcn_max):
        return int(round(ghcn_max)), ghcn_max, TargetProvenance.GHCN_DAILY_FINAL
    return None, ghcn_max, TargetProvenance.MISSING


def _write_schema(cfg: AppConfig, df: pd.DataFrame, synthetic: bool) -> None:
    schema = {
        "columns": [{"name": c, "dtype": str(df[c].dtype)} for c in df.columns],
        "n_rows": len(df),
        "synthetic": synthetic,
        "reserved_bookkeeping_columns": sorted(
            [c for c in df.columns if c in {
                "date", "target_date", "vintage", "forecast_issue_local", "forecast_issue_utc",
                "forecast_init_utc", "forecast_source", "forecast_model_version", "provenance",
                "baseline_tmax_f", "target_report_max_f", "target_ghcn_max_f", "target_provenance"}]),
    }
    write_json(Path(cfg.paths.processed_dir) / "dataset_schema.json", schema)
