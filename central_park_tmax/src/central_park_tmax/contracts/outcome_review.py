"""Consistency-review logic that may delay settlement determination to 11:00 a.m. ET.

Two families of triggers per the contract spec:
  1. The reported high is inconsistent with relevant 6-hour or 24-hour METAR highs.
  2. The final reported high is lower than an earlier report.

These functions decide whether a determination should be delayed and record the reason.
They NEVER change a value themselves; they only flag review conditions for the state
machine and settlement outputs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ReviewDecision:
    delayed: bool
    reasons: list[str]

    def as_reason_string(self) -> Optional[str]:
        return "; ".join(self.reasons) if self.reasons else None


def review_conditions(
    reported_max_f: Optional[int],
    metar_6h_max_f: Optional[float],
    metar_24h_max_f: Optional[float],
    earlier_reported_max_f: Optional[int],
    tolerance_f: float = 1.0,
) -> ReviewDecision:
    reasons: list[str] = []
    if reported_max_f is not None:
        if metar_6h_max_f is not None and abs(reported_max_f - metar_6h_max_f) > tolerance_f:
            reasons.append(
                f"reported_high_inconsistent_with_6h_metar_max "
                f"(report={reported_max_f}F, 6h={metar_6h_max_f:.1f}F)"
            )
        if metar_24h_max_f is not None and abs(reported_max_f - metar_24h_max_f) > tolerance_f:
            reasons.append(
                f"reported_high_inconsistent_with_24h_metar_max "
                f"(report={reported_max_f}F, 24h={metar_24h_max_f:.1f}F)"
            )
    if (earlier_reported_max_f is not None and reported_max_f is not None
            and reported_max_f < earlier_reported_max_f):
        reasons.append(
            f"final_reported_high_lower_than_earlier_report "
            f"({reported_max_f}F < {earlier_reported_max_f}F)"
        )
    return ReviewDecision(delayed=len(reasons) > 0, reasons=reasons)
