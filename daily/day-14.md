# Day 14 — 2026-08-17

Work top-to-bottom. **Don't scroll to the Answers section** until you've attempted everything.

---

## Part 1 — Probability & Expected Value (5 questions)

**Q1. Three heads in a row.**
You flip a fair coin until you first see three heads in a row (HHH). What is the expected number of flips? (Recall HH was 6 and HT was 4 — does the pattern keep growing?)

**Q2. Four-door Monty.**
A game show has 4 doors; one hides a prize. You pick a door. The host — who knows where the prize is — opens **two** of the other three doors, both empty, and offers you the chance to switch to the last remaining unopened door. Should you switch, and what is your probability of winning if you do?

**Q3. Ascents in a shuffle.**
A 52-card deck is shuffled uniformly at random. An "ascent" is a position where a card is immediately followed by a higher-ranked card (treat all 52 as distinct ranks). What is the expected number of ascents?

**Q4. Kelly bet.**
You can stake any amount on a bet that wins with probability 0.4; a win returns **3× your stake in profit**, a loss forfeits the stake. (a) What is the expected profit per $1 staked? (b) What fraction of your bankroll does the Kelly criterion say to bet?

**Q5. The secretary problem.**
You interview `n` candidates one at a time in random order and must accept or reject each on the spot (no going back). You only care about hiring *the single best* candidate. What strategy maximizes your chance of doing so, and what is that probability for large `n`?

---

## Part 2 — Brainteaser

**1,000 bottles, 10 rats.**
You have 1,000 bottles of wine; exactly one is poisoned. The poison is lethal but takes up to 24 hours to act, and even a single drop is fatal. You have **10 lab rats** and **24 hours** before you must serve the wine. How can you guarantee identifying the single poisoned bottle in time?

---

## Part 3 — Black-Scholes Lesson

### Day 14: The limits of Black-Scholes — where the assumptions break

Black-Scholes is the field's foundation, but no serious trader believes it literally. Knowing *where and why it fails* — and what desks do about it — is exactly the kind of maturity interviewers probe for.

**1. The assumptions, laid bare.**
Black-Scholes rests on a stack of idealizations:
1. **Constant, known volatility** across all strikes and expiries.
2. **Continuous price paths** — a lognormal/GBM diffusion with **no jumps**.
3. **Normally distributed log returns** (thin, well-behaved tails).
4. **Frictionless, continuous hedging** — no transaction costs, trade any size anytime.
5. **Constant interest rate**, no dividends (relaxable), European exercise.

Every one of these is false in the real world. Here's how each breaks.

**2. Volatility is not constant → the smile/skew.**
The most direct evidence is the **volatility smile/skew** itself (Day 12). If BS were right, every strike would imply the same vol; instead the market quotes a *curve*. Volatility also **clusters** (calm begets calm, turbulence begets turbulence) and is itself **random** over time. Fixes: **local-vol** models (Dupire), **stochastic-vol** models (Heston, SABR) that let σ vary with price and time.

**3. Prices jump → fat tails.**
Real markets **gap** — overnight, on earnings, on news, in crashes — with no chance to hedge continuously through the move. BS's continuous diffusion assigns essentially **zero probability** to large sudden moves, but they happen far more often than a bell curve allows. **Black Monday (Oct 1987)** was a ~20-standard-deviation day under BS — a "once in the lifetime of many universes" event — yet it occurred. Real return distributions are **leptokurtic** (fat-tailed) with **negative skew**. Fix: **jump-diffusion** models (Merton) add discrete jumps, fattening the tails and naturally producing a skew.

**4. Hedging isn't frictionless.**
Continuous, costless replication is a fiction. In practice you re-hedge **discretely**, pay **spreads and commissions**, and can't trade at all through a gap. So the perfect BS replication leaks — **hedging error** is real and grows with jumps, transaction costs, and how coarsely you re-hedge (Day 13).

**5. What this means — and what traders actually do.**
BS **systematically misprices** options (especially OTM puts) if you feed it one flat vol. But rather than throw it out, the market uses it as a **quoting language**: prices are translated to implied vols, and the *smile/skew/term-structure surface* carries all the corrections BS omits. "All models are wrong; some are useful" — BS is the useful, universal translator, and the **vol surface is where reality gets encoded.** For exotics and path-dependent products, desks reach for the richer models above; for tail risk, they **stress-test for jumps** and often hold some **long-convexity tail hedges.**

**6. A cautionary thread.**
Models that assume normality **underestimate tail risk**, and that mistake, levered up, has repeatedly caused blow-ups — from **portfolio insurance in 1987**, to **LTCM (1998)**, to **short-vol** strategies that collect steady premium for years and then lose it all in a single spike. The recurring lesson: the money is in the tails the Gaussian model waves away.

**Key intuition to carry forward:** Black-Scholes is a brilliant *baseline* and a common language, not a description of reality. Its failures — constant vol, no jumps, thin tails, costless hedging — are exactly the risks that matter most in a crisis. The professional stance is to **use BS as a translator, model the vol surface for the corrections, and respect the fat tails it ignores.**

---

## Part 4 — Lesson Quiz (5 questions)

**QZ1.** Name three assumptions of Black-Scholes that are violated in real markets.

**QZ2.** What observable market phenomenon is the most direct evidence that the constant-volatility assumption is false?

**QZ3.** What does adding *jumps* (a jump-diffusion model) do to the return distribution's tails and to the implied-vol skew?

**QZ4.** Given its known flaws, how do practitioners actually use the Black-Scholes model day to day?

**QZ5.** Being short out-of-the-money puts (short tail vol) is usually profitable. Why is it nonetheless dangerous?

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Part 1 — Probability & EV

**A1 — 14 flips.**
For a run of `k` heads with a fair coin, the expected wait is `2^(k+1) − 2`. For HHH: `2⁴ − 2 = **14**`. (Sanity: HH gives `2³ − 2 = 6`, matching Day 5; each extra required head roughly doubles the wait.)

**A2 — Switch; you win 3/4.**
Your original door had probability `1/4` and *stays* `1/4` after the host reveals empties. All the remaining probability, `3/4`, collapses onto the single unopened door you can switch to. **Switch → 3/4** (a stronger version of the classic 3-door 2/3).

**A3 — 25.5.**
There are 51 adjacent pairs; each is an ascent with probability `½` (either the left or right card is larger, equally likely). By linearity, `51 × ½ = **25.5**`.

**A4 — (a) +$0.60 per $1; (b) 20% of bankroll.**
(a) `E = 0.4·(+3) + 0.6·(−1) = 1.2 − 0.6 = **+$0.60**` per $1 staked. (b) With win-multiple `b = 3`, win prob `p = 0.4`, loss prob `q = 0.6`, Kelly says bet `f* = p − q/b = 0.4 − 0.6/3 = 0.4 − 0.2 = **0.20**` → 20% of bankroll.

**A5 — Reject the first ~37%, then take the next record-breaker; success ≈ 1/e ≈ 37%.**
Optimal rule: observe and reject the first `n/e` candidates (≈ 37%), remembering the best among them, then **accept the first subsequent candidate better than all seen so far.** As `n → ∞` this hires the very best with probability `1/e ≈ **37%**` — remarkably high for a no-going-back problem.

## Part 2 — Brainteaser

**Binary-encode the bottles across the 10 rats.**
Number the bottles `0` to `999` and write each number in **10-bit binary** (since `2¹⁰ = 1024 > 1000`). Assign **rat `i` to bit `i`**: rat `i` drinks a drop from *every* bottle whose number has a 1 in bit position `i`. After 24 hours, read off which rats died — that pattern of 1s and 0s **is the binary index of the poisoned bottle.** Ten rats encode up to 1,024 possibilities, so one round identifies the culprit exactly.

## Part 4 — Lesson Quiz

**AZ1.** Any three of: **constant volatility** (real vol varies and clusters — the smile/skew); **continuous paths / no jumps** (markets gap); **normally distributed returns** (real returns are fat-tailed and negatively skewed); **frictionless, continuous hedging** (transaction costs, discrete re-hedging); **constant rates / no dividends**.

**AZ2.** The **volatility smile/skew** — different strikes trading at different implied vols. Under constant volatility they'd all be equal, so the curve is direct proof the assumption fails.

**AZ3.** Jumps **fatten the tails** (assign realistic probability to large sudden moves) and **generate/steepen the implied-vol skew**, since options that pay off in those tail scenarios become worth more than a pure diffusion implies.

**AZ4.** As a **quoting convention and price⇄vol translator**, not a literal truth: they convert prices to implied vols and manage the full **volatility surface** (across strike and expiry) to capture the corrections BS omits, reaching for richer models (local/stochastic vol, jump-diffusion) for exotics and stress-testing for tail risk.

**AZ5.** Because returns have **fat tails and jumps**: you collect small, steady premium most of the time, but a rare crash produces a loss **far larger** than all that accumulated income (a highly negatively-skewed P&L). Levered, this is a blow-up waiting to happen — the risk lives in exactly the tail events the Gaussian model underweights.

---

*Tomorrow (Day 15): the **final comprehensive review** — the whole model end to end, plus the big cumulative quiz that ties Days 1–15 together.*
