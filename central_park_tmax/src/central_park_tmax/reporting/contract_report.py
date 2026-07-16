"""Human-readable rendering of a settlement record."""
from __future__ import annotations

from typing import Mapping


def render_settlement_text(record: Mapping) -> str:
    lines = []
    lines.append(f"Settlement status — {record.get('station')} {record.get('target_date_local')}")
    lines.append(f"  state               : {record.get('settlement_status')}")
    lines.append(f"  last trading (local): {record.get('last_trading_time_local')}")
    lines.append(f"  normal expiration   : {record.get('normal_expiration_time_local')}")
    lines.append(f"  determination delayed: {record.get('determination_delayed')} "
                 f"({record.get('delay_reason')})")
    lines.append(f"  settlement-eligible max: {record.get('settlement_eligible_tmax_f')} °F "
                 f"[{record.get('provenance')}]")
    lv = record.get("later_revision_tmax_f")
    if lv is not None:
        lines.append(f"  later revision (IGNORED for settlement): {lv} °F")
    versions = record.get("report_versions", [])
    if versions:
        lines.append(f"  report versions ({len(versions)}):")
        for i, v in enumerate(versions):
            flag = "<= eligible" if v.get("eligible_at_expiration") else ""
            lines.append(f"      [{i}] {v.get('reported_tmax_f')} °F  status={v.get('status')} "
                         f"issued={v.get('issuance_utc')} {flag}")
    lines.append("  NOTE: settlement is determined by the NWS report, not the weather model.")
    return "\n".join(lines)
