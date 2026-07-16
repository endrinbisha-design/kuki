from datetime import datetime, timezone

from central_park_tmax.data.nws_climate_report import parse_climate_report
from central_park_tmax.data.report_archive import ReportArchive


def _load(report_fixtures, name):
    return (report_fixtures / name).read_text(encoding="utf-8")


def test_parse_preliminary(report_fixtures):
    text = _load(report_fixtures, "clinyc_20240715_preliminary.txt")
    rep = parse_climate_report(text, source="fixture")
    assert rep.target_date.isoformat() == "2024-07-15"
    assert rep.reported_max_f == 88
    assert rep.reported_min_f == 72
    assert rep.status == "preliminary"
    assert rep.issuance_utc is not None


def test_parse_corrected_detected(report_fixtures):
    text = _load(report_fixtures, "clinyc_20240715_corrected.txt")
    rep = parse_climate_report(text, source="fixture")
    assert rep.reported_max_f == 90
    assert rep.status == "corrected"


def test_versions_never_overwritten(tmp_path, report_fixtures):
    archive = ReportArchive(tmp_path / "versions.jsonl")
    now = datetime.now(tz=timezone.utc)
    prelim = parse_climate_report(_load(report_fixtures, "clinyc_20240715_preliminary.txt"), source="f")
    corr = parse_climate_report(_load(report_fixtures, "clinyc_20240715_corrected.txt"), source="f")

    assert archive.add_version(prelim, now, "fixture") is True
    assert archive.add_version(corr, now, "fixture") is True
    # Re-adding the identical preliminary content does not create a new version.
    assert archive.add_version(prelim, now, "fixture") is False

    from datetime import date
    versions = archive.versions_for(date(2024, 7, 15))
    assert len(versions) == 2
    assert [v["reported_max_f"] for v in versions] == [88, 90]

    revisions = archive.detect_revisions(date(2024, 7, 15))
    assert len(revisions) == 1
    assert revisions[0]["from_max_f"] == 88 and revisions[0]["to_max_f"] == 90
    assert revisions[0]["direction"] == "up"


def test_parse_failure_raises_not_guess():
    import pytest
    from central_park_tmax.data import ReportParseError
    with pytest.raises(ReportParseError):
        parse_climate_report("this is not a climate report at all", source="bad")
