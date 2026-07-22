# Day 2 — 2026-07-22

Work top-to-bottom. **Don't scroll to the Answers section** until you've attempted everything.

---

## Part 1 — Probability & Expected Value (5 questions)

**Q1. At least one six.**
You roll two fair dice. Given that *at least one* of them shows a 6, what is the probability that *both* show a 6?

**Q2. Making a market.**
A contract is worth $1 if a fair coin lands heads and $0 if tails — so its true value is $0.50. You quote a market: **bid $0.45 / ask $0.55**. A customer is equally likely to buy from you (at your ask) or sell to you (at your bid), and trades exactly one contract. What is your expected profit per trade?

**Q3. Exactly one ace.**
You're dealt 5 cards from a standard 52-card deck. What is the probability you hold *exactly one* ace?

**Q4. Same EV, different risk.**
Game A pays **$100 with probability ½** and **$0 with probability ½**. Game B pays **$50 for certain**. (a) Which has the higher expected value? (b) Which has higher variance? (c) If both cost the same to play, which would a *risk-averse* person prefer, and why?

**Q5. Biased coin, first heads.**
A biased coin lands heads with probability 1/3. You flip it until the first heads appears. (a) What is the expected number of flips? (b) What is the probability that the first heads occurs on an *even-numbered* flip?

---

## Part 2 — Brainteaser

**Eight balls, one heavy.**
You have 8 balls that look identical. Exactly one is slightly *heavier* than the other seven, which all weigh the same. You have a balance scale (it tells you which side is heavier, or if they're equal). How do you guarantee finding the heavy ball in only **two weighings**?

---

## Part 3 — Black-Scholes Lesson

### Day 2: Where price uncertainty comes from — returns, volatility, and the lognormal picture

Yesterday we saw that an option's value hinges on the *distribution of possible future prices*. Today we build that distribution. This is the engine room of Black-Scholes.

**1. Model returns, not raw price changes.**
A $1 move means something very different on a $10 stock (10%) than on a $500 stock (0.2%). Raw dollar changes aren't comparable across stocks or over time. **Percentage returns** are the natural unit. And modeling returns has a bonus: a stock price built from percentage returns can *never go negative* — you can lose 99% and 99% again, but never cross zero. Dollar-change models would happily send a price below zero, which is nonsense for a stock.

**2. Volatility is the standard deviation of returns.**
"Volatility" (`σ`) is just how spread-out the returns are — the standard deviation. High σ = returns are all over the place = wide distribution of future prices. Low σ = returns cluster tightly. This single number is *the* input traders fight over, because everything else in Black-Scholes (`S`, `K`, `r`, `T`) is observable, but σ is a forecast.

**3. Volatility scales with the square root of time.** ⭐
Randomness accumulates, but *slower* than linearly — it grows with √time, not time. So to convert between horizons you multiply by √(ratio of periods):

> σ(annual) = σ(daily) × √(number of trading days) = σ(daily) × √252

*Worked example:* a stock moves about **1% per day** (daily σ = 0.01). Its annualized volatility is
`0.01 × √252 ≈ 0.01 × 15.87 ≈ 16%`.
This √t rule is why a "16% vol" stock and "1% daily moves" are the same statement — memorize √252 ≈ 15.9. (Rule of thumb: **daily vol ≈ annual vol ÷ 16**.)

**4. The lognormal picture.**
Black-Scholes assumes **log returns are normally distributed** (a bell curve). If the *log* of the return is normal, then the *price* itself follows a **lognormal** distribution. Two consequences that matter:

- **Prices stay positive** (lognormal lives on 0 to ∞).
- **The distribution is right-skewed** — a stock can double, triple, 10× (unbounded upside) but can only fall to zero. So the future-price distribution has a long right tail.

*Worked example:* stock at $100, annual vol 20%, one year out. A rough 1-standard-deviation band for the price is about `$100 × e^{±0.20} ≈ $81.9 to $122.1`. Notice it's not symmetric around $100 — the up-move ($22.1) is bigger than the down-move ($18.1). That asymmetry is the lognormal skew.

**5. Geometric Brownian Motion (GBM) — the equation.**
Putting it together, Black-Scholes assumes the stock follows:

> **dS/S = μ dt + σ dW**

Read it as: the *percentage* change in the stock over a tiny instant = a **drift** term (`μ dt`, the predictable trend) + a **diffusion** term (`σ dW`, the random shock, where `dW` is a random draw scaled by √dt). Two pieces:

- **Drift (`μ`)** — the expected trend. *Foreshadow:* here's the twist that makes Black-Scholes work — this drift term will turn out to **not matter** for pricing the option. We replace it with the risk-free rate. That's tomorrow's lesson (risk-neutral pricing).
- **Diffusion (`σ`)** — the randomness, driven entirely by volatility. This is what the option is really a bet on.

**Key intuition to carry forward:** the option is a bet on the *width* (`σ`) of the future-price distribution, not its *direction* (`μ`). That's the deep reason two traders who disagree about whether a stock goes up or down can still agree on the option's price.

---

## Part 4 — Lesson Quiz (5 questions)

**QZ1.** Give one reason Black-Scholes models percentage returns rather than raw dollar price changes.

**QZ2.** A stock has a daily volatility of 1%. Approximately what is its annualized volatility (assume 252 trading days)?

**QZ3.** If a stock's *log returns* are normally distributed, what distribution do the stock *prices* follow — and what's one property of that distribution that makes it realistic for stocks?

**QZ4.** In the GBM equation `dS/S = μ dt + σ dW`, which term captures the predictable trend and which captures the randomness?

**QZ5.** Two stocks trade at the same price with the same expected return, but Stock A has 15% volatility and Stock B has 40% volatility. Whose call options are worth more, all else equal, and why?

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Part 1 — Probability & EV

**A1 — 1/11.**
P(at least one six) = 1 − P(no six) = 1 − (5/6)² = 1 − 25/36 = 11/36. P(both six) = 1/36.
P(both | at least one) = (1/36) / (11/36) = **1/11 ≈ 9.1%**. (Common trap: the answer is *not* 1/6 — conditioning on "at least one six" isn't the same as fixing one specific die.)

**A2 — +$0.05 per trade.**
- If the customer **buys at your $0.55 ask**: you're now short a contract worth $0.50 on average, but you collected $0.55 → profit $0.05.
- If the customer **sells at your $0.45 bid**: you bought for $0.45 something worth $0.50 → profit $0.05.
Either way you make **$0.05**, so EV = **+$0.05**. Lesson: a market-maker's edge is the **half-spread** (½ × $0.10), earned regardless of direction — that's why flow is profitable if your fair value is right.

**A3 — ≈ 29.95% (about 30%).**
Exactly one ace = (choose 1 of 4 aces) × (choose 4 of the 48 non-aces) / (all 5-card hands):
`C(4,1)·C(48,4) / C(52,5) = 4 · 194,580 / 2,598,960 = 778,320 / 2,598,960 ≈ 0.2995` → **≈ 30%**.

**A4 — Same EV; A has higher variance; risk-averse prefers B.**
(a) EV(A) = ½·100 + ½·0 = $50 = EV(B). **Equal.**
(b) Var(A) = ½(100−50)² + ½(0−50)² = 2,500 (std dev $50); Var(B) = 0. **A is far riskier.**
(c) A **risk-averse** person prefers **B** — same expected payout with zero uncertainty. The gap between what they'd pay for A vs. its $50 EV is the "risk premium," and pricing that gap is much of what markets do.

**A5 — (a) 3 flips; (b) 2/5.**
(a) First-success count is geometric with p = 1/3, so expected flips = 1/p = **3**.
(b) With q = 2/3, P(first head on an even flip) = q/(1+q) = (2/3)/(5/3) = **2/5 = 0.4**.
Quick derivation: P(even) = Σ q^(2k−1)·p = pq/(1−q²) = (1/3)(2/3)/(1−4/9) = (2/9)/(5/9) = 2/5.

## Part 2 — Brainteaser

**Eight balls — split 3, 3, 2.**
*Weighing 1:* put **3 balls on each pan**, leaving 2 aside.
- **If they balance:** the heavy ball is one of the **2 set aside**. *Weighing 2:* put those 2 on the scale, one per pan — the heavier pan is the heavy ball. ✓
- **If they don't balance:** the heavy ball is among the **3 on the heavier pan**. *Weighing 2:* take those 3, weigh **1 vs. 1**. If one is heavier, that's it; if they balance, it's the **third** (un-weighed) ball. ✓
Two weighings, guaranteed. (Key idea: each weighing has *three* outcomes — left, right, balanced — so two weighings distinguish up to 3² = 9 cases, more than enough for 8 balls.)

## Part 4 — Lesson Quiz

**AZ1.** Any of: percentage returns are comparable across different price levels and across time; and a price built from returns can never go negative (a dollar-change model could push a price below zero, which is impossible for a stock).

**AZ2.** `1% × √252 ≈ 1% × 15.87 ≈ 16%`. (Handy rule: annual vol ≈ daily vol × 16.)

**AZ3.** Prices are **lognormally** distributed. Realistic properties: it keeps prices **strictly positive**, and it's **right-skewed** (unlimited upside, floored at zero) — matching how stocks actually behave.

**AZ4.** `μ dt` is the **drift** (predictable trend); `σ dW` is the **diffusion** (the random shock, driven by volatility).

**AZ5.** **Stock B's** (40% vol). Higher volatility widens the distribution of future prices, increasing the chance of large favorable moves. Since a call's downside is capped (you just let it expire) but its upside grows with those bigger moves, more volatility makes calls — and puts — more valuable.

---

*Tomorrow (Day 3): no-arbitrage, replication, and the risk-neutral idea — how hedging pins down a price and why that drift term `μ` disappears. **Day 3 also carries the first big cumulative quiz (Days 1–3).***
