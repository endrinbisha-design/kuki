# Day 6 — 2026-08-09  ·  ⭐ Big cumulative quiz day (Days 4–6)

Work top-to-bottom. **Don't scroll to the Answers section** until you've attempted everything. Today's Part 4 is a **bigger review quiz** covering Days 4–6.

---

## Part 1 — Probability & Expected Value (5 questions)

**Q1. Nine heads in a row.**
You flip a fair coin 10 times. Given that the first 9 flips all came up heads, what is the probability the 10th flip is also heads?

**Q2. At least one man.**
A committee of 3 is chosen at random from 4 men and 5 women. What is the probability the committee includes at least one man?

**Q3. Cards in place.**
A 52-card deck is shuffled uniformly at random. What is the expected number of cards that land in their *original* position?

**Q4. Sum of eight.**
You roll two fair dice and are told the sum is 8. What is the probability that (at least) one of the dice shows a 5?

**Q5. The martingale.**
Starting with a $1 bet on a fair, even-money coin, you use the classic doubling strategy: after any loss you double your next bet ($1, then $2, $4, $8, …), and you stop the moment you win. Assuming no bankroll limit, what is your profit when you finally win — and what is the catch that makes this *not* free money?

---

## Part 2 — Brainteaser

**The water jugs.**
You have a **3-liter** jug, a **5-liter** jug, and an unlimited water supply. Neither jug has markings. How do you measure out exactly **4 liters**?

---

## Part 3 — Black-Scholes Lesson

### Day 6: What `N(d1)` and `N(d2)` actually mean

We can now read the two probabilities in the call formula `C = S·N(d1) − K·e^(−rT)·N(d2)` with real understanding. They look symmetric but they mean different things — and interviewers love probing whether you know the difference.

**`N(d2)` — the probability of exercise.**
`N(d2)` is the **risk-neutral probability that the call finishes in the money** — that `S_T > K` at expiry, so you exercise and pay the strike. That's why it multiplies the strike term: you only pay `K` in the fraction `N(d2)` of scenarios where exercise happens, and `e^(−rT)` discounts that payment to today.

> ⚠️ **Crucial subtlety:** `N(d2)` is the probability under the **risk-neutral** measure (where the stock drifts at `r`), *not* the real-world probability. The real-world chance of exercise would use the true drift `μ`, which — as we saw on Day 3 — never enters pricing. So "the market's implied probability the option pays off" = `N(d2)`, and it is *not* what you'd get from the stock's actual expected return.

**`N(d1)` — the delta (and a probability under a different lens).**
`N(d1)` has two faces:

1. **It is the call's delta** — `∂C/∂S = N(d1)` — the hedge ratio. A call with `N(d1) = 0.64` moves like **0.64 shares** of stock and is hedged by shorting 0.64 shares. (Full delta treatment is tomorrow, Day 7.)
2. **It is also a probability**, but a *stock-weighted* one. The term `S·N(d1)` is the present value of *receiving the stock, in the scenarios where you exercise*. Because high-stock scenarios contribute more stock value, `N(d1)` tilts toward those up-states.

**Why `N(d1) ≥ N(d2)`, always.**
They differ by exactly `σ√T`: `d1 = d2 + σ√T`. The extra `σ√T` pushes `N(d1)` above `N(d2)`. Intuition: `N(d2)` just counts *whether* you exercise; `N(d1)` counts exercise *weighted by how much stock you collect*, and the biggest up-moves carry the most weight — so the stock-weighted measure is always at least as large. The gap widens with more volatility or more time.

**A picture of delta (`N(d1)`) across moneyness:**

| Situation | `N(d1)` ≈ delta | Call behaves like… |
|-----------|:---------------:|--------------------|
| Deep in-the-money | → 1.0 | the stock itself (minus discounted strike) |
| At-the-money | ≈ 0.5–0.6 | about half a share |
| Deep out-of-the-money | → 0.0 | almost nothing |

**Worked example (Day 4's numbers).**
`S = K = 100, r = 5%, σ = 20%, T = 1` gave `d1 = 0.35, d2 = 0.15`:
- `N(d1) = N(0.35) ≈ 0.637` → the call's **delta is 0.637**: it currently behaves like holding 0.637 shares, and you'd short 0.637 shares to hedge it.
- `N(d2) = N(0.15) ≈ 0.560` → there's a **~56% risk-neutral probability** the call finishes in the money.
- Note `0.637 > 0.560` ✓ — the `σ√T = 0.20` gap between them.

**One more for puts:** a put's delta is `N(d1) − 1`, which is negative (a put gains when the stock falls), running from 0 (deep OTM) to −1 (deep ITM).

**Key intuition to carry forward:** `N(d2)` answers *"how likely am I to exercise?"* (risk-neutral), while `N(d1)` answers *"how much stock am I effectively long right now?"* (the delta / hedge ratio). Same formula, two very different roles — and neither is the real-world probability of anything, because pricing lives in the risk-neutral world.

---

## Part 4 — ⭐ BIG CUMULATIVE QUIZ (Days 4–6, 10 questions)

**BQ1.** Write out the Black-Scholes formula for a European call.

**BQ2.** Compute `d1` and `d2` for `S = 100, K = 100, r = 0, σ = 0.25, T = 1`.

**BQ3.** In risk-neutral terms, what does `N(d2)` represent?

**BQ4.** Besides being a probability, what quantity does `N(d1)` equal?

**BQ5.** Explain why `N(d1)` is always at least as large as `N(d2)`.

**BQ6.** State put-call parity for European options on a non-dividend stock.

**BQ7.** A call is worth $12 with `S = $100, K = $95, r = 0, T = 0.5`. Using parity, what is the same-strike put worth?

**BQ8.** What position does "long one call + short one put" (same strike and expiry) replicate?

**BQ9.** A *deep in-the-money* call has a delta close to what value, and it behaves like what underlying position?

**BQ10.** True or false: `N(d2)` is the real-world (actual) probability that the call will be exercised. Explain.

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Part 1 — Probability & EV

**A1 — 1/2.**
Coin flips are independent; past results carry no information about the next flip. The probability is **½**, regardless of the nine prior heads. (The gambler's-fallacy trap: earlier outcomes don't "owe" a correction.)

**A2 — 37/42 ≈ 0.881.**
Easier via the complement: `P(no man) = P(all 3 women) = C(5,3)/C(9,3) = 10/84`. So `P(≥1 man) = 1 − 10/84 = 74/84 = **37/42 ≈ 0.881**`.

**A3 — 1.**
By linearity of expectation, each specific card returns to its own position with probability `1/52`, and there are 52 cards: `52 × (1/52) = **1**`. (Neat fact: the expected number of fixed points of a random permutation is always 1, regardless of deck size.)

**A4 — 2/5.**
Ways to make 8: (2,6), (3,5), (4,4), (5,3), (6,2) — five equally likely ordered outcomes. Those containing a 5: (3,5) and (5,3) — two of them. `2/5 = **0.4**`.

**A5 — Profit is exactly $1; the catch is the bankroll.**
Each doubling sequence, whenever it finally wins, recovers all prior losses plus a net **$1**: losing `1 + 2 + … + 2^(k−1) = 2^k − 1` then winning `2^k` nets `+1`. The catches: (i) it requires an **unbounded bankroll** and unlimited bet sizes — a losing streak needs exponentially growing capital; (ii) with any *finite* bankroll there's a real chance of a streak that wipes you out before the win, and that rare catastrophic loss exactly offsets the steady $1 gains, leaving EV = 0 (worse, with any house edge). "Guaranteed" profit funded by unlimited borrowing isn't an edge.

## Part 2 — Brainteaser

**The water jugs — leave 4 in the 5-liter.**
1. Fill the **5L** jug, then pour into the **3L** jug until full → **2L remain** in the 5L jug.
2. Empty the **3L** jug. Pour the **2L** from the 5L into the 3L jug (3L now holds 2).
3. Fill the **5L** jug again. Pour from it into the 3L jug until the 3L is full — it only needs **1 more liter** → the 5L jug is left with `5 − 1 = **4 liters**`. ✓

## Part 4 — Big Cumulative Quiz (Days 4–6)

**BAQ1.** `C = S·N(d1) − K·e^(−rT)·N(d2)`, with `d1 = [ln(S/K) + (r + σ²/2)T] / (σ√T)` and `d2 = d1 − σ√T`.

**BAQ2.** `σ²/2 = 0.25²/2 = 0.03125`. `d1 = [ln(1) + (0 + 0.03125)·1]/(0.25·1) = 0.03125/0.25 = **0.125**`; `d2 = 0.125 − 0.25 = **−0.125**`.

**BAQ3.** The **risk-neutral probability that the call finishes in the money** (that `S_T > K`, so it's exercised).

**BAQ4.** The call's **delta** — `∂C/∂S = N(d1)` — the number of shares the option currently behaves like / the hedge ratio.

**BAQ5.** Because `d1 = d2 + σ√T`, and `N(·)` is increasing, so `N(d1) ≥ N(d2)`. Meaning: `N(d2)` just counts the probability of exercise, while `N(d1)` weights exercise by how much stock value you collect — the large up-moves get extra weight, pushing it higher.

**BAQ6.** `C − P = S − K·e^(−rT)`.

**BAQ7.** With `r = 0`, parity gives `C − P = S − K = 100 − 95 = 5`, so `P = 12 − 5 = **$7**`.

**BAQ8.** A **forward / synthetic long stock** — it pays `S − K` at expiry in every scenario.

**BAQ9.** Delta ≈ **1.0**; it behaves essentially like being **long the stock** (specifically, long the stock minus the discounted strike).

**BAQ10.** **False.** `N(d2)` is the **risk-neutral** probability of exercise, computed with the stock drifting at the risk-free rate `r`. The real-world probability would use the stock's true expected return `μ`, which doesn't appear anywhere in pricing.

---

*Tomorrow (Day 7): **Delta** in full — the hedge ratio, how it changes with the stock, and how traders use it to stay market-neutral.*
