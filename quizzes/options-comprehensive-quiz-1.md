# Comprehensive Options Review — Big Quiz #1

**Covers:** everything so far — fundamentals & pricing (Days 1–6), the full Greeks incl. **Vega (Day 10)** and **Rho & dividends (Day 11)** — **plus interview-style questions on options theory and trading strategies** (spreads, straddles, skew, etc.).

Strategies (Part C) haven't had their own daily lesson yet, so the **answer key explains each one** — treat those answers as a mini-primer. Work through all four parts first; **answers with explanations are at the very end.**

---

## Part A — Fundamentals & Pricing (Days 1–6)

**A1.** A call has strike $40 and trades at $6.50 while the stock is $44. Split the premium into intrinsic value and time value.

**A2.** A stock has a daily volatility of 1.5%. Approximately what is its annualized volatility (252 trading days)?

**A3.** Why does Black-Scholes model stock *returns* as lognormal rather than modeling dollar price changes as normal? Give one concrete reason.

**A4.** In the risk-neutral pricing framework, which real-world quantity "drops out" of an option's price, and what replaces it?

**A5.** State put-call parity for European options on a non-dividend-paying stock, and explain in one line why it must hold.

**A6.** A European call is worth $9 with `S = $100`, `K = $95`, `r = 0`, `T = 1`. What is the same-strike put worth?

**A7.** In the Black-Scholes call formula, what does `N(d2)` represent, and what does `N(d1)` represent?

**A8.** Compute `d1` and `d2` for `S = 100, K = 100, r = 0, σ = 0.30, T = 1`.

---

## Part B — The Greeks (Days 7–11)

**B1.** Name the Greek that is each of the following: (a) the first derivative of price w.r.t. the stock; (b) the second derivative w.r.t. the stock; (c) the derivative w.r.t. time; (d) the derivative w.r.t. volatility; (e) the derivative w.r.t. interest rates.

**B2.** You are long 50 call contracts (each on 100 shares) with delta 0.45. How many shares do you trade, and in which direction, to be delta-neutral?

**B3.** For what moneyness and time-to-expiry are **gamma** and **|theta|** largest? For what moneyness and time-to-expiry is **vega** largest?

**B4.** Is **vega** positive or negative for a long put? Explain why it has the same sign as a long call's vega.

**B5.** Explain the gamma–theta trade-off in one or two sentences. If you are long gamma, what is the sign of your theta?

**B6.** What is the sign of **rho** for a call versus a put, and what is the intuition?

**B7.** How do **dividends** affect call values versus put values, and through what mechanism?

**B8.** An option has delta 0.40, gamma 0.05, and vega 0.30. (a) If the stock rises $4, what's the new approximate delta? (b) If implied vol rises 2 points with the stock unchanged, how much does the option's price change?

---

## Part C — Options Strategies (interview-style)

**C1.** Describe a **bull call spread**: how it's built, its max profit, max loss, and breakeven. When would you use it instead of just buying a call?

**C2.** You believe a stock will make a **big move but you don't know which direction**. What options position expresses that, and what are its breakevens?

**C3.** What's the difference between a **straddle** and a **strangle**, and why might you choose one over the other?

**C4.** Describe a **covered call** (long stock + short call). What's the payoff profile, and what market view does it express?

**C5.** What is a **protective put**, and what is a **collar**? How does a collar cheapen the protection?

**C6.** You think implied volatility is **too high** and the stock will stay range-bound. Name a **defined-risk** strategy that profits if the stock goes nowhere, and state where its max profit and max loss occur.

**C7.** What is the **maximum loss** on each of: (a) long call, (b) long put, (c) naked short call, (d) short put?

**C8.** Describe a **long butterfly** spread. What view does it express and what is its risk profile?

**C9.** What is a **calendar (time) spread**, and what two things does the buyer of one typically want to happen?

**C10.** What is a **risk reversal** (short put + long call), and what directional and volatility-skew exposures does it carry?

---

## Part D — Theory & Concept Questions (interview-style)

**D1.** What *is* implied volatility, and what does it tell you that the option's dollar price alone does not?

**D2.** In equity index options, out-of-the-money **puts** typically trade at higher implied vols than OTM calls. What is this pattern called, and give one reason it exists.

**D3.** Why do options market-makers **delta-hedge**? What risk are they trying to keep, and what risk are they trying to shed?

**D4.** What's the difference between **American** and **European** options? For a non-dividend-paying stock, is it ever optimal to exercise an American *call* early? What about a *put*?

**D5.** Two options on the same stock and expiry have the same strike, but one has a higher **implied volatility** than the other in the market. Is that possible, and if you saw it, what would you do?

**D6.** If you're **long a straddle** and the stock barely moves for two weeks while implied vol also drifts lower, explain — in Greek terms — the two ways you're losing money.

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Part A — Fundamentals & Pricing

**A1.** Intrinsic = `max(44 − 40, 0) = $4`; time value = `6.50 − 4 = $2.50`.

**A2.** `1.5% × √252 ≈ 1.5% × 15.87 ≈ **23.8%**`.

**A3.** Any one of: percentage returns are comparable across price levels/time; a lognormal price stays strictly **positive** (a normal-dollar-change model could push a stock below zero, which is impossible); the lognormal is right-skewed, matching stocks' unlimited upside / floored-at-zero downside.

**A4.** The stock's **real-world expected return / drift `μ`** drops out; it's replaced by the **risk-free rate `r`**. Pricing happens in a risk-neutral world where all assets drift at `r`.

**A5.** `C − P = S − K·e^(−rT)`. It must hold because "long call + short put" (same K, T) pays exactly `S − K` at expiry — a forward — which can be built today for `S − K·e^(−rT)`; identical payoffs must have identical prices or there's an arbitrage.

**A6.** With `r = 0`: `C − P = S − K = 100 − 95 = 5`, so `P = 9 − 5 = **$4**`.

**A7.** `N(d2)` = the **risk-neutral probability the call finishes in the money** (is exercised). `N(d1)` = the call's **delta** (hedge ratio / share-equivalent); it's also a stock-value-weighted exercise probability, and is always ≥ `N(d2)`.

**A8.** `σ²/2 = 0.09/2 = 0.045`. `d1 = [ln(1) + (0 + 0.045)·1]/(0.30·1) = 0.045/0.30 = **0.15**`; `d2 = 0.15 − 0.30 = **−0.15**`.

## Part B — The Greeks

**B1.** (a) **Delta**; (b) **Gamma**; (c) **Theta**; (d) **Vega**; (e) **Rho**.

**B2.** Position delta = `0.45 × 50 × 100 = 2,250` share-equivalents (long). **Short 2,250 shares** to be delta-neutral.

**B3.** Gamma and |theta| are largest for **at-the-money options near expiry**. Vega is largest for **at-the-money options with long time to expiry** (the long end of the calendar).

**B4.** Vega is **positive** for a long put, the same sign as a long call. Higher volatility widens the distribution of future prices; because both calls and puts have one-sided payoffs (limited downside, open upside), more dispersion raises the value of *both*.

**B5.** Owning convexity and paying for time are two sides of one coin: **long gamma ⇒ negative theta** (you pay daily time-decay "rent" for the privilege of profiting from big moves); short gamma ⇒ positive theta. Long gamma → theta is **negative**.

**B6.** **Call rho positive, put rho negative.** Higher rates shrink the present value of the strike `K·e^(−rT)`: the call holder benefits from deferring that payment (worth more); by parity the put is worth less.

**B7.** **Dividends lower calls and raise puts.** Dividends pay shareholders, not option holders, reducing the stock's forward price — bad for calls (need the stock higher), good for puts.

**B8.** (a) New delta ≈ `0.40 + 0.05×4 = **0.60**`. (b) Price change ≈ `0.30 × 2 = **+$0.60**`.

## Part C — Options Strategies

**C1. Bull call spread.** Buy a lower-strike call and sell a higher-strike call, same expiry (a net **debit**). **Max loss** = the net premium paid (if the stock finishes below the lower strike). **Max profit** = (difference in strikes) − net debit (if it finishes above the higher strike). **Breakeven** = lower strike + net debit. Use it when you're **moderately bullish**: selling the upper call cheapens the trade and lowers your breakeven, at the cost of capping your upside.

**C2. A long straddle** (buy a call *and* a put at the same at-the-money strike and expiry). You profit from a large move in *either* direction. **Breakevens** = strike ± (total premium paid). It's a long-volatility / long-gamma bet; the max loss (the total premium) occurs if the stock pins the strike at expiry.

**C3. Straddle vs. strangle.** A **straddle** buys the call and put at the **same** (usually ATM) strike; a **strangle** buys an **OTM call and an OTM put** at different strikes. The strangle is **cheaper** (both legs are OTM) but needs a **bigger move** to pay off; the straddle costs more but starts making money on a smaller move. Both are long-vol.

**C4. Covered call.** Long 100 shares + short 1 call. You collect the call premium as income and keep the stock's dividends, but your **upside is capped at the strike** (the shares get called away above it) and you still bear the downside below (cushioned only by the premium received). It expresses a **neutral-to-mildly-bullish** view — you don't expect the stock much above the strike and want yield.

**C5. Protective put & collar.** A **protective put** is long stock + long put: the put acts as insurance, flooring your downside at the strike, for the cost of the premium. A **collar** adds a **short OTM call** on top (long stock + long put + short call); the call premium **helps pay for the put** (often making it near-zero-cost), in exchange for capping your upside at the call strike. A collar brackets the stock between a floor and a ceiling.

**C6. A short iron condor** (equivalently: sell an OTM put spread *and* an OTM call spread). It's a **net credit**, **defined-risk** short-vol trade. **Max profit** = the net credit, earned if the stock stays between the two short strikes through expiry. **Max loss** = (width of one spread) − net credit, hit if the stock blows through either wing. (Selling a straddle/strangle expresses the same view but with *undefined* risk — the condor caps it.)

**C7. Maximum loss.** (a) Long call → the **premium paid**. (b) Long put → the **premium paid**. (c) Naked short call → **unlimited** (the stock can rise without bound). (d) Short put → **strike − premium received** per share (large but bounded; worst case the stock goes to zero).

**C8. Long butterfly.** Buy 1 lower-strike call, sell 2 middle-strike calls, buy 1 higher-strike call, equally spaced, same expiry — a small net **debit**. **Max profit** occurs if the stock finishes right at the **middle strike** (= middle − lower − net debit); **max loss** = the net debit, on a move to either wing. It's a **low-volatility / pinning** bet: you win if the stock sits near the middle strike, with strictly limited risk.

**C9. Calendar (time) spread.** Sell a **near-term** option and buy a **longer-term** option at the **same strike**. The buyer typically wants (1) the stock to sit **near the strike** so the short near-dated leg **decays faster** (you harvest the theta differential), and (2) **implied vol to rise** — the position is net **long vega** (the longer-dated leg has more vega).

**C10. Risk reversal.** Sell an OTM put and buy an OTM call (same expiry) — often structured for zero net cost. It's a **bullish**, synthetic-long-like position: you profit if the stock rallies, and you're exposed below the put strike. It's also a **skew** trade — you're short the (usually pricier) downside put vol and long the upside call vol, so you benefit if the put-over-call skew flattens.

## Part D — Theory & Concept

**D1. Implied volatility** is the volatility input that, plugged into Black-Scholes, reproduces the option's **market price**. It converts a dollar price into the market's forecast of **future volatility**, letting you compare options across strikes, expiries, and underlyings on an apples-to-apples basis — a $5 option isn't "cheap" or "expensive" until you know the vol it implies.

**D2.** It's called **volatility skew** (or the "smirk"). Reasons include: **crash-o-phobia / demand for downside protection** (investors overpay for OTM puts as insurance), the **leverage effect** (falling stocks become more volatile), and the fact that big market moves are disproportionately to the *downside*. The result: OTM puts carry higher implied vol than equidistant OTM calls.

**D3.** Market-makers **delta-hedge** to strip out **directional risk** (they don't want a bet on the stock going up or down) so they're left holding the exposure they actually chose to trade — **volatility** (gamma/vega). They profit from the bid-ask spread and from realized-vs-implied vol, not from guessing direction, so they neutralize delta and re-hedge dynamically as it drifts.

**D4. American vs. European.** American options can be exercised **any time up to expiry**; European only **at expiry**. For a **non-dividend** stock it is **never optimal to exercise an American call early** (you'd throw away remaining time value and lose the interest on the deferred strike — better to sell it), so such an American call is worth the same as the European. Early exercise of a **put** *can* be optimal when it's deep in-the-money, to collect the strike cash now and earn interest on it. (Calls become early-exercise candidates only to capture a **dividend**.)

**D5.** For a single option, the market price and its implied vol are one-to-one, so the *same* option can't simultaneously show two different IVs — but **two different options** (or the same option quoted on two venues) can imply different vols. If you genuinely saw the *identical* contract cheaper on one venue, you'd **buy the low-IV (cheap) one and sell the high-IV (rich) one** to capture the mispricing (subject to costs/liquidity). More realistically, different strikes having different IVs is just the **skew/smile** — not an arbitrage, but the surface you trade against.

**D6.** In Greek terms: (1) **theta** — you're long a straddle, so long gamma and paying daily time decay; a quiet market means your gamma re-hedging earns little while theta bleeds the premium away. (2) **vega** — you're long vega, so the **drop in implied vol** directly marks down both options. So you lose on *both* the passage of time (theta) and the vol repricing (vega), even with the stock unchanged.

---

*This quiz spans Days 1–11. The regular Day-12 big quiz will focus on Days 10–12 (vega, rho/dividends, and implied vol & the smile).*
