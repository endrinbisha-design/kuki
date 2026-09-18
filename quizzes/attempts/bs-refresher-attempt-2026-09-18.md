# Black-Scholes Refresher Test — Graded Attempt

**Date:** 2026-09-18 · **Format:** live interview (one question at a time, no answer key visible)
**Score: 20.75 / 24 ≈ 86% — interview-ready, with a few precise gaps to firm up.**

---

## Per-question grades

| Q | Topic | Score | Note |
|--:|-------|:-----:|------|
| 1 | Call/put rights & payoffs | 1.0 | Correct; payoffs `max(S−K,0)`, `max(K−S,0)`. |
| 2 | Intrinsic vs time value + split | 1.0 | $4 intrinsic / $4.20 time. ✓ |
| 3 | Two reasons for lognormal returns | 1.0 | Can't go ≤0; percentages more meaningful than dollars. ✓ |
| 4 | Annualize daily vol | 1.0 | 1.5%·√252 ≈ 24%. ✓ |
| 5 | Four BS assumptions | 1.0 | Gave several valid ones. ✓ |
| 6 | Moneyness at S=47 | 1.0 | Call OTM, put ITM, intrinsic $3. ✓ |
| 7 | BS formula + d1/d2 + N(d1)/N(d2) | 0.5 | Formula ✓ (+dividend bonus), but **d1/d2 formulas not given** and **N(d1)/N(d2) meanings reversed/muddled**. |
| 8 | Why μ drops out | 0.0 | Said "replaced by volatility." It's replaced by the **risk-free rate r** (risk-neutral/hedging removes drift). |
| 9 | Replication / no-arbitrage | 1.0 | Clear and correct. ✓ |
| 10 | Risk-neutral valuation (one line) | 0.5 | Got "everything drifts at r," but missed "price = **discounted expected payoff** under that measure." |
| 11 | Put-call parity + solve P | 1.0 | Parity ✓, P = $6. ✓ |
| 12 | Compute d1/d2 + meaning | 0.25 | Computation skipped (by choice); meaning again conflated N(d1) with N(d2). |
| 13 | Five Greeks → derivatives | 1.0 | All five correct. ✓ |
| 14 | Call/put delta + ranges | 0.5 | Call `N(d1)` ✓ and ranges ✓, but **put delta = N(d1)−1 = −N(−d1)**, not `N(−d1)` (sign). |
| 15 | Where gamma/theta vs vega peak | 1.0 | ATM near-expiry vs ATM long-dated. ✓ |
| 16 | Gamma-theta trade-off | 1.0 | Long gamma → negative theta; pays off if realized > implied. ✓ |
| 17 | New delta after $3 move | 1.0 | 0.67. ✓ |
| 18 | Vega sign for long put + why | 1.0 | Positive; wider distribution helps both. ✓ |
| 19 | Rho signs + dividends | 1.0 | Call +, put −; dividends lower calls / raise puts. ✓ |
| 20 | Define implied vol | 1.0 | Market's forecast priced into options. ✓ |
| 21 | Equity skew + reason | 1.0 | Low strikes higher IV; downside hedging demand. ✓ |
| 22 | Implied vs realized + Greeks | 1.0 | Gamma→realized, vega→implied. ✓ |
| 23 | Delta- & gamma-neutral | 1.0 | Stock is linear; need another option for gamma, then adjust delta. ✓ |
| 24 | A failed assumption + consequence | 1.0 | Thin vs fat tails → skew / more frequent crashes. ✓ |

**Total: 20.75 / 24.**

---

## The four things to firm up (highest priority first)

1. **Why μ drops out (Q8).** Not "replaced by volatility." Under **risk-neutral valuation** (built on the replication/hedging argument you nailed in Q9), the delta-hedge cancels exposure to the stock's actual drift, so pricing happens in a world where every asset grows at the **risk-free rate r**. μ is replaced by **r**, not σ. σ is a separate, independent input.

2. **N(d1) vs N(d2) — keep them straight (Q7, Q12).** This is *the* classic follow-up, so lock it in:
   - **N(d2) = the risk-neutral probability the option is exercised** (finishes in the money). It multiplies the strike term because you only pay `K` when you exercise.
   - **N(d1) = the option's delta** (and a *stock-value-weighted* probability). It's always **≥ N(d2)**. It is *not* simply "the probability of finishing ITM."

3. **Put delta sign (Q14).** Put delta `= N(d1) − 1`, equivalently `−N(−d1)` — a **negative** number in (−1, 0). You wrote `N(−d1)` (positive), though your stated range (−1 to 0) was right.

4. **Risk-neutral valuation, full sentence (Q10).** "An option's price = the **discounted expected value of its payoff under the risk-neutral measure**, in which all assets drift at the risk-free rate."

**Minor:** be able to write the `d1`/`d2` formulas and grind a `d1`/`d2` computation cold (Q7, Q12) — those show up as "price this in your head" prompts.

**Bottom line:** strong command of the Greeks, parity, skew, and hedging intuition. The gaps are all in the *pricing-theory core* — the μ→r logic and the N(d1)/N(d2) distinction. Tighten those two and you're at a confident 23–24/24.
