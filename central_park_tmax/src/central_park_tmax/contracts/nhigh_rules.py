"""Exact NHIGH payout semantics on an INTEGER reported temperature.

Boundary semantics (do NOT relax these):
  * greater_than(K)          : reported >  K   (strict)
  * greater_than_or_equal(K) : reported >= K
  * less_than(K)             : reported <  K   (strict)
  * less_than_or_equal(K)    : reported <= K
  * between_inclusive(A, B)  : A <= reported <= B  (both endpoints included)
  * exactly(K)               : reported == K

Worked examples encoded in tests:
  * 90 does NOT satisfy greater_than(90).
  * 90 DOES satisfy between_inclusive(88, 90).
  * 90 does NOT satisfy less_than(90).
"""
from __future__ import annotations

CONTRACT_RULE_VERSION = "nhigh_v1"


def satisfies_greater_than(reported: int, k: int) -> bool:
    return reported > k


def satisfies_greater_than_or_equal(reported: int, k: int) -> bool:
    return reported >= k


def satisfies_less_than(reported: int, k: int) -> bool:
    return reported < k


def satisfies_less_than_or_equal(reported: int, k: int) -> bool:
    return reported <= k


def satisfies_between_inclusive(reported: int, lower: int, upper: int) -> bool:
    if lower > upper:
        lower, upper = upper, lower
    return lower <= reported <= upper


def satisfies_exactly(reported: int, k: int) -> bool:
    return reported == k
