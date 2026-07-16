"""Exact contract-outcome probabilities from an integer-report probability mass function.

Given a PMF over integer reported temperatures (dict {int: prob} summing to 1), these
functions compute exact NHIGH probabilities by summing the mass of integers that satisfy
each boundary rule. Strict vs. inclusive boundaries are honored exactly (see nhigh_rules).
"""
from __future__ import annotations

from typing import Mapping

from . import nhigh_rules as rules

TOL = 1e-6


def _validate_pmf(pmf: Mapping[int, float]) -> None:
    total = sum(pmf.values())
    if abs(total - 1.0) > 1e-3:
        raise ValueError(f"Integer PMF must sum to 1 (got {total:.6f}).")


def probability_greater_than(pmf: Mapping[int, float], k: int) -> float:
    return float(sum(p for v, p in pmf.items() if rules.satisfies_greater_than(int(v), k)))


def probability_greater_than_or_equal(pmf: Mapping[int, float], k: int) -> float:
    return float(sum(p for v, p in pmf.items() if rules.satisfies_greater_than_or_equal(int(v), k)))


def probability_less_than(pmf: Mapping[int, float], k: int) -> float:
    return float(sum(p for v, p in pmf.items() if rules.satisfies_less_than(int(v), k)))


def probability_less_than_or_equal(pmf: Mapping[int, float], k: int) -> float:
    return float(sum(p for v, p in pmf.items() if rules.satisfies_less_than_or_equal(int(v), k)))


def probability_between_inclusive(pmf: Mapping[int, float], lower: int, upper: int) -> float:
    return float(sum(p for v, p in pmf.items()
                     if rules.satisfies_between_inclusive(int(v), lower, upper)))


def probability_exactly(pmf: Mapping[int, float], k: int) -> float:
    return float(sum(p for v, p in pmf.items() if rules.satisfies_exactly(int(v), k)))


def contract_probability_report(pmf: Mapping[int, float], thresholds: dict) -> dict[str, float]:
    """Build a dict of common contract probabilities from configured thresholds."""
    _validate_pmf(pmf)
    out: dict[str, float] = {}
    for k in thresholds.get("greater_than", []):
        out[f"greater_than_{k}"] = probability_greater_than(pmf, k)
        out[f"greater_than_or_equal_{k}"] = probability_greater_than_or_equal(pmf, k)
    for k in thresholds.get("less_than", []):
        out[f"less_than_{k}"] = probability_less_than(pmf, k)
        out[f"less_than_or_equal_{k}"] = probability_less_than_or_equal(pmf, k)
    for pair in thresholds.get("ranges_inclusive", []):
        a, b = int(pair[0]), int(pair[1])
        out[f"between_{a}_and_{b}_inclusive"] = probability_between_inclusive(pmf, a, b)
    return out
