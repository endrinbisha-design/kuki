"""Append-only archive of NWS Daily Climate Report versions + expiration-value logic.

Every retrieved report version is stored and NEVER overwritten. For a given target date
and contract expiration time we can reconstruct:
  * which versions existed at/ before expiration,
  * the settlement-eligible value (latest version released at/before expiration),
  * whether an earlier value was superseded before expiration (pre-expiration revision),
  * whether a later revision exists that must be ignored for settlement.

'Availability' for settlement is judged by the report's NWS *release* (issuance) time when
known, falling back to our retrieval timestamp with a recorded warning.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from ..constants import TargetProvenance
from ..logging_config import get_logger
from ..time_utils import to_utc
from .nws_climate_report import ClimateReport
from .storage import AppendOnlyStore

log = get_logger(__name__)


def _parse_iso_utc(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        return to_utc(datetime.fromisoformat(s))
    except ValueError:
        return None


@dataclass
class SettlementResolution:
    target_date: date
    settlement_eligible_max_f: Optional[int]
    eligible_version_index: Optional[int]
    provenance: TargetProvenance
    superseded_before_expiration: bool
    revised_after_expiration: bool
    later_revision_max_f: Optional[int]
    n_versions: int
    used_retrieval_time_fallback: bool
    versions: list[dict]

    def to_dict(self) -> dict:
        return {
            "target_date": self.target_date.isoformat(),
            "settlement_eligible_tmax_f": self.settlement_eligible_max_f,
            "eligible_version_index": self.eligible_version_index,
            "provenance": self.provenance.value,
            "superseded_before_expiration": self.superseded_before_expiration,
            "revised_after_expiration": self.revised_after_expiration,
            "later_revision_tmax_f": self.later_revision_max_f,
            "later_revision_affects_settlement": False,
            "n_versions": self.n_versions,
            "used_retrieval_time_fallback": self.used_retrieval_time_fallback,
        }


class ReportArchive:
    """One append-only JSONL store per station holding all report versions."""

    def __init__(self, path: Path | str):
        self.store = AppendOnlyStore(path)

    # ---- ingestion -------------------------------------------------------------------
    def add_version(self, report: ClimateReport, retrieved_at_utc: datetime, source: str) -> bool:
        """Append a report version. Returns True if newly stored, False if exact duplicate.

        Never overwrites an existing version. Two retrievals with identical raw content
        (same content hash) are treated as the same version and not duplicated.
        """
        record = report.to_record(retrieved_at_utc=retrieved_at_utc, source=source)
        newly = self.store.append_if_new(record, dedupe_key="content_sha256")
        if newly:
            log.info("Archived CLI version target=%s max=%sF status=%s source=%s",
                     report.target_date, report.reported_max_f, report.status, source)
        else:
            log.debug("CLI version already archived (identical content) target=%s",
                      report.target_date)
        return newly

    def versions_for(self, target_date: date) -> list[dict]:
        tgt = target_date.isoformat()
        rows = [r for r in self.store.read_all() if r.get("target_date") == tgt]
        # Order by best-known availability time, then retrieval time.
        def _key(r: dict) -> str:
            return r.get("issuance_utc") or r.get("retrieved_at_utc") or ""
        return sorted(rows, key=_key)

    def all_target_dates(self) -> list[date]:
        seen = sorted({r.get("target_date") for r in self.store.read_all() if r.get("target_date")})
        return [date.fromisoformat(s) for s in seen]

    def detect_revisions(self, target_date: date) -> list[dict]:
        """Return version-to-version changes in the reported maximum (revision events)."""
        versions = self.versions_for(target_date)
        changes: list[dict] = []
        prev: Optional[dict] = None
        for v in versions:
            if prev is not None and v.get("reported_max_f") != prev.get("reported_max_f"):
                changes.append({
                    "from_max_f": prev.get("reported_max_f"),
                    "to_max_f": v.get("reported_max_f"),
                    "from_status": prev.get("status"),
                    "to_status": v.get("status"),
                    "to_available_utc": v.get("issuance_utc") or v.get("retrieved_at_utc"),
                    "direction": "down" if (v.get("reported_max_f") or 0) < (prev.get("reported_max_f") or 0) else "up",
                })
            prev = v
        return changes

    # ---- settlement resolution -------------------------------------------------------
    def determine_settlement_value(self, target_date: date, expiration_utc: datetime) -> SettlementResolution:
        """Resolve the settlement-eligible value at ``expiration_utc``.

        Post-expiration revisions are recorded but do NOT alter the settlement value.
        Pre-expiration revisions replace an earlier eligible value.
        """
        versions = self.versions_for(target_date)
        if not versions:
            return SettlementResolution(
                target_date=target_date, settlement_eligible_max_f=None,
                eligible_version_index=None, provenance=TargetProvenance.MISSING,
                superseded_before_expiration=False, revised_after_expiration=False,
                later_revision_max_f=None, n_versions=0, used_retrieval_time_fallback=False,
                versions=[],
            )

        used_fallback = False
        available: list[tuple[int, dict]] = []
        later: list[tuple[int, dict]] = []
        for idx, v in enumerate(versions):
            avail = _parse_iso_utc(v.get("issuance_utc"))
            if avail is None:
                avail = _parse_iso_utc(v.get("retrieved_at_utc"))
                used_fallback = used_fallback or avail is not None
            if avail is not None and avail <= expiration_utc:
                available.append((idx, v))
            else:
                later.append((idx, v))

        if not available:
            # Nothing was released by expiration => unresolved at expiration time.
            later_val = later[-1][1].get("reported_max_f") if later else None
            return SettlementResolution(
                target_date=target_date, settlement_eligible_max_f=None,
                eligible_version_index=None, provenance=TargetProvenance.MISSING,
                superseded_before_expiration=False,
                revised_after_expiration=bool(later),
                later_revision_max_f=later_val, n_versions=len(versions),
                used_retrieval_time_fallback=used_fallback, versions=versions,
            )

        eligible_idx, eligible = available[-1]
        eligible_val = eligible.get("reported_max_f")

        # Did an earlier eligible version carry a different value (pre-expiration revision)?
        earlier_vals = [v.get("reported_max_f") for i, v in available[:-1]]
        superseded_before = any(val != eligible_val for val in earlier_vals)

        # Any later (post-expiration) revision with a different value?
        later_diff = [v.get("reported_max_f") for i, v in later
                      if v.get("reported_max_f") != eligible_val]
        revised_after = len(later_diff) > 0
        later_val = later[-1][1].get("reported_max_f") if later else None

        if superseded_before:
            provenance = TargetProvenance.NWS_PRE_EXPIRATION_REVISION
        else:
            provenance = TargetProvenance.NWS_AT_EXPIRATION

        return SettlementResolution(
            target_date=target_date,
            settlement_eligible_max_f=eligible_val,
            eligible_version_index=eligible_idx,
            provenance=provenance,
            superseded_before_expiration=superseded_before,
            revised_after_expiration=revised_after,
            later_revision_max_f=later_val,
            n_versions=len(versions),
            used_retrieval_time_fallback=used_fallback,
            versions=versions,
        )
