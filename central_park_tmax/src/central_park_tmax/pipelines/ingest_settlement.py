"""Settlement monitoring: retrieve + version reports, reconstruct METAR maxima, resolve value.

Retrieves the Central Park CLI (or archives supplied text), preserves every version, compares
against relevant METAR highs, flags review/delay conditions, and resolves the
settlement-eligible value per configured timing via the settlement state machine. NEVER
overwrites prior versions; NEVER automates trading.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from ..config import AppConfig
from ..contracts.settlement_state import evaluate_settlement
from ..data.metar import reconstruct_daily_maxima
from ..data.report_archive import ReportArchive
from ..data.storage import write_json
from ..logging_config import get_logger
from ..time_utils import contract_timing, now_utc
from .build_report_archive import archive_path
from ..reporting.contract_report import render_settlement_text

log = get_logger(__name__)


def monitor_settlement(
    cfg: AppConfig,
    target_date: date,
    obs: Optional[pd.DataFrame] = None,
    fetch_live: bool = True,
    now_override_utc=None,
) -> dict:
    archive = ReportArchive(archive_path(cfg))

    if fetch_live:
        try:
            from .build_report_archive import fetch_and_archive_latest
            fetch_and_archive_latest(cfg)
        except Exception as exc:  # noqa: BLE001
            log.warning("Live report fetch failed (using existing archive): %s", exc)

    # Reconstruct METAR maxima for consistency review, when observations are supplied.
    metar_6h = metar_24h = None
    if obs is not None and not obs.empty:
        rec = reconstruct_daily_maxima(obs, target_date)
        metar_6h, metar_24h = rec.metar_6h_max_f, rec.metar_24h_max_f

    timing_cfg = cfg.contracts.timing if cfg.contracts else None
    exp_hours = tuple(timing_cfg.normal_expiration_candidate_hours) if timing_cfg else (7, 8)
    lt = timing_cfg.last_trading_local if timing_cfg else {"hour": 23, "minute": 59}
    dd = timing_cfg.delayed_determination_local if timing_cfg else {"hour": 11, "minute": 0}

    # Use the earliest eligible report's issuance as the release time when available.
    versions = archive.versions_for(target_date)
    release_local = None
    if versions:
        from ..data.report_archive import _parse_iso_utc
        from ..time_utils import to_local
        rel = _parse_iso_utc(versions[0].get("issuance_utc"))
        release_local = to_local(rel) if rel else None

    timing = contract_timing(
        target_date, report_release_local=release_local,
        last_trading_hm=(lt["hour"], lt["minute"]),
        expiration_candidate_hours=exp_hours,
        delayed_hm=(dd["hour"], dd["minute"]),
    )

    now = now_override_utc or now_utc()
    record = evaluate_settlement(
        station=cfg.station.shorthand, target_date=target_date, timing=timing,
        archive=archive, now_utc=now, metar_6h_max_f=metar_6h, metar_24h_max_f=metar_24h,
        review_tolerance_f=(cfg.contracts.metar_consistency_tolerance_f if cfg.contracts else 1.0),
    )
    out = record.to_dict()
    revisions = archive.detect_revisions(target_date)
    out["detected_revisions"] = revisions
    path = Path(cfg.paths.settlement_dir) / f"settlement_{target_date.isoformat()}.json"
    write_json(path, out)
    log.info("Settlement record saved: %s", path)
    print(render_settlement_text(out))
    return out
