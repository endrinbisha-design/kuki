"""Analyze disagreement among candidate maximum-temperature labels.

Compares, per target date:
  * reconstructed hourly METAR maximum,
  * METAR 6h/24h maximum,
  * GHCN-Daily final maximum,
  * initial NWS Daily Climate Report maximum,
  * revised NWS report maximum,
  * settlement-eligible report value.

Reports disagreement rates so users understand how often the contract label differs from the
final climatological record (a core motivation of this project).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def disagreement_table(rows: list[dict]) -> pd.DataFrame:
    """rows: dicts with any of the label columns below (per target_date)."""
    df = pd.DataFrame(rows)
    return df


def disagreement_rates(df: pd.DataFrame) -> dict:
    pairs = [
        ("initial_nws_max_f", "revised_nws_max_f"),
        ("initial_nws_max_f", "ghcn_max_f"),
        ("settlement_eligible_max_f", "ghcn_max_f"),
        ("settlement_eligible_max_f", "metar_hourly_max_f"),
        ("initial_nws_max_f", "metar_24h_max_f"),
    ]
    out: dict[str, float] = {}
    for a, b in pairs:
        if a in df.columns and b in df.columns:
            sub = df[[a, b]].dropna()
            if not sub.empty:
                disagree = (sub[a].round() != sub[b].round()).mean()
                out[f"disagree_{a}_vs_{b}"] = float(disagree)
                out[f"mean_abs_diff_{a}_vs_{b}"] = float((sub[a] - sub[b]).abs().mean())
    return out
