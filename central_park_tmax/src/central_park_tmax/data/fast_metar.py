"""Low-latency METAR feed (aviationweather.gov) — the settlement-relevant observation.

Discovered 2026-07-28 while investigating why the Kalshi market repeatedly priced a
higher bucket than our observed max supported (Jul 26: market 85-86 @97c vs our 84.02F;
Jul 28: market 79-80 @93c vs our 78.08F). Two independent defects, both fixed here:

1. **Latency.** ``api.weather.gov/stations/{icao}/observations`` lagged the real feed by
   ~1 hour (measured 2026-07-28 18:04Z: api.weather.gov latest = 16:51Z while
   aviationweather.gov already served the 17:51Z METAR). Trading intraday off the lagging
   feed means acting on stale information the market already has.

2. **The hourly-snapshot gap.** Kalshi settles on the NWS Climatological Report, whose
   max comes from the station's *continuous* trace — not the :51 hourly snapshots. The
   METAR **6-hour maximum group** (``1sTTT`` in the RMK section) carries that continuous
   max and is the closest public proxy for the settlement value.

Worked example (2026-07-28 17:51Z KNYC):

    METAR KNYC 281751Z AUTO VRB03KT 10SM CLR 25/22 A2970 RMK AO2 SLP047
          T02500217 10261 20228 58014
                    ^^^^^^ ^^^^^
                    |      6-hour MAX 26.1C = 79.0F  <- settles as 79
                    instantaneous 25.0C = 77.0F      <- what hourly feeds show

The hourly snapshots peaked at 78.08F and would have implied a 78 settlement (the 77-78
bucket, which the market had priced to ~0). The 6-hour group shows the true peak was
79.0F -> 79, i.e. the 79-80 bucket the market held at 93c. The sky group also flipped
SCT020 -> CLR: the sun broke through and the spike happened *between* hourly obs.

SPECI reports (off-schedule specials, e.g. the 1627Z above) are included by this feed and
give extra sampling during rapidly changing conditions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

from ..logging_config import get_logger
from .metar import six_hour_max_f, twentyfour_hour_max_f

log = get_logger(__name__)

AVWX_URL = ("https://aviationweather.gov/api/data/metar"
            "?ids={icao}&format=raw&hours={hours}")

_HEADER_RE = re.compile(r"^(?:METAR|SPECI)\s+(?P<icao>[A-Z]{4})\s+(?P<ddhhmm>\d{6})Z")
_TEMP_RE = re.compile(r"\bT(?P<sign>[01])(?P<t>\d{3})(?P<dsign>[01])(?P<d>\d{3})\b")


@dataclass
class FastObservation:
    issued_utc: datetime
    is_speci: bool
    temp_f: Optional[float]
    six_hour_max_f: Optional[float]
    twentyfour_hour_max_f: Optional[float]
    raw: str


def _parse_ddhhmm(ddhhmm: str, reference: datetime) -> Optional[datetime]:
    """METAR headers carry day-hour-minute only; resolve against a reference month."""
    try:
        day, hour, minute = int(ddhhmm[:2]), int(ddhhmm[2:4]), int(ddhhmm[4:6])
    except ValueError:
        return None
    year, month = reference.year, reference.month
    if day > reference.day + 1:          # report belongs to the previous month
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    try:
        return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_metar_block(text: str, reference_utc: Optional[datetime] = None
                      ) -> list[FastObservation]:
    """Parse the raw multi-line aviationweather.gov response (newest first)."""
    ref = reference_utc or datetime.now(timezone.utc)
    out: list[FastObservation] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        h = _HEADER_RE.match(line)
        if not h:
            continue
        issued = _parse_ddhhmm(h.group("ddhhmm"), ref)
        if issued is None:
            continue
        temp_f = None
        t = _TEMP_RE.search(line)
        if t:
            c = int(t.group("t")) / 10.0
            if t.group("sign") == "1":
                c = -c
            temp_f = c * 9 / 5 + 32
        out.append(FastObservation(
            issued_utc=issued, is_speci=line.startswith("SPECI"), temp_f=temp_f,
            six_hour_max_f=six_hour_max_f(line),
            twentyfour_hour_max_f=twentyfour_hour_max_f(line), raw=line))
    return sorted(out, key=lambda o: o.issued_utc, reverse=True)


def fetch_fast_metars(http, icao: str, hours: int = 6,
                      reference_utc: Optional[datetime] = None) -> list[FastObservation]:
    """Recent METAR/SPECI reports for a station, newest first. Empty list on failure."""
    try:
        text = http.get_text(AVWX_URL.format(icao=icao, hours=hours), use_cache=False)
        return parse_metar_block(text, reference_utc)
    except Exception as exc:  # noqa: BLE001
        log.warning("fast METAR fetch failed for %s: %s", icao, str(exc)[:120])
        return []


@dataclass
class SettlementMax:
    best_max_f: Optional[float]
    source: str
    hourly_max_f: Optional[float]
    six_hour_max_f: Optional[float]
    latest_issued_utc: Optional[datetime]
    gap_f: float = 0.0        # how much the 6-hour group exceeds the hourly snapshots
    # Instantaneous temperatures for the local day in CHRONOLOGICAL order. Consumers use
    # the tail of this to tell "the max is banked" from "still climbing" — the hourly
    # remaining-rise climatology cannot distinguish the two on its own.
    recent_temps_f: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"settlement_max_f": self.best_max_f,
                "settlement_max_source": self.source,
                "hourly_snapshot_max_f": self.hourly_max_f,
                "metar_6h_max_f": self.six_hour_max_f,
                "snapshot_gap_f": round(self.gap_f, 2),
                "recent_temps_f": self.recent_temps_f[-6:],
                "latest_ob_utc": self.latest_issued_utc.isoformat()
                if self.latest_issued_utc else None}


def settlement_max_so_far(obs: list[FastObservation], target_date: date,
                          utc_offset_hours: int) -> SettlementMax:
    """Best available estimate of the settlement max so far for a local calendar day.

    Takes the larger of (a) the max instantaneous temperature across reports and (b) the
    max 6-hour maximum group — the latter captures spikes between hourly reports and is
    what the CLI settlement value is derived from.
    """
    todays = [o for o in obs
              if (o.issued_utc.timestamp() + utc_offset_hours * 3600) // 86400
              == (datetime(target_date.year, target_date.month, target_date.day,
                           tzinfo=timezone.utc).timestamp()) // 86400]
    if not todays:
        return SettlementMax(None, "none", None, None, None)
    hourly = [o.temp_f for o in todays if o.temp_f is not None]
    six = [o.six_hour_max_f for o in todays if o.six_hour_max_f is not None]
    h_max = max(hourly) if hourly else None
    s_max = max(six) if six else None
    # ``obs`` (and therefore ``todays``) is newest-first; the trace wants chronological.
    trace = [o.temp_f for o in reversed(todays) if o.temp_f is not None]
    if s_max is not None and (h_max is None or s_max > h_max):
        return SettlementMax(s_max, "metar_6h_group", h_max, s_max,
                             todays[0].issued_utc, (s_max - h_max) if h_max else 0.0,
                             recent_temps_f=trace)
    return SettlementMax(h_max, "hourly_snapshot", h_max, s_max, todays[0].issued_utc, 0.0,
                         recent_temps_f=trace)
