# Day 3 — 2026-08-06  ·  ⭐ Big cumulative quiz day (Days 1–3)

Work top-to-bottom. **Don't scroll to the Answers section** until you've attempted everything. Today's Part 4 is a **bigger review quiz** covering Days 1–3, not just today's lesson.

---

## Part 1 — Probability & Expected Value (5 questions)

**Q1. The Monty Hall problem.**
Three doors; behind one is a car, behind the other two are goats. You pick Door 1. The host — who knows what's behind every door — opens Door 3, revealing a goat, and offers you the chance to switch to Door 2. Should you switch, and what is your probability of winning the car if you do?

**Q2. Position of the first ace.**
A standard 52-card deck is shuffled and you flip cards one at a time. On average, at what position does the *first ace* appear?

**Q3. More heads than tails.**
You flip a fair coin 3 times. What is the probability you get strictly more heads than tails?

**Q4. Draw, then maybe re-draw.**
A number `X` is drawn uniformly from [0, 1]. You may keep it, or discard it and draw a second number `Y` (also uniform on [0, 1]) which you must then keep. Playing optimally, what is the expected value of the number you end with?

**Q5. Hit rate.**
A trader is correct on 60% of her calls, independently. She makes 5 calls today. What is the probability she is right on *exactly 3* of them?

---

## Part 2 — Brainteaser

**Three switches, one bulb.**
Outside a closed room are three on/off light switches; exactly one controls a single incandescent bulb inside the room. The door is shut and you can't see the bulb from outside. You may flip the switches as much as you like, but you may **enter the room only once**. How do you determine which switch controls the bulb?

---

## Part 3 — Black-Scholes Lesson

### Day 3: No-arbitrage, replication, and the risk-neutral idea

We now answer the question we've been circling: *how does the market actually pin down an option's price?* The answer is not "guess the probability the stock goes up." It's **hedging** — and it's the single most important idea underneath Black-Scholes.

**1. The no-arbitrage principle.**
*If two portfolios produce identical payoffs in every possible future state of the world, they must cost the same today.* If they didn't, you'd buy the cheap one, sell the expensive one, pocket the difference, and have zero net exposure — a risk-free money machine ("arbitrage"). Markets stamp those out fast, so we price *as if* none exist.

**2. Replication — build the option out of stock and cash.**
Here's the trick: an option's payoff can be **reproduced** by a cleverly chosen mix of (a) some shares of the stock and (b) borrowing or lending cash at the risk-free rate. If a portfolio of stock + cash pays *exactly* what the option pays in every future state, then by no-arbitrage the option must cost exactly what that portfolio costs. **We don't need to know the odds — we just need to match the payoffs.**

**3. Worked example — one-step binomial.**
Stock is $100 today. In one period it either goes **up to $120** or **down to $90**. Consider a call with **strike $105**. Take the risk-free rate `r = 0` for simplicity.

Payoffs at expiry:
- Up ($120): call pays `max(120 − 105, 0) = $15`.
- Down ($90): call pays `max(90 − 105, 0) = $0`.

*Find the replicating portfolio.* Hold `Δ` shares plus borrow `B` dollars. The **hedge ratio** is:
> `Δ = (payoff_up − payoff_down) / (S_up − S_down) = (15 − 0) / (120 − 90) = 15/30 = 0.5 shares.`

Solve for the borrowing so payoffs match:
- Up: `0.5 × 120 − B = 15` → `60 − B = 15` → `B = 45`.
- Down check: `0.5 × 90 − 45 = 45 − 45 = 0` ✓.

*Cost today* = value of the shares − the cash you borrowed = `0.5 × 100 − 45 = 50 − 45 = $5`.
So the call is worth **$5**. Not because we guessed the up-probability — but because $5 is what it costs to *build* the option's payoff.

**4. Risk-neutral valuation — the shortcut, and why μ vanishes.**
There's an elegant shortcut that gives the same $5. Define the **risk-neutral probability** `q` — the up-probability that would make the stock's expected value grow at the risk-free rate:
> `q = (S_today − S_down) / (S_up − S_down) = (100 − 90) / (120 − 90) = 10/30 = 1/3.`

Then price the option as the **discounted expected payoff under `q`**:
> `Call = q · payoff_up + (1−q) · payoff_down = (1/3)(15) + (2/3)(0) = $5.` ✓

Notice what we **never used**: the *real* probability of an up-move, and the stock's expected return `μ`. That's the payoff of yesterday's foreshadow — **the drift `μ` drops out**. Under the risk-neutral measure, every asset drifts at `r`, and the option's price is just the discounted expected payoff in that made-up world. Two traders who violently disagree about `μ` still compute the *same* option price.

**5. From one step to Black-Scholes.**
Chop time into more and more tiny binomial up/down steps. In the limit, the stock's ending price becomes **lognormal** (Day 2), and the discounted risk-neutral expected payoff becomes a clean closed-form expression — **the Black-Scholes formula**. The `Δ` we computed becomes the option's **delta**, and the "keep re-hedging as the stock moves" idea becomes **dynamic hedging**. That formula is Day 4.

**Key intuition to carry forward:** an option's price = the **cost of the hedge that replicates it** = its **discounted expected payoff in a risk-neutral world** where everything grows at `r`. Probabilities of direction never enter; only volatility and the structure of payoffs do.

---

## Part 4 — ⭐ BIG CUMULATIVE QUIZ (Days 1–3, 10 questions)

**BQ1.** Define *intrinsic value* and *time value*. A $60-strike call trades at $7 while the stock is $64 — split the $7 into the two components.

**BQ2.** A put has strike $50 and the stock is at $45. Is it in- or out-of-the-money? What is its intrinsic value?

**BQ3.** A stock has a daily volatility of 2%. Approximately what is its annualized volatility (252 trading days)?

**BQ4.** Why can a lognormally-distributed stock price never go negative, and why is the distribution right-skewed?

**BQ5.** In the GBM equation `dS/S = μ dt + σ dW`, which term does option pricing effectively *ignore*, and what does it get replaced by?

**BQ6.** State the no-arbitrage principle in one sentence.

**BQ7.** One-step binomial: stock $100 goes to $110 or $95; a call has strike $100; `r = 0`. Find the risk-neutral probability of an up-move and the call's fair value.

**BQ8.** In that same binomial, what is the option's **delta** (hedge ratio), and what does it represent?

**BQ9.** Two traders strongly disagree about whether a stock will rise or fall, but agree on its volatility. Can they still agree on the option's fair price? Why or why not?

**BQ10.** Two calls are identical except one expires next week and one in six months. Which has more *time value*, and what's the intuition?

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Part 1 — Probability & EV

**A1 — Switch; you win 2/3 of the time.**
Your original pick was right with probability 1/3, and that doesn't change when the host (who deliberately avoids the car) opens a goat door. So the car is behind the *other* unopened door with probability **2/3**. Switching doubles your win rate from 1/3 to 2/3.

**A2 — Position 10.6.**
The 4 aces split the other 48 cards into 5 gaps of equal expected size. Expected position of the first ace = `(52 + 1) / (4 + 1) = 53/5 = **10.6**`. (General rule: first of `k` successes among `n` items sits at expected position `(n+1)/(k+1)`.)

**A3 — 1/2.**
With 3 flips a tie is impossible, so by symmetry P(more heads) = P(more tails) = ½. Check: P(2 or 3 heads) = `[C(3,2) + C(3,3)]/8 = (3 + 1)/8 = 4/8 = **1/2**`.

**A4 — 5/8 = 0.625.**
Re-draw only when your first number is below what a fresh draw averages, i.e. when `X < 0.5` (since `E[Y] = 0.5`). Then:
`EV = P(X ≥ ½)·E[X | X ≥ ½] + P(X < ½)·E[Y] = ½·(0.75) + ½·(0.5) = 0.375 + 0.25 = **0.625**`.

**A5 — ≈ 34.6%.**
Binomial: `C(5,3)·(0.6)³·(0.4)² = 10 · 0.216 · 0.16 = **0.3456**`.

## Part 2 — Brainteaser

**Three switches — use heat as a third state.**
Turn switch **1 ON** and leave it for a few minutes. Then turn switch **1 OFF**, turn switch **2 ON**, and immediately enter the room.
- Bulb **on** → switch **2**.
- Bulb **off but warm** → switch **1** (it was on long enough to heat the filament).
- Bulb **off and cold** → switch **3**.
The trick is that the bulb carries *two* bits of information — light *and* temperature — so a single visit distinguishes three switches.

## Part 4 — Big Cumulative Quiz (Days 1–3)

**BAQ1.** *Intrinsic value* = value if exercised now = `max(S − K, 0)` for a call; *time value* = premium − intrinsic value (what you pay for remaining time/uncertainty). Here intrinsic = `max(64 − 60, 0) = $4`, so time value = `7 − 4 = $3`.

**BAQ2.** Stock $45 < strike $50, so the put is **in-the-money**. Intrinsic value = `max(50 − 45, 0) = $5`.

**BAQ3.** `2% × √252 ≈ 2% × 15.87 ≈ **31.7%**` (≈ 32%).

**BAQ4.** Lognormal values live on (0, ∞) — the price is `e^(something)`, which is always positive — so it can't cross zero. It's right-skewed because the stock's upside is unbounded (it can multiply many times over) while its downside stops at zero, producing a long right tail.

**BAQ5.** It ignores the **drift `μ`** (the real expected return). Pricing replaces it with the **risk-free rate `r`** via risk-neutral valuation.

**BAQ6.** *If two portfolios have identical payoffs in every future state, they must have the same price today* — otherwise a risk-free arbitrage profit exists.

**BAQ7.** `q = (100 − 95)/(110 − 95) = 5/15 = 1/3`. Payoffs: up = `max(110 − 100,0) = $10`, down = `$0`. Value = `(1/3)(10) + (2/3)(0) = $10/3 ≈ **$3.33**`.

**BAQ8.** `Δ = (payoff_up − payoff_down)/(S_up − S_down) = (10 − 0)/(110 − 95) = 10/15 ≈ **0.667 shares**`. It's the number of shares you hold to **replicate/hedge** the option — how much stock exposure the option currently behaves like.

**BAQ9.** **Yes.** An option's price depends on **volatility** (`σ`) and the payoff structure, not on the *direction* (`μ`) of the stock. Risk-neutral pricing removes `μ` entirely, so two people who disagree about direction but agree on volatility compute the same fair price.

**BAQ10.** The **six-month** call has more time value. Both share the same intrinsic value, but more time means more chances for a favorable move (and more accumulated volatility, `σ√T`), which the market charges for.

---

*Tomorrow (Day 4): the Black-Scholes formula itself — writing down the call-price equation and defining `d1` and `d2`.*
