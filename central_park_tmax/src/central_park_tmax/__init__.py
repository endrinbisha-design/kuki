"""central_park_tmax: station-specific MOS forecasting for KNYC maximum temperature.

Predicts tomorrow's maximum temperature at NY City Central Park (KNYC / USW00094728)
and converts a continuous predictive distribution into calibrated integer-Fahrenheit
report probabilities and exact NHIGH contract-outcome probabilities.

The package deliberately separates five distinct quantities (see README):
  1. latent continuous maximum air temperature,
  2. the maximum published in the NWS Daily Climate Report,
  3. later revised / QC'd climatological values,
  4. the report value available at contract expiration,
  5. the contract payout outcome implied by that report value.
"""

__version__ = "0.1.0"

from .constants import (  # noqa: F401
    STATION,
    TargetProvenance,
    SettlementState,
    FallbackLevel,
)
