"""Concise human-readable rendering of a prediction record."""
from __future__ import annotations

from typing import Mapping


def render_forecast_text(record: Mapping) -> str:
    lines = []
    lines.append(f"Central Park (KNYC) maximum-temperature forecast")
    lines.append(f"  target date (local) : {record.get('target_date_local')}")
    lines.append(f"  vintage / issued    : {record.get('vintage')} @ {record.get('forecast_issued_at_local')}")
    if record.get("is_synthetic"):
        lines.append("  ** SYNTHETIC DATA — not a real forecast **")
    lines.append(f"  baseline ({record.get('baseline_model')}) : {record.get('baseline_tmax_f')} °F")
    lines.append(f"  bias correction     : {record.get('predicted_bias_correction_f')} °F")
    lines.append(f"  predicted max       : {record.get('predicted_continuous_tmax_f')} °F "
                 f"({record.get('predicted_continuous_tmax_c')} °C)")
    if record.get("observed_max_so_far_f") is not None:
        lines.append(f"  observed so far     : {record.get('observed_max_so_far_f')} °F (hard lower bound)")
    if record.get("interval_80_f"):
        lo, hi = record["interval_80_f"]
        lines.append(f"  80% interval        : [{lo}, {hi}] °F")
    lines.append(f"  fallback level      : {record.get('fallback_level')}  model: {record.get('model_name')}")
    if record.get("regime"):
        adv = "" if record.get("regime_weighting_enabled") else " (advisory)"
        lines.append(f"  regime{adv:11}: {record['regime']} -> weighted "
                     f"{record.get('regime_weighted_tmax_f')} °F | {record.get('regime_rationale')}")

    if record.get("sea_breeze_risk") is not None:
        flag = " ** ELEVATED **" if record.get("sea_breeze_flagged") else ""
        lines.append(f"  sea-breeze risk     : {record['sea_breeze_risk']*100:.0f}%{flag} "
                     f"| {record.get('sea_breeze_rationale')}")
    if record.get("sea_breeze_underway"):
        lines.append(f"  MARINE INTRUSION UNDERWAY: {record.get('sea_breeze_divergence_rationale')}")

    if record.get("hot_day_calibration_applies"):
        lines.append(f"  hot-day tail        : {record.get('hot_day_rationale')}")

    if record.get("strategy"):
        lines.append(f"  STRATEGY            : {record['strategy']} "
                     f"[{record.get('strategy_confidence')}] "
                     f"regime={record.get('strategy_regime')} lean={record.get('strategy_lean')}")
        lines.append(f"      why: {record.get('strategy_rationale')}")
        for a in (record.get("strategy_actions") or [])[:3]:
            lines.append(f"      - {a}")

    pmf = record.get("integer_report_probabilities", {})
    if pmf:
        top = sorted(pmf.items(), key=lambda kv: kv[1], reverse=True)[:5]
        lines.append("  most-likely reported integers:")
        for k, v in top:
            lines.append(f"      {k} °F : {v*100:5.1f}%")

    cp = record.get("contract_probabilities", {})
    if cp:
        lines.append("  contract probabilities (selected):")
        for key in ("greater_than_90", "greater_than_or_equal_90", "less_than_90",
                    "between_88_and_90_inclusive", "exactly_90"):
            if key in cp:
                lines.append(f"      P[{key}] = {cp[key]*100:5.1f}%")
    lines.append(f"  sources used: {record.get('data_sources_used')}  missing: {record.get('missing_sources')}")
    lines.append("  NOTE: forecast only — not an official NWS report or contract settlement.")
    return "\n".join(lines)
