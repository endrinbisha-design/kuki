from datetime import date, datetime, timedelta, timezone

import pytest

from central_park_tmax.data.forecast_base import ForecastSource, RunHandle
from central_park_tmax.evaluation.diagnostics import (DataQualityError,
                                                      check_forecast_availability,
                                                      check_observation_availability)


class _Dummy(ForecastSource):
    name = "dummy"

    def list_available_runs(self, target_date, issued_before_utc):
        return []

    def fetch_run(self, run, locations, target_date):
        raise NotImplementedError


def test_run_initialized_after_issue_is_rejected():
    src = _Dummy()
    issue = datetime(2024, 7, 15, 12, tzinfo=timezone.utc)
    future_run = RunHandle(source="dummy", init_utc=issue + timedelta(hours=1),
                           cycle="future", availability_estimate_utc=issue + timedelta(hours=1))
    assert src.validate_run_availability(future_run, issue) is False


def test_run_available_before_issue_is_accepted():
    src = _Dummy()
    issue = datetime(2024, 7, 15, 12, tzinfo=timezone.utc)
    past_run = RunHandle(source="dummy", init_utc=issue - timedelta(hours=6),
                         cycle="past", availability_estimate_utc=issue - timedelta(hours=2))
    assert src.validate_run_availability(past_run, issue) is True


def test_run_available_after_issue_rejected_even_if_init_before():
    src = _Dummy()
    issue = datetime(2024, 7, 15, 12, tzinfo=timezone.utc)
    run = RunHandle(source="dummy", init_utc=issue - timedelta(hours=1),
                    cycle="latent", availability_estimate_utc=issue + timedelta(minutes=30))
    assert src.validate_run_availability(run, issue) is False


def test_diagnostic_rejects_future_forecast():
    issue = datetime(2024, 7, 15, 12, tzinfo=timezone.utc)
    with pytest.raises(DataQualityError):
        check_forecast_availability(issue + timedelta(hours=1), issue)


def test_diagnostic_rejects_future_observation():
    issue = datetime(2024, 7, 15, 12, tzinfo=timezone.utc)
    with pytest.raises(DataQualityError):
        check_observation_availability(issue + timedelta(minutes=1), issue)
