"""Configurable reporting-convention layer: latent continuous max -> integer report value.

IMPORTANT DOCUMENTATION NOTE
----------------------------
The NWS Daily Climate Report publishes the maximum in whole degrees Fahrenheit. The exact
convention by which the integer is derived is NOT assumed here to be naive rounding. ASOS
computes temperatures internally and the CLI value is generally the maximum of the reported
(already rounded to whole degrees F) hourly/METAR observations, i.e. a *max of rounded*
values rather than a round of the true continuous maximum. Both behaviors are supported and
the choice is configurable and empirically evaluated (see README, section "Reporting
convention"). We default to ``round_half_up`` as a documented, reproducible baseline and
provide ``max_of_rounded`` for the ASOS-consistent interpretation when hourly data exist.

Supported methods:
  * round_half_up   : floor(x + 0.5)         (default documented convention)
  * round_half_even : banker's rounding
  * truncate        : floor(x)               (drop fractional degrees)
  * ceil            : ceil(x)
  * max_of_rounded  : max over provided already-rounded hourly values (needs hourly input)
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

_METHODS = {"round_half_up", "round_half_even", "truncate", "ceil", "max_of_rounded"}


def apply_reporting_convention(
    latent_max_f: float,
    method: str = "round_half_up",
    hourly_rounded_f: Optional[Iterable[float]] = None,
) -> int:
    """Map a latent continuous maximum (F) to the integer the NWS report would publish."""
    if method not in _METHODS:
        raise ValueError(f"Unknown reporting convention method {method!r}; valid: {sorted(_METHODS)}")
    if method == "round_half_up":
        return int(math.floor(latent_max_f + 0.5))
    if method == "round_half_even":
        return int(round(latent_max_f))
    if method == "truncate":
        return int(math.floor(latent_max_f))
    if method == "ceil":
        return int(math.ceil(latent_max_f))
    if method == "max_of_rounded":
        if hourly_rounded_f is None:
            # Fall back to rounding the latent max if no hourly detail is available.
            return int(math.floor(latent_max_f + 0.5))
        vals = [int(math.floor(v + 0.5)) for v in hourly_rounded_f]
        if not vals:
            return int(math.floor(latent_max_f + 0.5))
        return max(vals)
    raise AssertionError("unreachable")


def convention_version(method: str) -> str:
    return f"nws_cli_v1:{method}"
