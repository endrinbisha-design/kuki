"""Parser for the NWS Daily Climate Report (CLI product) for Central Park.

The authoritative contract underlying is the ``Maximum`` value in the ``Temperature``
section, ``Yesterday`` column of this product. This module parses the raw fixed-width
text product, extracts the target date, the published maximum, the observation time, the
issuance timestamp, and the report status (preliminary / corrected / final indicator).

Parsing is intentionally strict: if the expected fields cannot be located, a
``ReportParseError`` is raised rather than guessing a value. Any deviation from the known
layout is logged so format drift is caught.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from ..logging_config import get_logger
from ..time_utils import to_utc
from . import ReportParseError

log = get_logger(__name__)

# US timezone abbreviations that can appear in the product header, mapped to fixed offsets.
# NWS reports include LST/LDT abbreviations; we map the eastern ones used for KNYC.
_TZ_ABBR = {
    "EST": ZoneInfo("America/New_York"),
    "EDT": ZoneInfo("America/New_York"),
}

_MONTHS = {m.upper(): i for i, m in enumerate(
    ["", "January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=0)}

# e.g. "605 AM EDT SUN JUL 16 2026"
_HEADER_TS_RE = re.compile(
    r"(?P<time>\d{1,4})\s+(?P<ampm>AM|PM)\s+(?P<tz>[A-Z]{3,4})\s+"
    r"[A-Z]{3}\s+(?P<mon>[A-Z]{3})\s+(?P<day>\d{1,2})\s+(?P<year>\d{4})"
)

# e.g. "...THE CENTRAL PARK NY CLIMATE SUMMARY FOR JULY 15 2026..."
_SUMMARY_DATE_RE = re.compile(
    r"CLIMATE\s+SUMMARY\s+FOR\s+(?P<mon>[A-Z]+)\s+(?P<day>\d{1,2})\s+(?P<year>\d{4})",
    re.IGNORECASE,
)

# Correction / status markers.
_CORRECTED_RE = re.compile(r"\bCORRECT(?:ED|ION)\b", re.IGNORECASE)
# Intraday preliminary marker, e.g. "VALID TODAY AS OF 0400 PM LOCAL TIME."
# These same-day issuances report the maximum SO FAR (a lower bound on the final value),
# and are distinct from the next-morning final report (which summarizes YESTERDAY).
_VALID_AS_OF_RE = re.compile(
    r"VALID\s+TODAY\s+AS\s+OF\s+(?P<time>\d{3,4})\s*(?P<ampm>AM|PM)\s+LOCAL\s+TIME",
    re.IGNORECASE,
)
# Whether the temperature block is labeled TODAY (intraday) vs YESTERDAY (final).
_TODAY_ROW_RE = re.compile(r"TEMPERATURE\s*\(F\)\s*\n\s*TODAY", re.IGNORECASE)
_MON3 = {m.upper()[:3]: i for i, m in enumerate(
    ["", "January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=0)}


@dataclass
class ClimateReport:
    """Parsed representation of a single retrieved CLI report version."""
    target_date: date
    reported_max_f: int
    max_time_lst: Optional[str]
    issuance_local: Optional[datetime]
    issuance_utc: Optional[datetime]
    status: str                       # intraday_preliminary | preliminary | corrected | unknown
    issuing_office: Optional[str]
    product_id: Optional[str]
    raw_text: str
    is_intraday_preliminary: bool = False   # same-day "VALID TODAY AS OF ..." issuance
    valid_as_of_lst: Optional[str] = None   # the "as of" time for intraday reports
    # optional extras parsed when present:
    reported_min_f: Optional[int] = None
    parse_warnings: list[str] = field(default_factory=list)

    def to_record(self, retrieved_at_utc: datetime, source: str) -> dict:
        from .storage import sha256_text
        return {
            "target_date": self.target_date.isoformat(),
            "reported_max_f": self.reported_max_f,
            "reported_min_f": self.reported_min_f,
            "max_time_lst": self.max_time_lst,
            "issuance_local": self.issuance_local.isoformat() if self.issuance_local else None,
            "issuance_utc": self.issuance_utc.strftime("%Y-%m-%dT%H:%M:%SZ") if self.issuance_utc else None,
            "status": self.status,
            "is_intraday_preliminary": self.is_intraday_preliminary,
            "valid_as_of_lst": self.valid_as_of_lst,
            "issuing_office": self.issuing_office,
            "product_id": self.product_id,
            "retrieved_at_utc": retrieved_at_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": source,
            "content_sha256": sha256_text(self.raw_text),
            "raw_text": self.raw_text,
            "parse_warnings": self.parse_warnings,
        }


def _parse_header_timestamp(text: str, warnings: list[str]) -> tuple[Optional[datetime], Optional[datetime]]:
    m = _HEADER_TS_RE.search(text)
    if not m:
        warnings.append("header timestamp not found")
        return None, None
    raw_time = m.group("time")
    # raw_time like "605" -> 6:05, "1005" -> 10:05, "12" -> 12:00
    raw_time = raw_time.zfill(3)
    minute = int(raw_time[-2:])
    hour = int(raw_time[:-2])
    ampm = m.group("ampm")
    if ampm == "PM" and hour != 12:
        hour += 12
    if ampm == "AM" and hour == 12:
        hour = 0
    mon = _MON3.get(m.group("mon").upper())
    if not mon:
        warnings.append(f"unknown header month {m.group('mon')!r}")
        return None, None
    tz = _TZ_ABBR.get(m.group("tz").upper(), ZoneInfo("America/New_York"))
    local = datetime(int(m.group("year")), mon, int(m.group("day")), hour, minute, tzinfo=tz)
    return local, to_utc(local)


def _parse_target_date(text: str, warnings: list[str]) -> date:
    m = _SUMMARY_DATE_RE.search(text)
    if not m:
        raise ReportParseError(
            "Could not locate 'CLIMATE SUMMARY FOR <MONTH DAY YEAR>' line; "
            "report layout may have changed."
        )
    mon_name = m.group("mon").upper()
    mon = _MONTHS.get(mon_name) or _MON3.get(mon_name[:3])
    if not mon:
        raise ReportParseError(f"Unrecognized month in summary date: {mon_name!r}")
    return date(int(m.group("year")), mon, int(m.group("day")))


def _parse_temperature_block(text: str, warnings: list[str]) -> tuple[int, Optional[str], Optional[int]]:
    """Extract the YESTERDAY MAXIMUM (and MINIMUM) from the TEMPERATURE section.

    The section looks like:
        TEMPERATURE (F)
         YESTERDAY
          MAXIMUM         88   313 PM ...
          MINIMUM         72   530 AM ...
    We anchor on the TEMPERATURE header, then read the first MAXIMUM row after it.
    """
    upper = text.upper()
    t_idx = upper.find("TEMPERATURE")
    if t_idx < 0:
        raise ReportParseError("No TEMPERATURE section found in report.")
    section = text[t_idx:]
    # Stop at the next major section header if present to avoid capturing later blocks.
    for stop in ("PRECIPITATION", "SNOWFALL", "DEGREE DAYS", "WIND"):
        s_idx = section.upper().find(stop)
        if s_idx > 0:
            section = section[:s_idx]
            break

    max_val, max_time = _find_row_value(section, "MAXIMUM")
    if max_val is None:
        raise ReportParseError("Could not parse MAXIMUM row in TEMPERATURE section.")
    min_val, _ = _find_row_value(section, "MINIMUM")
    return max_val, max_time, min_val


def _find_row_value(section: str, label: str) -> tuple[Optional[int], Optional[str]]:
    """Find a labeled row like 'MAXIMUM  88   313 PM' -> (88, '313 PM')."""
    row_re = re.compile(
        rf"^\s*{label}\s+(?P<val>-?\d{{1,3}})(?:\s+(?P<time>\d{{1,4}}\s*(?:AM|PM)))?",
        re.IGNORECASE | re.MULTILINE,
    )
    m = row_re.search(section)
    if not m:
        return None, None
    val = int(m.group("val"))
    tstr = m.group("time")
    time_norm = re.sub(r"\s+", " ", tstr).strip() if tstr else None
    return val, time_norm


def _parse_product_id(text: str) -> Optional[str]:
    # First non-empty non-numeric token line is usually the AWIPS id (e.g. CLINYC).
    for line in text.splitlines()[:12]:
        s = line.strip()
        if re.fullmatch(r"[A-Z]{3,6}\d?", s):
            if s.startswith("CLI") or s in {"CDUS41"}:
                if s.startswith("CLI"):
                    return s
    m = re.search(r"\b(CLI[A-Z]{2,3})\b", text)
    return m.group(1) if m else None


def _parse_issuing_office(text: str) -> Optional[str]:
    m = re.search(r"NATIONAL WEATHER SERVICE\s+([A-Z ,]+?)\s*$", text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"\bK([A-Z]{3})\b", text)
    return m2.group(1) if m2 else None


def parse_climate_report(raw_text: str, retrieved_at_utc: Optional[datetime] = None,
                         source: str = "unknown") -> ClimateReport:
    """Parse a raw CLI product into a validated ClimateReport. Raises on failure."""
    if not raw_text or "CLIMATE" not in raw_text.upper():
        raise ReportParseError("Text does not look like a CLI climate report (no 'CLIMATE' token).")
    warnings: list[str] = []
    target = _parse_target_date(raw_text, warnings)
    max_f, max_time, min_f = _parse_temperature_block(raw_text, warnings)
    issuance_local, issuance_utc = _parse_header_timestamp(raw_text, warnings)
    product_id = _parse_product_id(raw_text)
    office = _parse_issuing_office(raw_text)

    # Status: corrections win; otherwise an intraday "VALID TODAY AS OF ..." same-day
    # issuance (max SO FAR) is distinguished from the next-morning final report.
    valid_as_of = _VALID_AS_OF_RE.search(raw_text)
    is_intraday = bool(valid_as_of) or bool(_TODAY_ROW_RE.search(raw_text))
    valid_as_of_lst = (re.sub(r"\s+", " ", f"{valid_as_of.group('time')} {valid_as_of.group('ampm')}").strip()
                       if valid_as_of else None)
    if _CORRECTED_RE.search(raw_text):
        status = "corrected"
    elif is_intraday:
        status = "intraday_preliminary"
    else:
        status = "preliminary"

    from ..constants import MIN_PLAUSIBLE_TMAX_F, MAX_PLAUSIBLE_TMAX_F
    if not (MIN_PLAUSIBLE_TMAX_F <= max_f <= MAX_PLAUSIBLE_TMAX_F):
        raise ReportParseError(f"Parsed maximum {max_f}F outside plausible bounds; likely mis-parse.")

    for w in warnings:
        log.warning("CLI parse warning (%s target=%s): %s", source, target, w)

    return ClimateReport(
        target_date=target,
        reported_max_f=max_f,
        max_time_lst=max_time,
        issuance_local=issuance_local,
        issuance_utc=issuance_utc,
        status=status,
        issuing_office=office,
        product_id=product_id,
        raw_text=raw_text,
        is_intraday_preliminary=is_intraday,
        valid_as_of_lst=valid_as_of_lst,
        reported_min_f=min_f,
        parse_warnings=warnings,
    )
