"""Trading-strategy definitions and P&L accounting for NHIGH bucket ladders.

Three research strategies, all driven by the model's out-of-sample integer PMF versus
market quotes available at the forecast issue time (no lookahead):

  1. ``EdgeThresholdFlat``  — buy 1 contract of YES (or NO) whenever the model's
     probability exceeds the ask by more than ``edge_threshold``. The simplest
     value-betting rule; every signal is staked equally.

  2. ``FractionalKelly``    — same signal, but the stake is a fraction of the Kelly
     optimum for a binary payout, capped. Sizes up confident edges, sizes down
     marginal ones; fractional (default 25%) because full Kelly is ruinous under
     model misspecification.

  3. ``TailFade``           — behavioral strategy: buy NO on longshot buckets the
     market prices in [tail_min, tail_max] but the model considers at most half as
     likely. Harvests the favorite-longshot bias documented in prediction markets;
     trades rarely and only sells tails, never buys them.

P&L uses exact settlement (bucket.settles_yes on the settled integer), Kalshi taker
fees, and $1 max payout per contract. This module evaluates strategies on historical
records only; nothing here places orders.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import numpy as np

from ..data.kalshi import Bucket, DayMarket, kalshi_taker_fee


@dataclass
class Trade:
    target_date: date
    bucket_label: str
    side: str               # 'yes' | 'no'
    contracts: int
    entry_price: float      # dollars per contract (0..1)
    model_prob: float       # model P(side wins)
    fee: float
    won: Optional[bool] = None
    pnl: Optional[float] = None

    def settle(self, reported: int, bucket: Bucket) -> None:
        yes_settled = bucket.settles_yes(reported)
        self.won = yes_settled if self.side == "yes" else (not yes_settled)
        gross = (1.0 - self.entry_price) if self.won else (-self.entry_price)
        self.pnl = gross * self.contracts - self.fee


class Strategy:
    name = "abstract"

    def decide(self, market: DayMarket, model_pmf: dict[int, float]) -> list[Trade]:  # pragma: no cover
        raise NotImplementedError


@dataclass
class EdgeThresholdFlat(Strategy):
    edge_threshold: float = 0.08
    contracts: int = 1

    def __post_init__(self):
        self.name = f"edge_flat_{int(self.edge_threshold*100)}c"

    def decide(self, market: DayMarket, model_pmf: dict[int, float]) -> list[Trade]:
        trades = []
        for q in market.quotes:
            p_yes = q.bucket.model_probability(model_pmf)
            if p_yes - q.yes_ask > self.edge_threshold:
                trades.append(Trade(market.target_date, q.bucket.label(), "yes",
                                    self.contracts, q.yes_ask, p_yes,
                                    kalshi_taker_fee(q.yes_ask, self.contracts)))
            elif (1 - p_yes) - q.no_ask > self.edge_threshold:
                trades.append(Trade(market.target_date, q.bucket.label(), "no",
                                    self.contracts, q.no_ask, 1 - p_yes,
                                    kalshi_taker_fee(q.no_ask, self.contracts)))
        return trades


@dataclass
class FractionalKelly(Strategy):
    edge_threshold: float = 0.05
    kelly_fraction: float = 0.25
    bankroll_contracts: int = 100   # contracts corresponding to a full bankroll unit
    max_contracts: int = 10

    def __post_init__(self):
        self.name = f"kelly_{int(self.kelly_fraction*100)}pct"

    def _size(self, p: float, cost: float) -> int:
        # Kelly fraction for a binary contract bought at `cost` paying $1:
        # f* = (p - cost) / (1 - cost); stake fraction of bankroll, translated
        # into contracts and capped.
        if cost >= 1.0 or p <= cost:
            return 0
        f_star = (p - cost) / (1.0 - cost)
        n = int(round(self.kelly_fraction * f_star * self.bankroll_contracts))
        return max(0, min(self.max_contracts, n))

    def decide(self, market: DayMarket, model_pmf: dict[int, float]) -> list[Trade]:
        trades = []
        for q in market.quotes:
            p_yes = q.bucket.model_probability(model_pmf)
            if p_yes - q.yes_ask > self.edge_threshold:
                n = self._size(p_yes, q.yes_ask)
                if n > 0:
                    trades.append(Trade(market.target_date, q.bucket.label(), "yes", n,
                                        q.yes_ask, p_yes, kalshi_taker_fee(q.yes_ask, n)))
            elif (1 - p_yes) - q.no_ask > self.edge_threshold:
                n = self._size(1 - p_yes, q.no_ask)
                if n > 0:
                    trades.append(Trade(market.target_date, q.bucket.label(), "no", n,
                                        q.no_ask, 1 - p_yes, kalshi_taker_fee(q.no_ask, n)))
        return trades


@dataclass
class TailFade(Strategy):
    tail_min: float = 0.05
    tail_max: float = 0.20
    overprice_ratio: float = 2.0    # market must price >= ratio x model probability
    contracts: int = 1

    def __post_init__(self):
        self.name = "tail_fade"

    def decide(self, market: DayMarket, model_pmf: dict[int, float]) -> list[Trade]:
        trades = []
        for q in market.quotes:
            p_yes = q.bucket.model_probability(model_pmf)
            in_tail_band = self.tail_min <= q.mid <= self.tail_max
            overpriced = q.mid >= self.overprice_ratio * max(p_yes, 1e-6)
            if in_tail_band and overpriced:
                trades.append(Trade(market.target_date, q.bucket.label(), "no",
                                    self.contracts, q.no_ask, 1 - p_yes,
                                    kalshi_taker_fee(q.no_ask, self.contracts)))
        return trades


# --------------------------------------------------------------------------------------
# Result aggregation
# --------------------------------------------------------------------------------------
@dataclass
class StrategyResult:
    name: str
    trades: list[Trade] = field(default_factory=list)

    def summary(self) -> dict:
        settled = [t for t in self.trades if t.pnl is not None]
        if not settled:
            return {"strategy": self.name, "n_trades": 0}
        pnl = np.array([t.pnl for t in settled])
        cost = np.array([t.entry_price * t.contracts for t in settled])
        fees = float(sum(t.fee for t in settled))
        wins = sum(1 for t in settled if t.won)
        # per-day cumulative P&L for drawdown
        by_day: dict[date, float] = {}
        for t in settled:
            by_day[t.target_date] = by_day.get(t.target_date, 0.0) + t.pnl
        curve = np.cumsum([by_day[d] for d in sorted(by_day)])
        peak = np.maximum.accumulate(curve)
        max_dd = float(np.max(peak - curve)) if len(curve) else 0.0
        return {
            "strategy": self.name,
            "n_trades": len(settled),
            "n_days_traded": len(by_day),
            "total_contracts": int(sum(t.contracts for t in settled)),
            "win_rate": round(wins / len(settled), 3),
            "gross_pnl": round(float(pnl.sum() + fees), 2),
            "fees": round(fees, 2),
            "net_pnl": round(float(pnl.sum()), 2),
            "net_pnl_per_trade": round(float(pnl.mean()), 4),
            "total_risked": round(float(cost.sum()), 2),
            "roi_on_risked": round(float(pnl.sum() / cost.sum()), 4) if cost.sum() > 0 else None,
            "max_drawdown": round(max_dd, 2),
            "avg_entry_price": round(float(cost.sum() / sum(t.contracts for t in settled)), 3),
            "avg_model_edge": round(float(np.mean([t.model_prob - t.entry_price for t in settled])), 4),
        }
