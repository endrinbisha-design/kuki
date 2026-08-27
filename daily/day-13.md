# Day 13 — 2026-08-16

Work top-to-bottom. **Don't scroll to the Answers section** until you've attempted everything.

---

## Part 1 — Probability & Expected Value (5 questions)

**Q1. Counting HH.**
You flip a fair coin 100 times. What is the expected number of times the pattern **HH** appears, counting overlaps (so HHH counts as two)?

**Q2. Both even.**
You roll two fair dice. Given that their sum is even, what is the probability that *both* dice show even numbers?

**Q3. Shared birth month.**
In a group of 5 people, what is the probability that at least two share the same birth *month* (assume 12 equally likely months)?

**Q4. Market-maker's take.**
A market-maker quotes a stock **100 bid / 101 ask**; fair value is 100.5. Buyers and sellers arrive equally often, one share each, always trading against the quote. Over 100 trades, what is the expected profit?

**Q5. Breaking a stick.**
A stick of length 1 is broken at two independently, uniformly random points. What is the probability the three resulting pieces can form a triangle?

---

## Part 2 — Brainteaser

**The hat line.**
100 people stand in a single-file line, each wearing a red or blue hat. Each person can see the hats of everyone *in front* of them but not their own or those behind. Starting from the **back** of the line and moving forward, each person must say a single word — "red" or "blue" — guessing their own hat color; everyone hears every guess. They may agree on a strategy beforehand. What strategy **guarantees** the most correct guesses, and how many can they always get right?

---

## Part 3 — Black-Scholes Lesson

### Day 13: Practical hedging — delta-gamma hedging and P&L attribution

We've met the Greeks one at a time. Now we run a *position* with them — how a desk actually neutralizes risk and explains its daily P&L.

**1. Recap: delta-hedging isn't enough.**
Shorting `Δ` shares against an option kills first-order directional risk *for an instant*. But **gamma** means delta drifts as the stock moves, so a delta-hedge is only momentarily correct — you must **re-hedge**, and between re-hedges you carry gamma risk. For a book with large gamma, that residual can dominate.

**2. Why you can't hedge gamma with stock.**
Stock is **linear** — its payoff is a straight line, so its gamma (curvature) is **zero**. No amount of stock adds or removes convexity. **To offset gamma you need another *convex* instrument — i.e. another option.** This is the key structural fact.

**3. Delta-gamma hedging — two Greeks, two instruments.**
To be *both* delta- and gamma-neutral you need **at least two hedging instruments**:
1. **Use another option to cancel gamma.** Pick a traded option and hold enough of it that your net gamma = 0. (Say you're short a book with gamma −G; buy `n` of a hedging option with gamma `g` each so that `n·g = G`.)
2. **Then use stock to clean up the residual delta.** The gamma-hedging option changes your net delta, so finish by trading shares until net delta = 0.

Order matters: neutralize gamma *first* (only options can), then delta (stock is free to do this without disturbing gamma). The same logic extends to vega — add more options to zero out vega, then re-solve delta.

**4. P&L attribution — the "Greek explain."** ⭐
Over a small step, an option/portfolio's value change decomposes almost exactly into its Greeks:

> **ΔV ≈ Δ·ΔS + ½·Γ·(ΔS)² + Θ·Δt + Vega·Δσ + ρ·Δr**

Every term is a *source* of the day's P&L: direction (delta), convexity (gamma), time decay (theta), vol repricing (vega), rates (rho). Desks compute this daily to "explain" P&L — if the actual P&L and the Greek-predicted P&L diverge a lot, something is mismodeled or mismarked ("unexplained P&L" is a red flag).

**5. The gamma–theta breakeven — where it all connects.**
For a **delta-hedged** position, the delta term is ~0 and (holding vol/rates fixed) the daily P&L is essentially:

> **daily P&L ≈ ½·Γ·(ΔS)² + Θ·Δt**

The gamma term is positive (for a long option) and grows with the *square* of the move; theta is a steady negative drip. Set them equal to find the **breakeven daily move** — the size of move that exactly pays for one day's theta:

`½·Γ·(ΔS)² = −Θ·Δt`.

- Move **more** than breakeven → long-gamma wins (realized > implied).
- Move **less** → theta bleed wins (realized < implied).

This is Day 9's gamma-vs-theta made quantitative, and it's *the same thing* as implied-vs-realized vol (Day 12), just expressed as a daily price move.

**6. Worked example.**
You're **long** a delta-hedged option with **gamma = 0.10** per share and **theta = −$0.10/day**. Breakeven move:
`½·0.10·(ΔS)² = 0.10 → 0.05·(ΔS)² = 0.10 → (ΔS)² = 2 → ΔS ≈ **$1.41**`.
So if the stock's *typical daily move* exceeds about $1.41, your gamma re-hedging (buy low / sell high) earns back more than the 10-cent daily theta and you profit; if it's calmer than that, you bleed. Every long-gamma trade has such a daily breakeven baked in.

**7. The real-world frictions.**
Re-hedging **more often** cuts risk but racks up **transaction costs** (spreads, commissions, market impact). Hedge too rarely and gamma risk bites; hedge too often and costs eat the edge. Choosing the re-hedge frequency — often tied to how far delta has drifted — is a craft in itself.

**Key intuition to carry forward:** running an options book is *managing the Greeks as a portfolio*: cancel gamma (and vega) with other options, cancel delta with stock, and watch the daily gamma-vs-theta race, which is nothing but realized-vs-implied vol priced as a breakeven move. P&L attribution is how you check that the position is behaving the way the Greeks say it should.

---

## Part 4 — Lesson Quiz (5 questions)

**QZ1.** Why can't you hedge an option's gamma by trading the underlying stock?

**QZ2.** To make a position both delta-neutral *and* gamma-neutral, how many hedging instruments do you need at minimum, and what kinds?

**QZ3.** Write the Greek P&L attribution for a small step in an option/portfolio's value.

**QZ4.** For a delta-hedged position (vol and rates held fixed), what is the approximate daily P&L, and what defines the "breakeven" daily move?

**QZ5.** A delta-hedged long option has gamma 0.08 and theta −$0.16/day. What size daily stock move breaks even?

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Part 1 — Probability & EV

**A1 — 24.75.**
There are 99 adjacent pairs of positions; each is "HH" with probability `¼`. By linearity, expected count = `99 × ¼ = **24.75**`. (Overlaps don't break linearity — expectation adds regardless of dependence.)

**A2 — 1/2.**
An even sum means both dice are even or both odd: `3·3 + 3·3 = 18` outcomes. Both even is `3·3 = 9`. `P(both even | even sum) = 9/18 = **1/2**`.

**A3 — ≈ 61.8%.**
Complement (all different months): `(12·11·10·9·8)/12⁵ = 95,040/248,832 ≈ 0.382`. So `P(at least two match) = 1 − 0.382 = **0.618 ≈ 61.8%**` — a birthday-paradox-style surprise even with just 5 people and 12 months.

**A4 — $50.**
Every trade — whether the customer buys at 101 or sells at 100 — earns the maker the **half-spread of $0.50** relative to fair value (101 − 100.5, or 100.5 − 100). Over 100 trades: `100 × $0.50 = **$50**`.

**A5 — 1/4.**
With break points `x, y` uniform on [0,1], the three pieces form a triangle iff no piece exceeds ½ (each piece must be less than the sum of the other two). That region has area **1/4** of the unit square. So the probability is **1/4**.

## Part 2 — Brainteaser

**99 guaranteed, using parity.**
Before starting, they agree that **"red" means an odd number of red hats, "blue" means even** (a parity code). The **last person** (at the back, who sees all 99 hats ahead) counts the red hats in front and announces the parity — they're sacrificing themselves (a 50/50 shot at their own hat) to transmit one bit.
Now the **99th** person sees the 98 ahead, knows the total parity announced, and can deduce their own hat from the difference. After they answer, the **98th** person knows the original parity *and* the 99th person's hat, so they can subtract both and deduce theirs — and so on down the line. Every person from the 99th forward gets it **right with certainty**: **99 guaranteed** (the 100th is right half the time). The trick is encoding global parity in one guess.

## Part 4 — Lesson Quiz

**AZ1.** Because stock is **linear** — its payoff is a straight line, so it has **zero gamma** (no curvature). Trading it changes your delta but adds no convexity, so it can't offset an option's gamma. You need another **convex** instrument — i.e. an option.

**AZ2.** At least **two** instruments: **another option** to cancel the gamma (only a convex instrument can), and then **stock** to neutralize the residual delta the gamma-hedge introduced.

**AZ3.** `ΔV ≈ Δ·ΔS + ½·Γ·(ΔS)² + Θ·Δt + Vega·Δσ + ρ·Δr` — direction, convexity, time decay, vol, and rate contributions.

**AZ4.** `daily P&L ≈ ½·Γ·(ΔS)² + Θ·Δt`. The **breakeven move** is the `ΔS` where the gamma gain exactly offsets one day's theta: `½·Γ·(ΔS)² = −Θ·Δt`. Bigger moves favor long gamma; smaller moves favor theta.

**AZ5.** `½·0.08·(ΔS)² = 0.16 → 0.04·(ΔS)² = 0.16 → (ΔS)² = 4 → ΔS = **$2.00**` daily move to break even.

---

*Tomorrow (Day 14): **the limits of Black-Scholes** — where the assumptions break (fat tails, jumps, stochastic vol) and how traders cope.*
