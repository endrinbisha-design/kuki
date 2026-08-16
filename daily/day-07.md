# Day 7 — 2026-08-10

Work top-to-bottom. **Don't scroll to the Answers section** until you've attempted everything.

---

## Part 1 — Probability & Expected Value (5 questions)

**Q1. Three different dice.**
You roll three fair dice. What is the probability all three show *different* values?

**Q2. Which coin?**
You have three coins: one fair (heads 50%), one biased to heads 75%, one biased to heads 25%. You pick one at random and flip it twice — both are heads. What is the probability you picked the 75%-heads coin?

**Q3. Matching socks.**
A drawer holds 5 distinct pairs of socks (10 socks total). You pull out 2 socks at random. What is the probability they form a matching pair?

**Q4. Fair ticket price.**
A raffle sells 1,000 tickets. Prizes: one worth $500 and ten worth $50 each. What is the fair (break-even) price for a single ticket?

**Q5. Roll-and-bank (a "Pig"-style game).**
You roll a fair die repeatedly, adding each roll to a running total — *but* if you ever roll a **1**, you lose the entire total and the game ends. You may stop at any time and keep your total. What is the optimal stopping rule?

---

## Part 2 — Brainteaser

**The snail in the well.**
A snail is at the bottom of a **10-meter** well. Each *day* it climbs up **3 meters**, but each *night* it slips back down **2 meters**. How many days does it take the snail to climb out of the well?

---

## Part 3 — Black-Scholes Lesson

### Day 7: Delta — the hedge ratio

We've mentioned delta twice (it's `N(d1)`). Now we give it the full treatment, because delta is the Greek traders live and breathe — it's how an options book is kept from being a naked bet on direction.

**1. Definition.**
**Delta (Δ) = ∂(option price) / ∂S** — the rate of change of the option's value for a $1 move in the underlying. It's the *first derivative* of the price with respect to the stock.

- **Call delta = `N(d1)`**, which lies in **(0, 1)**.
- **Put delta = `N(d1) − 1`**, which lies in **(−1, 0)** (a put gains when the stock falls).

**2. Three ways to read delta.**

- **Sensitivity:** if a call has Δ = 0.40 and the stock rises $1, the call gains ≈ **$0.40** (for small moves).
- **Hedge ratio:** to neutralize a long call, **short Δ shares**. The combined position is *delta-neutral* — first-order insensitive to small stock moves. This is the practical heart of Black-Scholes replication.
- **Share-equivalent / "how much stock am I really long":** a Δ = 0.40 call behaves like being long 0.40 shares *right now*.

(You'll also hear the loose heuristic "delta ≈ probability of finishing in the money." Be precise in an interview: the *exact* risk-neutral exercise probability is `N(d2)`; delta is `N(d1)`, which is close for near-the-money options but always a bit higher — Day 6.)

**3. Delta across moneyness.**

| Call | Delta | Put | Delta |
|------|:-----:|-----|:-----:|
| Deep ITM | → +1.0 | Deep ITM | → −1.0 |
| At-the-money | ≈ +0.5 | At-the-money | ≈ −0.5 |
| Deep OTM | → 0.0 | Deep OTM | → 0.0 |

A deep-ITM call moves dollar-for-dollar with the stock (like being long a share); a deep-OTM call barely reacts.

**4. Position delta — running a book.**
A desk sums delta across everything: `position delta = Σ (contract delta × number of contracts × shares per contract)`. Traders keep the book's net delta near **zero** so P&L doesn't swing with the market's direction — leaving them exposed instead to *volatility* (which is what they're actually trading).

**5. Worked example.**
Recall Day 4: `S = K = 100, r = 5%, σ = 20%, T = 1`, giving call delta = `N(0.35) ≈ 0.637`.
Say you're long **100 call contracts**, each on 100 shares → 10,000 calls. Position delta = `0.637 × 10,000 = 6,370` share-equivalents. **Hedge by shorting 6,370 shares.** Now if the stock ticks up $1, the calls gain ≈ $6,370 while the short stock loses ≈ $6,370 — roughly flat.

**6. Delta doesn't stay put — dynamic hedging.**
Here's the catch that powers the whole model: **delta itself changes as the stock moves** (and as time passes and vol shifts). So the 6,370-share hedge is only right for this instant. As `S` moves, you must **re-hedge** — buy/sell stock to stay delta-neutral. The *rate* at which delta changes is the next Greek, **gamma** (Day 8), and this continuous re-hedging is exactly the "replicate the option step by step" idea from Day 3, made real.

**Key intuition to carry forward:** delta is both *the option's sensitivity to the stock* and *the number of shares that hedges it*. Keeping a book delta-neutral strips out directional risk so the trader is left holding a pure bet on volatility — which is the whole point of an options desk.

---

## Part 4 — Lesson Quiz (5 questions)

**QZ1.** Define delta in one sentence.

**QZ2.** In Black-Scholes, what does a call's delta equal (in terms of the `N(·)` function), and what range does it live in?

**QZ3.** What is a put's delta, and what sign is it?

**QZ4.** You are long one call (on 100 shares) with delta 0.40. What stock trade makes the position delta-neutral?

**QZ5.** Roughly what are the deltas of a deep-ITM call, an at-the-money call, and a deep-OTM call?

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Part 1 — Probability & EV

**A1 — 5/9.**
First die anything; second must differ (5/6); third must differ from both (4/6): `(6·5·4)/6³ = 120/216 = **5/9 ≈ 0.556**`.

**A2 — 9/14.**
Likelihoods of two heads: fair `(½)² = 4/16`, 75%-coin `(¾)² = 9/16`, 25%-coin `(¼)² = 1/16`; equal priors. `P(75% | HH) = 9 / (4 + 9 + 1) = **9/14 ≈ 0.643**`.

**A3 — 1/9.**
The first sock can be anything; among the remaining 9 socks, exactly 1 matches it. `P = **1/9 ≈ 0.111**`.

**A4 — $1.00.**
Total prize value = `500 + 10×50 = $1,000`, spread over 1,000 tickets → EV per ticket = `1000/1000 = **$1.00**`.

**A5 — Keep rolling until your total reaches 20 (stop at total ≥ 20).**
With current total `s`, one more roll has expected change `= (5/6)(average of 2–6) + (1/6)(−s) = (5/6)(4) − s/6 = (20 − s)/6`. That's positive exactly when `s < 20`. So you should **roll while your total is below 20 and stop once it hits 20 or more**.

## Part 2 — Brainteaser

**The snail — 8 days.**
The snail nets +1 m per full day-night cycle, but it escapes the instant a *daytime* climb reaches the top, before it can slip. At the start of day `n` it sits at `n − 1` meters; it climbs 3, so it's out when `(n − 1) + 3 ≥ 10`, i.e. `n ≥ 8`. On **day 8** it starts at 7 m, climbs to 10 m, and is out — no 8th night. **8 days.** (Trap answer "10 days" forgets that the last climb clears the top before the nightly slip.)

## Part 4 — Lesson Quiz

**AZ1.** Delta is the sensitivity of an option's price to a $1 change in the underlying — the derivative `∂(option price)/∂S`.

**AZ2.** A call's delta = `N(d1)`, and it lies in the range **(0, 1)**.

**AZ3.** A put's delta = `N(d1) − 1`, which is **negative** (in (−1, 0)) — the put gains value as the stock falls.

**AZ4.** **Short 40 shares** (`0.40 × 100`). The long call's +40 share-equivalents and the −40 shares cancel to delta-neutral.

**AZ5.** Deep-ITM call ≈ **+1.0**; at-the-money ≈ **+0.5**; deep-OTM ≈ **0.0**.

---

*Tomorrow (Day 8): **Gamma** — the rate at which delta itself changes, why it forces constant re-hedging, and what "long gamma" feels like.*
