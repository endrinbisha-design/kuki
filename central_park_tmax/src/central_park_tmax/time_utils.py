"""Time zone, local-calendar-day, DST, and contract-timing utilities.

All "local day" logic is anchored to America/New_York. The maximum-temperature target
covers the local calendar day 00:00:00 through 23:59:59.999999 in that zone, which is a
23-hour day on the spring-forward date and a 25-hour day on the fall-back date. We never
approximate a local day as a fixed 24-hour UTC window.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from .constants import TIMEZONE

NY = ZoneInfo(TIMEZONE)
UTC = timezone.utc


# --------------------------------------------------------------------------------------
# Basic conversions (cached: the same timestamps recur across many locations/features)
# --------------------------------------------------------------------------------------
@lru_cache(maxsize=262144)
def _to_utc_cached(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=NY)
    return dt.astimezone(UTC)


@lru_cache(maxsize=262144)
def _to_local_cached(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(NY)


def to_utc(dt: datetime) -> datetime:
    """Convert an aware datetime to UTC. Naive datetimes are assumed local (NY)."""
    return _to_utc_cached(dt)


def to_local(dt: datetime) -> datetime:
    """Convert an aware datetime to America/New_York. Naive assumed UTC."""
    return _to_local_cached(dt)


def now_local() -> datetime:
    return datetime.now(tz=NY)


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def local_datetime(d: date, hour: int, minute: int = 0, second: int = 0) -> datetime:
    """Build an aware NY-local datetime, folding correctly across DST.

    ``fold=0`` is used; for the ambiguous fall-back hour this selects the first
    (pre-transition, still-DST) occurrence, which is the conventional choice.
    """
    return datetime(d.year, d.month, d.day, hour, minute, second, tzinfo=NY)


# --------------------------------------------------------------------------------------
# Local calendar-day bounds
# --------------------------------------------------------------------------------------
def local_day_bounds(d: date) -> tuple[datetime, datetime]:
    """Return (start, end_exclusive) NY-local aware datetimes for local calendar day ``d``.

    end_exclusive is midnight of the following local day, so the half-open interval
    [start, end_exclusive) is exactly the local day regardless of DST length.
    """
    start = datetime.combine(d, time(0, 0), tzinfo=NY)
    end_excl = datetime.combine(d + timedelta(days=1), time(0, 0), tzinfo=NY)
    return start, end_excl


def local_day_bounds_utc(d: date) -> tuple[datetime, datetime]:
    start, end = local_day_bounds(d)
    return to_utc(start), to_utc(end)


def local_day_length_hours(d: date) -> float:
    """Length of NY-local calendar day ``d`` in hours (23, 24, or 25)."""
    start, end = local_day_bounds_utc(d)
    return (end - start).total_seconds() / 3600.0


def is_in_local_day(dt: datetime, d: date) -> bool:
    """True if aware ``dt`` falls within NY-local calendar day ``d`` (half-open)."""
    start, end = local_day_bounds_utc(d)
    u = to_utc(dt)
    return start <= u < end


def local_date_of(dt: datetime) -> date:
    """The NY-local calendar date on which aware ``dt`` falls."""
    return to_local(dt).date()


def next_local_date(reference: datetime | None = None) -> date:
    """The 'tomorrow' target date: the next local calendar day after ``reference``."""
    ref = reference or now_local()
    return to_local(ref).date() + timedelta(days=1)


def hours_remaining_in_local_day(dt: datetime, d: date) -> float:
    """Hours from aware ``dt`` until the end of NY-local day ``d`` (>= 0, clipped)."""
    _, end = local_day_bounds_utc(d)
    delta = (end - to_utc(dt)).total_seconds() / 3600.0
    return max(0.0, delta)


# --------------------------------------------------------------------------------------
# Forecast vintage resolution
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ForecastVintage:
    name: str
    issue_local: datetime

    @property
    def issue_utc(self) -> datetime:
        return to_utc(self.issue_local)


def resolve_vintage(target_date: date, day: str, hour: int, minute: int, name: str) -> ForecastVintage:
    """Resolve a configured vintage spec into a concrete issue timestamp.

    ``day`` is 'prev_day' (calendar day before target) or 'target_day'.
    """
    if day == "prev_day":
        base = target_date - timedelta(days=1)
    elif day == "target_day":
        base = target_date
    else:
        raise ValueError(f"Unknown vintage day anchor: {day!r} (expected prev_day/target_day)")
    return ForecastVintage(name=name, issue_local=local_datetime(base, hour, minute))


# --------------------------------------------------------------------------------------
# Contract / settlement timing
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ContractTiming:
    target_date: date
    last_trading_local: datetime
    normal_expiration_local: datetime
    delayed_determination_local: datetime


def last_trading_time(target_date: date, hour: int = 23, minute: int = 59) -> datetime:
    return local_datetime(target_date, hour, minute)


def normal_expiration_time(
    target_date: date,
    report_release_local: datetime | None,
    candidate_hours: tuple[int, ...] = (7, 8),
) -> datetime:
    """First applicable candidate expiration hour on/after report release.

    The expiration is the first of the candidate a.m. hours (default 7 or 8 ET) that
    occurs at or after the report is released for the target date. If the release time
    is unknown, we assume the earliest candidate hour on the day AFTER the target date
    (reports for 'yesterday' publish the next morning).
    """
    day_after = target_date + timedelta(days=1)
    candidates = sorted(candidate_hours)
    if report_release_local is None:
        return local_datetime(day_after, candidates[0])
    # Choose first candidate slot at/after release. Search release day then following days.
    search_date = report_release_local.date()
    for offset in range(0, 3):
        d = search_date + timedelta(days=offset)
        for h in candidates:
            slot = local_datetime(d, h)
            if slot >= report_release_local:
                return slot
    # Fallback (should not happen): earliest candidate the day after target.
    return local_datetime(day_after, candidates[0])


def delayed_determination_time(target_date: date, hour: int = 11, minute: int = 0) -> datetime:
    """Delayed-determination cutoff (default 11:00 a.m. ET on the day after target)."""
    return local_datetime(target_date + timedelta(days=1), hour, minute)


def contract_timing(
    target_date: date,
    report_release_local: datetime | None = None,
    last_trading_hm: tuple[int, int] = (23, 59),
    expiration_candidate_hours: tuple[int, ...] = (7, 8),
    delayed_hm: tuple[int, int] = (11, 0),
) -> ContractTiming:
    return ContractTiming(
        target_date=target_date,
        last_trading_local=last_trading_time(target_date, *last_trading_hm),
        normal_expiration_local=normal_expiration_time(
            target_date, report_release_local, tuple(expiration_candidate_hours)
        ),
        delayed_determination_local=delayed_determination_time(target_date, *delayed_hm),
    )


def isoformat_local(dt: datetime) -> str:
    return to_local(dt).isoformat()


def isoformat_utc(dt: datetime) -> str:
    return to_utc(dt).strftime("%Y-%m-%dT%H:%M:%SZ")
