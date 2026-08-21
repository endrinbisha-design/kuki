# Day 10 — 2026-08-13

Work top-to-bottom. **Don't scroll to the Answers section** until you've attempted everything.

---

## Part 1 — Probability & Expected Value (5 questions)

**Q1. Sum exceeds 10.**
You roll two fair dice. What is the probability their sum is *greater than* 10?

**Q2. Defective from a line.**
Two machines make widgets: Machine A produces 60% of output with a 2% defect rate; Machine B produces 40% with a 5% defect rate. A randomly chosen widget is defective. What is the probability it came from Machine B?

**Q3. Runs of three.**
You flip a fair coin 3 times. What is the probability that all three flips come up the same (all heads or all tails)?

**Q4. Insurance EV.**
A $1,000 gadget has a 3% chance of breaking within a year (total loss). An extended warranty costs $45 and would fully replace it. From a pure expected-value standpoint, is the warranty worth buying?

**Q5. Expected minimum.**
You roll two fair dice and take the *smaller* of the two values (if they tie, that value). What is the expected result?

---

## Part 2 — Brainteaser

**The 100 lockers.**
A hallway has 100 lockers, all initially closed, and 100 students. Student 1 toggles every locker (opens them all). Student 2 toggles every 2nd locker (2, 4, 6, …). Student 3 toggles every 3rd locker (3, 6, 9, …), and so on through Student 100. After all 100 students have gone, **which lockers are left open**?

---

## Part 3 — Black-Scholes Lesson

### Day 10: Vega — the sensitivity to volatility

Delta, gamma, and theta are about the stock and time. **Vega** is different: it measures sensitivity to **volatility itself** — the one input that isn't directly observable, and the one options traders are really trading.

**1. Definition.**
**Vega = ∂(option price) / ∂σ** — how much the option's value changes when volatility changes by **one percentage point** (e.g. σ from 20% to 21%). It's quoted as *dollars per 1 vol point*.

- **Vega is positive for both long calls and long puts.** More volatility widens the distribution of future prices, and since option payoffs are one-sided (capped downside, open upside), a wider distribution is worth more — for calls *and* puts.
- (Strictly, "vega" isn't a Greek letter — but it's used universally alongside the others.)

**2. Where vega is largest.**
Vega peaks for **at-the-money options with a lot of time to expiry**. Intuition: long-dated ATM options have the most "distributional width" to gain or lose when σ moves, so their value is most sensitive to it. This is the mirror of gamma/theta, which peak for ATM options *near* expiry — **vega lives at the long end, gamma/theta at the short end.**

| | Peaks when… |
|---|---|
| **Gamma, |Theta|** | at-the-money, **near** expiry |
| **Vega** | at-the-money, **far** from expiry |

**3. Long vega vs. short vega.**
- **Long vega** (you own options): you *profit if implied volatility rises*, lose if it falls — independent of whether the stock actually moves yet. Buying options is a long-vol *and* long-gamma position.
- **Short vega** (you sold options): you profit if implied vol falls, lose if it spikes. Vol spikes usually accompany market crashes, so being short vega carries nasty tail risk (the "short vol" blow-up).

**4. Implied vs. realized — two different volatilities vega touches.**
Careful distinction that trips people up:
- **Realized volatility** is how much the stock *actually* moves — that's what your **gamma** P&L harvests (Day 9).
- **Implied volatility** is the σ the market has *priced into* the option — that's what **vega** exposes you to. A long option position is *long realized vol via gamma* and *long implied vol via vega* at the same time. You can lose on vega (implied drops) even in a week the stock moved a lot, and vice versa.

**5. Worked example.**
An option is priced at $10.45 with implied vol 20% and has **vega = 0.375** (i.e. $0.375 per vol point). If implied volatility jumps from **20% to 23%** (+3 points), the option's value rises by ≈ `0.375 × 3 = **$1.13**`, to about $11.58 — *with the stock unchanged.* That's a pure volatility repricing. If instead vol fell to 18% (−2 points), the option loses ≈ `0.375 × 2 = $0.75`.

**Key intuition to carry forward:** vega is the option's exposure to the *price of volatility*. It's why you can be right about a stock going nowhere and still lose money (implied vol fell), or make money on a quiet day (implied vol rose). When traders say they're "buying vol" or "selling vol," vega is the Greek they mean.

---

## Part 4 — Lesson Quiz (5 questions)

**QZ1.** Define vega — what does it measure, and in what units?

**QZ2.** Is vega positive or negative for a long call? For a long put? Why the same sign?

**QZ3.** For what moneyness and time-to-expiry is vega largest — and how does that contrast with gamma and theta?

**QZ4.** What's the difference between the volatility your *gamma* P&L depends on and the volatility your *vega* exposes you to?

**QZ5.** An option has vega 0.40. If implied volatility rises from 25% to 28% with the stock unchanged, approximately how much does the option's value change?

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Part 1 — Probability & EV

**A1 — 1/12.**
Sums greater than 10 are 11 and 12: 11 comes from (5,6),(6,5) → 2 ways; 12 from (6,6) → 1 way. `3/36 = **1/12 ≈ 0.083**`.

**A2 — 5/8.**
`P(defective) = 0.60·0.02 + 0.40·0.05 = 0.012 + 0.020 = 0.032`. `P(B | defective) = 0.020 / 0.032 = **0.625 = 5/8**`. (Machine B makes less but accounts for most defects.)

**A3 — 1/4.**
All same = all heads or all tails = `2/2³ = 2/8 = **1/4**`.

**A4 — Not worth it (EV −$15).**
Expected loss without warranty = `0.03 × $1,000 = $30`. The warranty costs **$45** to remove that $30 expected loss, so on pure EV it's `30 − 45 = **−$15**`. (Real people still buy it for risk aversion — the same "insurance premium" idea as A4 on Day 2.)

**A5 — 91/36 ≈ 2.53.**
For the minimum, `P(min = k) = (2(6−k) + 1)/36` — i.e. 11,9,7,5,3,1 out of 36 for k = 1…6. `E[min] = (1·11 + 2·9 + 3·7 + 4·5 + 5·3 + 6·1)/36 = (11+18+21+20+15+6)/36 = 91/36 ≈ **2.53**`. Check: `E[min] + E[max] = 91/36 + 161/36 = 252/36 = 7` ✓ (E[max] was Day 1).

## Part 2 — Brainteaser

**The perfect squares: 1, 4, 9, 16, 25, 36, 49, 64, 81, 100.**
Locker `n` is toggled once by each student whose number *divides* `n` — so it ends **open** iff `n` has an **odd number of divisors**. Divisors normally pair up (`d` with `n/d`), giving an even count — *unless* `n` is a **perfect square**, where one divisor (`√n`) pairs with itself. So exactly the perfect squares stay open: **1, 4, 9, 16, 25, 36, 49, 64, 81, 100** (10 lockers).

## Part 4 — Lesson Quiz

**AZ1.** Vega measures the change in an option's price for a **1-percentage-point change in volatility** (σ), quoted in dollars per vol point.

**AZ2.** **Positive for both** a long call and a long put. Higher volatility widens the future-price distribution, and because option payoffs are one-sided (limited downside, open-ended upside), that extra dispersion raises the value of calls *and* puts alike.

**AZ3.** Vega is largest for **at-the-money options with long time to expiry**. This contrasts with gamma and theta, which are largest for at-the-money options **near** expiry — vega lives at the long end of the calendar, gamma/theta at the short end.

**AZ4.** Gamma P&L depends on **realized** volatility — how much the stock actually moves. Vega exposes you to **implied** volatility — the σ the market has priced into the option. You can win on one and lose on the other in the same week.

**AZ5.** ≈ `0.40 × 3 = **$1.20**` increase (implied vol rose 3 points, stock unchanged).

---

*Tomorrow (Day 11): **Rho and dividends** — how interest rates and payouts feed into option prices, rounding out the Greeks.*
