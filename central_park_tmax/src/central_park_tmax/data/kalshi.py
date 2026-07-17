"""Kalshi market data for NYC high-temperature contracts (KXHIGHNY / legacy HIGHNY).

Two market-data sources behind one interface:

  * ``KalshiMarketDataSource`` — REAL data from the public Kalshi trade API
    (settled markets + price candlesticks). No credentials are needed for public
    market-data routes. Raises ``MarketDataUnavailable`` when the host is
    unreachable (some sandboxes block it); nothing is fabricated.

  * ``SimulatedMarketDataSource`` — a documented, clearly-labeled SIMULATED market
    used when real prices are unreachable: a bucket ladder centered on the same
    public NBM guidance the model uses (available at issue time — no lookahead),
    priced by a noisy-but-reasonable pseudo-market maker. Strategy results against
    it measure *behavior against an imperfect market*, never real profitability.

Bucket semantics follow Kalshi temperature ladders and our exact NHIGH rules:
low tail  = "K or below"  (reported <= K, inclusive),
middle    = "A to B"      (A <= reported <= B, both endpoints inclusive),
high tail = "K or above"  (reported >= K, inclusive).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import numpy as np

from ..contracts import nhigh_rules as rules
from ..logging_config import get_logger
from . import DataSourceError
from .storage import HttpClient

log = get_logger(__name__)

KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"
NYC_HIGH_SERIES = "KXHIGHNY"


class MarketDataUnavailable(DataSourceError):
    """Real Kalshi market data cannot be retrieved in this environment."""


# --------------------------------------------------------------------------------------
# Contract bucket model
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Bucket:
    """One market in the daily ladder. kind: 'le' (<=K), 'between' (A..B incl), 'ge' (>=K)."""
    kind: str
    low: int    # for 'le': K; for 'between': A; for 'ge': K
    high: int   # for 'le': K; for 'between': B; for 'ge': K

    def settles_yes(self, reported: int) -> bool:
        if self.kind == "le":
            return rules.satisfies_less_than_or_equal(reported, self.high)
        if self.kind == "ge":
            return rules.satisfies_greater_than_or_equal(reported, self.low)
        return rules.satisfies_between_inclusive(reported, self.low, self.high)

    def model_probability(self, pmf: dict[int, float]) -> float:
        return float(sum(p for k, p in pmf.items() if self.settles_yes(int(k))))

    def label(self) -> str:
        if self.kind == "le":
            return f"{self.high}F_or_below"
        if self.kind == "ge":
            return f"{self.low}F_or_above"
        return f"{self.low}_to_{self.high}F"


def standard_ladder(center: int, n_middle: int = 4, width: int = 2) -> list[Bucket]:
    """Kalshi-style ladder: low tail, ``n_middle`` inclusive 2-degree bands, high tail.

    ``center`` must come from information available at issue time (e.g. the rounded
    NBM baseline) — never from the outcome.
    """
    first_low = center - (n_middle * width) // 2 + 1
    buckets = [Bucket("le", first_low - 1, first_low - 1)]
    lo = first_low
    for _ in range(n_middle):
        buckets.append(Bucket("between", lo, lo + width - 1))
        lo += width
    buckets.append(Bucket("ge", lo, lo))
    return buckets


@dataclass
class MarketQuote:
    bucket: Bucket
    yes_ask: float          # cost to buy YES, in dollars (0..1)
    no_ask: float           # cost to buy NO, in dollars (0..1)
    mid: float              # midpoint probability implied by the market


@dataclass
class DayMarket:
    target_date: date
    buckets: list[Bucket]
    quotes: list[MarketQuote]
    source: str             # 'kalshi' | 'simulated'


# --------------------------------------------------------------------------------------
# Real Kalshi client (public market-data routes)
# --------------------------------------------------------------------------------------
class KalshiMarketDataSource:
    """Fetch settled KXHIGHNY markets and entry prices from the public Kalshi API.

    Public GET routes used (no auth):
      /markets?series_ticker=KXHIGHNY&status=settled&...   -> strikes + results
      /series/{series}/markets/{ticker}/candlesticks       -> historical prices

    Entry prices are taken from the candle whose window covers the requested
    issue timestamp, so backtests never use prices from after the decision time.
    """

    def __init__(self, http: HttpClient, series: str = NYC_HIGH_SERIES):
        self.http = http
        self.series = series

    def day_market(self, target_date: date, issue_ts_utc) -> DayMarket:
        try:
            markets = self._settled_markets_for(target_date)
        except Exception as exc:  # noqa: BLE001
            raise MarketDataUnavailable(
                f"Kalshi API unreachable or returned no data ({exc}). In restricted "
                "environments run the strategy backtest with --simulated-market."
            ) from exc
        quotes = []
        buckets = []
        for m in markets:
            bucket = self._bucket_from_market(m)
            if bucket is None:
                continue
            price = self._entry_price(m["ticker"], issue_ts_utc)
            if price is None:
                continue
            buckets.append(bucket)
            quotes.append(MarketQuote(bucket=bucket, yes_ask=price,
                                      no_ask=round(1.0 - price + 0.01, 4), mid=price))
        if not quotes:
            raise MarketDataUnavailable(f"No priced Kalshi markets for {target_date}.")
        return DayMarket(target_date=target_date, buckets=buckets, quotes=quotes,
                        source="kalshi")

    def _settled_markets_for(self, target_date: date) -> list[dict]:
        # Kalshi day tickers look like KXHIGHNY-25JAN15-...
        tag = target_date.strftime("%y%b%d").upper()
        url = (f"{KALSHI_API_BASE}/markets?series_ticker={self.series}"
               f"&status=settled&limit=100")
        data = self.http.get_json(url, use_cache=True)
        return [m for m in data.get("markets", []) if tag in m.get("ticker", "")]

    @staticmethod
    def _bucket_from_market(m: dict) -> Optional[Bucket]:
        st = m.get("strike_type")
        if st == "between":
            return Bucket("between", int(math.ceil(float(m["floor_strike"]))),
                          int(math.floor(float(m["cap_strike"]))))
        if st in ("less", "less_or_equal"):
            k = float(m["cap_strike"])
            return Bucket("le", int(math.floor(k)), int(math.floor(k)))
        if st in ("greater", "greater_or_equal"):
            k = float(m["floor_strike"])
            return Bucket("ge", int(math.ceil(k)), int(math.ceil(k)))
        return None

    def _entry_price(self, ticker: str, issue_ts_utc) -> Optional[float]:
        import datetime as _dt
        start = int(issue_ts_utc.timestamp()) - 6 * 3600
        end = int(issue_ts_utc.timestamp())
        url = (f"{KALSHI_API_BASE}/series/{self.series}/markets/{ticker}/candlesticks"
               f"?start_ts={start}&end_ts={end}&period_interval=60")
        data = self.http.get_json(url, use_cache=True)
        candles = data.get("candlesticks", [])
        if not candles:
            return None
        last = candles[-1]
        price_c = (last.get("yes_ask", {}) or {}).get("close") or (last.get("price", {}) or {}).get("close")
        return float(price_c) / 100.0 if price_c is not None else None


# --------------------------------------------------------------------------------------
# Simulated market (documented stand-in; NEVER real Kalshi prices)
# --------------------------------------------------------------------------------------
@dataclass
class SimulatedMarketDataSource:
    """Pseudo-market maker for strategy research when Kalshi is unreachable.

    The market prices each bucket from a Normal centered on the same NBM baseline the
    model sees (plus its own daily error and small bias), then adds pricing noise and a
    bid/ask spread. Its daily error draws are seeded per date -> reproducible. This
    represents a *reasonably efficient but imperfect* counterparty anchored on public
    guidance; results against it are research diagnostics, not profit claims.
    """
    market_sigma: float = 2.4       # market's own forecast-error stdev (F)
    daily_error_sigma: float = 1.2  # day-specific market mispricing (F)
    price_noise: float = 0.015      # per-bucket multiplicative pricing noise
    half_spread: float = 0.015      # half bid/ask spread in dollars
    bias_f: float = 0.3             # slight market warm bias

    def day_market(self, target_date: date, baseline_tmax_f: float,
                   ladder: Optional[list[Bucket]] = None) -> DayMarket:
        seed = int(target_date.strftime("%Y%m%d"))
        rng = np.random.default_rng(seed)
        center = int(round(baseline_tmax_f))
        buckets = ladder or standard_ladder(center)
        mu = baseline_tmax_f + self.bias_f + rng.normal(0, self.daily_error_sigma)

        from scipy.stats import norm
        probs = []
        for b in buckets:
            if b.kind == "le":
                p = norm.cdf(b.high + 0.5, mu, self.market_sigma)
            elif b.kind == "ge":
                p = 1 - norm.cdf(b.low - 0.5, mu, self.market_sigma)
            else:
                p = (norm.cdf(b.high + 0.5, mu, self.market_sigma)
                     - norm.cdf(b.low - 0.5, mu, self.market_sigma))
            p = max(0.005, float(p) * (1 + rng.normal(0, self.price_noise)))
            probs.append(p)
        total = sum(probs)
        probs = [p / total for p in probs]

        quotes = [
            MarketQuote(
                bucket=b,
                yes_ask=round(min(0.99, max(0.01, p + self.half_spread)), 4),
                no_ask=round(min(0.99, max(0.01, (1 - p) + self.half_spread)), 4),
                mid=round(p, 4),
            )
            for b, p in zip(buckets, probs)
        ]
        return DayMarket(target_date=target_date, buckets=buckets, quotes=quotes,
                        source="simulated")


def kalshi_taker_fee(price: float, contracts: int = 1) -> float:
    """Kalshi trading fee: ceil(0.07 * C * P * (1-P)) cents, converted to dollars."""
    cents = math.ceil(7.0 * contracts * price * (1.0 - price))
    return cents / 100.0
