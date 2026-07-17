from datetime import date

import numpy as np

from central_park_tmax.contracts.strategies import (EdgeThresholdFlat, FractionalKelly,
                                                    StrategyResult, TailFade, Trade)
from central_park_tmax.data.kalshi import (Bucket, DayMarket, MarketQuote,
                                           SimulatedMarketDataSource, kalshi_taker_fee,
                                           standard_ladder)


def _market(probs, d=date(2025, 1, 15), center=40):
    buckets = standard_ladder(center)
    quotes = [MarketQuote(bucket=b, yes_ask=min(0.99, p + 0.015),
                          no_ask=min(0.99, (1 - p) + 0.015), mid=p)
              for b, p in zip(buckets, probs)]
    return DayMarket(target_date=d, buckets=buckets, quotes=quotes, source="simulated")


def _pmf(center=40, spread=1.2):
    ks = range(center - 8, center + 9)
    w = np.exp(-0.5 * ((np.arange(-8, 9)) / spread) ** 2)
    w = w / w.sum()
    return {k: float(x) for k, x in zip(ks, w)}


def test_fee_formula_matches_kalshi():
    # fees = ceil_to_cent(0.07 * C * P * (1-P)):  0.07*0.25 = $0.0175 -> $0.02
    assert kalshi_taker_fee(0.50, 1) == 0.02
    # 0.07 * 10 * 0.35 * 0.65 = $0.15925 -> $0.16
    assert kalshi_taker_fee(0.35, 10) == 0.16
    assert kalshi_taker_fee(0.99, 1) == 0.01  # never zero when a trade happens


def test_ladder_boundaries_exact():
    ladder = standard_ladder(40)  # le 36 | 37-38 | 39-40 | 41-42 | 43-44 | ge 45
    le, b1, b2, b3, b4, ge = ladder
    assert le.settles_yes(36) and not le.settles_yes(37)
    assert b2.settles_yes(39) and b2.settles_yes(40) and not b2.settles_yes(41)
    assert ge.settles_yes(45) and not ge.settles_yes(44)
    # Every integer settles exactly one bucket.
    for k in range(20, 60):
        assert sum(b.settles_yes(k) for b in ladder) == 1


def test_trade_settlement_and_pnl():
    b = Bucket("between", 39, 40)
    t = Trade(date(2025, 1, 15), b.label(), "yes", 1, 0.40, 0.55, fee=0.02)
    t.settle(40, b)   # inclusive endpoint -> YES wins
    assert t.won and abs(t.pnl - (0.60 - 0.02)) < 1e-9
    t2 = Trade(date(2025, 1, 15), b.label(), "yes", 1, 0.40, 0.55, fee=0.02)
    t2.settle(41, b)  # outside -> YES loses
    assert not t2.won and abs(t2.pnl - (-0.40 - 0.02)) < 1e-9


def test_edge_flat_trades_only_when_edge_exceeds_threshold():
    pmf = _pmf(40)
    # Market that matches the model exactly -> no trades (edge < threshold + spread).
    buckets = standard_ladder(40)
    fair = [b.model_probability(pmf) for b in buckets]
    market = _market(fair)
    assert EdgeThresholdFlat(edge_threshold=0.08).decide(market, pmf) == []
    # Market that badly underprices the model's central bucket -> YES trade appears.
    skewed = list(fair)
    center_idx = int(np.argmax(fair))
    skewed[center_idx] = max(0.01, fair[center_idx] - 0.25)
    market2 = _market(skewed)
    trades = EdgeThresholdFlat(edge_threshold=0.08).decide(market2, pmf)
    assert any(t.side == "yes" for t in trades)


def test_kelly_sizes_larger_edges_larger():
    strat = FractionalKelly(edge_threshold=0.05, kelly_fraction=0.25)
    small = strat._size(0.45, 0.40)
    large = strat._size(0.70, 0.40)
    assert 0 <= small < large <= strat.max_contracts


def test_tail_fade_only_sells_overpriced_tails():
    pmf = _pmf(40, spread=0.9)  # tight model -> tails tiny
    buckets = standard_ladder(40)
    fair = [b.model_probability(pmf) for b in buckets]
    # Inflate an outer bucket into the 5-20c band while model says ~0.
    prices = list(fair)
    prices[0] = 0.12
    market = _market(prices)
    trades = TailFade().decide(market, pmf)
    assert len(trades) >= 1
    assert all(t.side == "no" for t in trades)


def test_simulated_market_is_deterministic_and_no_lookahead():
    sim = SimulatedMarketDataSource()
    m1 = sim.day_market(date(2025, 1, 15), baseline_tmax_f=40.3)
    m2 = sim.day_market(date(2025, 1, 15), baseline_tmax_f=40.3)
    assert [q.yes_ask for q in m1.quotes] == [q.yes_ask for q in m2.quotes]
    # Ladder centers on the issue-time baseline, never the outcome.
    assert m1.buckets == standard_ladder(40)
    probs = [q.mid for q in m1.quotes]
    assert abs(sum(probs) - 1.0) < 0.05


def test_summary_accounts_fees_and_roi():
    res = StrategyResult(name="x")
    b = Bucket("between", 39, 40)
    t = Trade(date(2025, 1, 15), b.label(), "yes", 1, 0.40, 0.60, fee=0.02)
    t.settle(39, b)
    res.trades.append(t)
    s = res.summary()
    assert s["n_trades"] == 1 and s["win_rate"] == 1.0
    assert abs(s["net_pnl"] - 0.58) < 1e-9
    assert abs(s["fees"] - 0.02) < 1e-9
    assert abs(s["roi_on_risked"] - 0.58 / 0.40) < 1e-6


def test_kalshi_integer_strikes_are_strict():
    from central_park_tmax.data.kalshi import KalshiMarketDataSource
    f = KalshiMarketDataSource._bucket_from_market
    # 'greater' floor=90 is STRICT: settles YES only at >= 91 (the live ladder's B89.5
    # bucket covers 89-90, so the tail must start at 91).
    ge = f({"strike_type": "greater", "floor_strike": 90})
    assert not ge.settles_yes(90) and ge.settles_yes(91)
    # 'less' cap=83 is STRICT: YES only at <= 82 (B83.5 covers 83-84).
    le = f({"strike_type": "less", "cap_strike": 83})
    assert le.settles_yes(82) and not le.settles_yes(83)
    # Half-point strikes keep their natural integer bound.
    ge_h = f({"strike_type": "greater", "floor_strike": 89.5})
    assert ge_h.settles_yes(90) and not ge_h.settles_yes(89)
    b = f({"strike_type": "between", "floor_strike": 87, "cap_strike": 88})
    assert b.settles_yes(87) and b.settles_yes(88) and not b.settles_yes(89)
