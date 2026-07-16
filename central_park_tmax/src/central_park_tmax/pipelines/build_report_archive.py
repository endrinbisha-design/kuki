"""Retrieve, parse, and version-archive the Central Park NWS Daily Climate Report."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import AppConfig
from ..data.nws_api import NwsApiClient, retrieved_at
from ..data.nws_climate_report import parse_climate_report
from ..data.report_archive import ReportArchive
from ..data.storage import http_client_from_config
from ..logging_config import get_logger

log = get_logger(__name__)


def archive_path(cfg: AppConfig) -> Path:
    return Path(cfg.paths.nws_reports_dir) / "cli_report_versions.jsonl"


def fetch_and_archive_latest(cfg: AppConfig) -> Optional[dict]:
    """Fetch the latest Central Park CLI, parse, and append as a new version (never overwrite)."""
    http = http_client_from_config(cfg)
    client = NwsApiClient(http)
    text, issuance = client.latest_central_park_cli()
    report = parse_climate_report(text, retrieved_at_utc=retrieved_at(), source="nws_api")
    archive = ReportArchive(archive_path(cfg))
    newly = archive.add_version(report, retrieved_at(), source="nws_api")
    rec = report.to_record(retrieved_at(), "nws_api")
    rec["newly_archived"] = newly
    return rec


def archive_report_text(cfg: AppConfig, raw_text: str, source: str = "manual") -> dict:
    """Archive a report from raw text (e.g. a fixture or a manual paste)."""
    report = parse_climate_report(raw_text, retrieved_at_utc=retrieved_at(), source=source)
    archive = ReportArchive(archive_path(cfg))
    newly = archive.add_version(report, retrieved_at(), source=source)
    rec = report.to_record(retrieved_at(), source)
    rec["newly_archived"] = newly
    return rec
