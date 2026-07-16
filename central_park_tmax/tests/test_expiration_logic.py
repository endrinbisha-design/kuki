from datetime import date, datetime, timezone

from central_park_tmax.constants import TargetProvenance
from central_park_tmax.data.nws_climate_report import ClimateReport
from central_park_tmax.data.report_archive import ReportArchive
from central_park_tmax.time_utils import NY, to_utc


def _report(target, maxf, issuance_local, status="preliminary"):
    return ClimateReport(
        target_date=target, reported_max_f=maxf, max_time_lst="300 PM",
        issuance_local=issuance_local, issuance_utc=to_utc(issuance_local),
        status=status, issuing_office="OKX", product_id="CLINYC",
        raw_text=f"CLIMATE SUMMARY FOR JULY {target.day} {target.year} max {maxf} {issuance_local}",
    )


def test_post_expiration_revision_does_not_change_settlement(tmp_path):
    archive = ReportArchive(tmp_path / "v.jsonl")
    target = date(2024, 7, 15)
    now = datetime.now(tz=timezone.utc)
    # v1 released 6:05 AM next day (before 7 AM expiration) = 88
    v1 = _report(target, 88, datetime(2024, 7, 16, 6, 5, tzinfo=NY))
    # v2 released 11:05 AM next day (AFTER 7 AM expiration) = 90 (later revision)
    v2 = _report(target, 90, datetime(2024, 7, 16, 11, 5, tzinfo=NY), status="corrected")
    archive.add_version(v1, now, "f")
    archive.add_version(v2, now, "f")

    expiration_utc = to_utc(datetime(2024, 7, 16, 7, 0, tzinfo=NY))
    res = archive.determine_settlement_value(target, expiration_utc)
    assert res.settlement_eligible_max_f == 88          # value available at expiration
    assert res.revised_after_expiration is True
    assert res.later_revision_max_f == 90
    assert res.provenance == TargetProvenance.NWS_AT_EXPIRATION


def test_pre_expiration_revision_replaces_earlier_value(tmp_path):
    archive = ReportArchive(tmp_path / "v.jsonl")
    target = date(2024, 7, 15)
    now = datetime.now(tz=timezone.utc)
    # v1 at 6:05 AM = 88, v2 at 6:45 AM = 90, both before 7 AM expiration.
    v1 = _report(target, 88, datetime(2024, 7, 16, 6, 5, tzinfo=NY))
    v2 = _report(target, 90, datetime(2024, 7, 16, 6, 45, tzinfo=NY), status="corrected")
    archive.add_version(v1, now, "f")
    archive.add_version(v2, now, "f")

    expiration_utc = to_utc(datetime(2024, 7, 16, 7, 0, tzinfo=NY))
    res = archive.determine_settlement_value(target, expiration_utc)
    assert res.settlement_eligible_max_f == 90          # latest eligible pre-expiration value
    assert res.superseded_before_expiration is True
    assert res.provenance == TargetProvenance.NWS_PRE_EXPIRATION_REVISION


def test_no_report_by_expiration_is_unresolved(tmp_path):
    archive = ReportArchive(tmp_path / "v.jsonl")
    target = date(2024, 7, 15)
    now = datetime.now(tz=timezone.utc)
    v1 = _report(target, 90, datetime(2024, 7, 16, 9, 0, tzinfo=NY))  # after 7 AM
    archive.add_version(v1, now, "f")
    expiration_utc = to_utc(datetime(2024, 7, 16, 7, 0, tzinfo=NY))
    res = archive.determine_settlement_value(target, expiration_utc)
    assert res.settlement_eligible_max_f is None
    assert res.provenance == TargetProvenance.MISSING
