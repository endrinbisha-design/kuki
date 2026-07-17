"""Settlement state machine tying timing, report versions, and review together.

States (constants.SettlementState):
  forecast_open -> trading_closed -> awaiting_report -> preliminary_report_available
  -> [consistency_review] -> expiration_value_locked
  (+ later_revision_ignored_for_settlement, outcome_under_review)

The weather model NEVER declares the settlement result. Once an eligible NWS report value
exists at expiration, this machine locks it; later revisions are recorded but ignored for
settlement.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from ..constants import SettlementState, TargetProvenance
from ..data.report_archive import ReportArchive, SettlementResolution
from ..logging_config import get_logger
from ..time_utils import ContractTiming, to_utc
from .outcome_review import ReviewDecision, review_conditions

log = get_logger(__name__)


@dataclass
class SettlementRecord:
    station: str
    target_date: date
    timing: ContractTiming
    state: SettlementState
    resolution: SettlementResolution
    review: ReviewDecision
    determination_delayed: bool
    evaluated_at_utc: datetime

    def to_dict(self) -> dict:
        r = self.resolution
        return {
            "station": self.station,
            "target_date_local": self.target_date.isoformat(),
            "last_trading_time_local": self.timing.last_trading_local.isoformat(),
            "normal_expiration_time_local": self.timing.normal_expiration_local.isoformat(),
            "delayed_determination_time_local": self.timing.delayed_determination_local.isoformat(),
            "determination_delayed": self.determination_delayed,
            "delay_reason": self.review.as_reason_string(),
            "report_versions": [
                {
                    "retrieved_at": v.get("retrieved_at_utc"),
                    "issuance_utc": v.get("issuance_utc"),
                    "reported_tmax_f": v.get("reported_max_f"),
                    "status": v.get("status"),
                    "eligible_at_expiration": (i == r.eligible_version_index),
                    "superseded_before_expiration": (
                        i != r.eligible_version_index and r.eligible_version_index is not None
                        and i < r.eligible_version_index),
                }
                for i, v in enumerate(r.versions)
            ],
            "settlement_eligible_tmax_f": r.settlement_eligible_max_f,
            "settlement_status": self.state.value,
            "provenance": r.provenance.value,
            "later_revision_tmax_f": r.later_revision_max_f,
            "later_revision_affects_settlement": False,
            "evaluated_at_utc": self.evaluated_at_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }


def evaluate_settlement(
    station: str,
    target_date: date,
    timing: ContractTiming,
    archive: ReportArchive,
    now_utc: datetime,
    metar_6h_max_f: Optional[float] = None,
    metar_24h_max_f: Optional[float] = None,
    review_tolerance_f: float = 1.0,
) -> SettlementRecord:
    """Advance the settlement state machine given current time and archived reports."""
    expiration_utc = to_utc(timing.normal_expiration_local)
    resolution = archive.determine_settlement_value(target_date, expiration_utc)
    versions = resolution.versions

    # Determine review conditions (using earliest vs latest eligible report values).
    earlier_max = versions[0].get("reported_max_f") if versions else None
    eligible_max = resolution.settlement_eligible_max_f
    review = review_conditions(
        reported_max_f=eligible_max,
        metar_6h_max_f=metar_6h_max_f,
        metar_24h_max_f=metar_24h_max_f,
        earlier_reported_max_f=earlier_max if earlier_max != eligible_max else None,
        tolerance_f=review_tolerance_f,
    )

    # State selection.
    state = _select_state(now_utc, timing, resolution, review)
    return SettlementRecord(
        station=station, target_date=target_date, timing=timing, state=state,
        resolution=resolution, review=review, determination_delayed=review.delayed,
        evaluated_at_utc=now_utc,
    )


def _select_state(now_utc: datetime, timing: ContractTiming,
                  resolution: SettlementResolution, review: ReviewDecision) -> SettlementState:
    last_trading = to_utc(timing.last_trading_local)
    expiration = to_utc(timing.normal_expiration_local)
    has_report = resolution.n_versions > 0
    eligible = resolution.settlement_eligible_max_f is not None

    if now_utc < last_trading:
        return SettlementState.FORECAST_OPEN
    if now_utc < expiration:
        if not has_report:
            # Between last trading and the morning report window: trading_closed; once the
            # report is plausibly due (within ~3h of expiration) and still absent: awaiting.
            from datetime import timedelta
            if now_utc < expiration - timedelta(hours=3):
                return SettlementState.TRADING_CLOSED
            return SettlementState.AWAITING_REPORT
        if review.delayed:
            return SettlementState.CONSISTENCY_REVIEW
        return SettlementState.PRELIMINARY_REPORT_AVAILABLE
    # At/after expiration:
    if not eligible:
        return SettlementState.AWAITING_REPORT
    if review.delayed and now_utc < to_utc(timing.delayed_determination_local):
        return SettlementState.OUTCOME_UNDER_REVIEW
    if resolution.revised_after_expiration:
        return SettlementState.LATER_REVISION_IGNORED
    return SettlementState.EXPIRATION_VALUE_LOCKED
