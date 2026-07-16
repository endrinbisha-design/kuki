"""Spatial-gradient features across Central Park and surrounding points.

Gradients (e.g. Central Park minus JFK forecast temperature, inland minus coastal) are
strong signals for marine-air penetration, sea-breeze, and frontal position. This module
consumes per-location daily maxima (and dew points where available) from a ForecastRun and
produces the configured gradient pairs plus a marine-air-penetration indicator.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np


def gradient_features(run, target_date: date, locations) -> dict:
    """Compute configured a_minus_b forecast-temperature (and dewpoint) gradients."""
    out: dict[str, float] = {}
    tmax = {p.key: run.daily_max_f(p.key, target_date) for p in locations.all_points()}
    for pair in locations.gradient_pairs:
        a, b = tmax.get(pair.a), tmax.get(pair.b)
        if a is not None and b is not None:
            out[f"grad_{pair.name}_tmax_f"] = float(a - b)

    # Marine-air-penetration indicator: coastal points cooler than inland by a wide margin.
    coastal = [tmax[p.key] for p in locations.all_points()
               if p.role in ("marine", "coastal", "coastal_airport") and tmax.get(p.key) is not None]
    inland = [tmax[p.key] for p in locations.all_points()
              if p.role in ("inland", "inland_airport") and tmax.get(p.key) is not None]
    if coastal and inland:
        out["marine_penetration_f"] = float(np.mean(inland) - np.mean(coastal))
    # Central Park position within the coastal-inland gradient.
    cp = tmax.get(locations.primary.key)
    if cp is not None and coastal and inland:
        span = np.mean(inland) - np.mean(coastal)
        if abs(span) > 1e-6:
            out["cp_coastal_inland_position"] = float((cp - np.mean(coastal)) / span)
    return out


def neighborhood_temperature_stats(run, target_date: date, keys: list[str]) -> dict:
    vals = [run.daily_max_f(k, target_date) for k in keys]
    vals = [v for v in vals if v is not None]
    if not vals:
        return {}
    return {
        "neigh_tmax_mean_f": float(np.mean(vals)),
        "neigh_tmax_min_f": float(np.min(vals)),
        "neigh_tmax_max_f": float(np.max(vals)),
        "neigh_tmax_std_f": float(np.std(vals)),
        "neigh_tmax_range_f": float(np.max(vals) - np.min(vals)),
    }
