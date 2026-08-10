# Day 4 — 2026-08-07

Work top-to-bottom. **Don't scroll to the Answers section** until you've attempted everything.

---

## Part 1 — Probability & Expected Value (5 questions)

**Q1. Distinct faces.**
You roll a fair six-sided die 6 times. What is the expected number of *distinct* faces you see?

**Q2. The positive test.**
A disease affects 1% of a population. A test has 99% sensitivity (correctly flags 99% of sick people) and 99% specificity (correctly clears 99% of healthy people). Someone tests positive. What is the probability they actually have the disease?

**Q3. Deciding game.**
Two equally-matched teams play a best-of-three series (first to 2 wins). What is the probability the series goes to a third, deciding game?

**Q4. Even money.**
A fair die is rolled. If it lands on an *even* number you're paid that many dollars; if *odd*, you're paid nothing. What is the fair value of this game?

**Q5. First to roll a six.**
Two players alternate rolling a fair die; the first to roll a 6 wins. What is the probability that the player who rolls *first* wins?

---

## Part 2 — Brainteaser

**The fork in the road.**
You reach a fork: one path leads to freedom, the other to doom. Two guards stand there — one *always* tells the truth, one *always* lies — but you don't know which is which. You may ask **one** guard **one** yes/no question. What do you ask to guarantee you pick the path to freedom?

---

## Part 3 — Black-Scholes Lesson

### Day 4: The Black-Scholes formula — and what `d1` and `d2` mean

Everything so far — payoffs (Day 1), the lognormal distribution (Day 2), risk-neutral valuation (Day 3) — collapses into one closed-form equation. Here it is.

**The formula (European call, no dividends):**

> **C = S · N(d1) − K · e^(−rT) · N(d2)**

where

> **d1 = [ ln(S/K) + (r + σ²/2)·T ] / (σ·√T)**
> **d2 = d1 − σ·√T**

and the inputs are:

| Symbol | Meaning |
|--------|---------|
| `S` | current stock price |
| `K` | strike price |
| `r` | risk-free interest rate (continuous) |
| `T` | time to expiry, in years |
| `σ` | volatility of the stock's returns |
| `N(·)` | the **standard normal CDF** — N(x) = probability a standard normal draw is ≤ x |

**Reading the formula in two pieces.**
It has the shape *"(what you get) − (what you pay)"*, each weighted by a probability:

- **`S · N(d1)`** — the present value of *receiving the stock*, if you end up exercising. `N(d1)` is also the option's **delta** (Day 7) — how many shares the call currently behaves like.
- **`K · e^(−rT) · N(d2)`** — the present value of *paying the strike*. `e^(−rT)` discounts the strike `K` back to today, and `N(d2)` is the **risk-neutral probability the call finishes in the money** (i.e. that you actually pay the strike and exercise).

So in words: *the call is worth the discounted, probability-weighted value of the stock you'd receive, minus the discounted, probability-weighted strike you'd pay.*

**What `d1` and `d2` are.**
Both are "how many standard deviations in-the-money" measures for the log of the stock, under the risk-neutral distribution:

- `σ·√T` is the **total volatility over the option's life** — the standard deviation of the log return from now to expiry. (There's the √time rule from Day 2 again.)
- `d2` measures how far the *typical* ending log-price sits above `ln(K)`, in those standard-deviation units → `N(d2)` = P(finish above strike).
- `d1 = d2 + σ√T` carries an extra `σ√T` bump because `S·N(d1)` weights by the *stock's value in the states where you exercise*, not just the bare probability — the bigger up-moves count for more.
- The `σ²/2` inside `d1` is the **lognormal adjustment**: the mean of the log differs from the log of the mean, and this term corrects for it.

**Worked example.**
`S = 100, K = 100, r = 5% (0.05), σ = 20% (0.20), T = 1 year.`

- `d1 = [ ln(100/100) + (0.05 + 0.20²/2)·1 ] / (0.20·√1) = [ 0 + (0.05 + 0.02) ] / 0.20 = 0.07 / 0.20 = 0.35`
- `d2 = 0.35 − 0.20·1 = 0.15`
- `N(0.35) ≈ 0.6368`, `N(0.15) ≈ 0.5596`
- `C = 100·(0.6368) − 100·e^(−0.05)·(0.5596) = 63.68 − 95.12·0.5596 = 63.68 − 53.23 ≈ **$10.45**`

So an at-the-money 1-year call on a $100 stock with 20% vol and a 5% rate is worth about **$10.45**. Sanity checks that should feel right: raise `σ` and the call gets more expensive; raise `T` and it gets more expensive; push `S` far above `K` and both `N(·)` → 1, so `C → S − K·e^(−rT)` (deep-ITM calls behave like the stock minus the discounted strike).

**Key intuition to carry forward:** the formula is not magic — it's the Day-3 risk-neutral expectation (discounted expected payoff) written out for a lognormal stock. `N(d2)` is *"how likely am I to exercise,"* `N(d1)` is *"how much stock exposure do I effectively hold,"* and the whole thing is *get-the-stock minus pay-the-strike*, each in present-value, probability-weighted terms.

---

## Part 4 — Lesson Quiz (5 questions)

**QZ1.** Write out the Black-Scholes call formula, and say what the function `N(·)` is.

**QZ2.** What is the role of the `e^(−rT)` factor in the formula?

**QZ3.** What is the relationship between `d1` and `d2`?

**QZ4.** In risk-neutral terms, what does `N(d2)` represent?

**QZ5.** Compute `d1` and `d2` for `S = 50, K = 50, r = 0, σ = 0.20, T = 1`.

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Part 1 — Probability & EV

**A1 — ≈ 3.99 faces.**
By linearity of expectation, each of the 6 faces appears in your 6 rolls with probability `1 − (5/6)⁶`. So expected distinct faces = `6·[1 − (5/6)⁶] = 6·[1 − 0.3349] = 6·0.6651 ≈ **3.99**`.

**A2 — 50%.**
Bayes with a base rate. Out of 10,000 people: 100 sick (99 test positive), 9,900 healthy (99 falsely test positive). Positives = 99 + 99 = 198, of which 99 are truly sick → `99/198 = **50%**`. The lesson: even a "99% accurate" test is only a coin flip when the condition is rare — base rates dominate.

**A3 — 1/2.**
The series reaches game 3 exactly when the teams split the first two games: `P = P(WL) + P(LW) = ¼ + ¼ = **½**`.

**A4 — $2.**
Only even faces pay: `(1/6)(2) + (1/6)(4) + (1/6)(6) = (2 + 4 + 6)/6 = 12/6 = **$2**`.

**A5 — 6/11.**
Let `p = 1/6`. The first player wins on roll 1, or if both miss and it "resets": `P = p / [1 − (1−p)²] = (1/6) / [1 − (5/6)²] = (1/6) / (11/36) = (1/6)(36/11) = **6/11 ≈ 0.545**`. Going first is worth a small edge.

## Part 2 — Brainteaser

**Ask about what the *other* guard would say.**
Point at one path and ask either guard: *"Would the **other** guard tell me this path leads to freedom?"* Then take the **opposite** path of whatever answer you get.
- If you happen to ask the **truth-teller**, they truthfully report the liar's lie → the answer is inverted.
- If you ask the **liar**, they lie about the truth-teller's honest answer → also inverted.
Either way the reply is the *reverse* of the truth, so doing the opposite of what they say leads to freedom. The self-referencing question cancels out not knowing who's who.

## Part 4 — Lesson Quiz

**AZ1.** `C = S·N(d1) − K·e^(−rT)·N(d2)`, where `N(·)` is the **standard normal cumulative distribution function** — `N(x)` is the probability that a standard normal random variable is ≤ `x`.

**AZ2.** `e^(−rT)` **discounts the strike `K` to its present value** — the strike is only paid at expiry, so it's worth less than `K` today.

**AZ3.** `d2 = d1 − σ·√T` (they differ by one "total volatility over the life" unit).

**AZ4.** `N(d2)` is the **risk-neutral probability that the call finishes in the money** (stock ends above the strike, so the option is exercised).

**AZ5.** `d1 = [ ln(1) + (0 + 0.20²/2)·1 ] / (0.20·√1) = (0 + 0.02)/0.20 = **0.10**`; `d2 = 0.10 − 0.20 = **−0.10**`.

---

*Tomorrow (Day 5): pricing puts, and the elegant no-arbitrage link between calls and puts — put-call parity.*
