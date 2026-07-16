from datetime import date, datetime, timezone

from central_park_tmax.constants import SettlementState
from central_park_tmax.contracts.outcome_review import review_conditions
from central_park_tmax.contracts.settlement_state import evaluate_settlement
from central_park_tmax.data.nws_climate_report import ClimateReport
from central_park_tmax.data.report_archive import ReportArchive
from central_park_tmax.time_utils import NY, contract_timing, to_utc


def test_review_flagged_when_report_below_earlier():
    d = review_conditions(reported_max_f=88, metar_6h_max_f=None, metar_24h_max_f=None,
                          earlier_reported_max_f=90)
    assert d.delayed is True
    assert any("lower_than_earlier" in r for r in d.reasons)


def test_review_flagged_on_metar_inconsistency():
    d = review_conditions(reported_max_f=88, metar_6h_max_f=92.0, metar_24h_max_f=None,
                          earlier_reported_max_f=None, tolerance_f=1.0)
    assert d.delayed is True
    assert any("6h_metar" in r for r in d.reasons)


def test_no_review_when_consistent():
    d = review_conditions(reported_max_f=90, metar_6h_max_f=90.4, metar_24h_max_f=90.2,
                          earlier_reported_max_f=90, tolerance_f=1.0)
    assert d.delayed is False


def _report(target, maxf, issuance_local, status="preliminary"):
    return ClimateReport(target_date=target, reported_max_f=maxf, max_time_lst="300 PM",
                         issuance_local=issuance_local, issuance_utc=to_utc(issuance_local),
                         status=status, issuing_office="OKX", product_id="CLINYC",
                         raw_text=f"CLIMATE SUMMARY FOR JULY {target.day} {target.year} {maxf}")


def test_state_machine_locks_value_after_expiration(tmp_path):
    archive = ReportArchive(tmp_path / "v.jsonl")
    target = date(2024, 7, 15)
    now = datetime.now(tz=timezone.utc)
    archive.add_version(_report(target, 90, datetime(2024, 7, 16, 6, 5, tzinfo=NY)), now, "f")
    timing = contract_timing(target, report_release_local=datetime(2024, 7, 16, 6, 5, tzinfo=NY))
    # Evaluate well after expiration.
    after = to_utc(datetime(2024, 7, 16, 9, 0, tzinfo=NY))
    rec = evaluate_settlement("KNYC", target, timing, archive, after)
    assert rec.state == SettlementState.EXPIRATION_VALUE_LOCKED
    assert rec.resolution.settlement_eligible_max_f == 90
    d = rec.to_dict()
    assert d["later_revision_affects_settlement"] is False


def test_state_forecast_open_before_last_trading(tmp_path):
    archive = ReportArchive(tmp_path / "v.jsonl")
    target = date(2024, 7, 15)
    timing = contract_timing(target)
    before = to_utc(datetime(2024, 7, 15, 10, 0, tzinfo=NY))
    rec = evaluate_settlement("KNYC", target, timing, archive, before)
    assert rec.state == SettlementState.FORECAST_OPEN
