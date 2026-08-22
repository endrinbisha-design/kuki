# Day 11 — 2026-08-14

Work top-to-bottom. **Don't scroll to the Answers section** until you've attempted everything.

---

## Part 1 — Probability & Expected Value (5 questions)

**Q1. Waiting for a five-or-six.**
You roll a fair die repeatedly until it shows a 5 or a 6. What is the expected number of rolls?

**Q2. Two children.**
A family has two children. Given that *at least one* of them is a boy, what is the probability that *both* are boys? (Assume each child is independently a boy or girl with probability ½.)

**Q3. Dealt a flush.**
You're dealt 5 cards from a standard deck. What is the probability the hand is a *flush* (all five the same suit, including straight flushes)?

**Q4. Roulette edge.**
On an American roulette wheel there are 38 slots, 18 of them red. You bet $1 on red, which pays even money ($1 profit on a win). What is your expected value per $1 bet?

**Q5. The two envelopes.**
Two sealed envelopes contain money; one holds exactly twice the other. You open one and find **$100**. A friend argues: "The other envelope is equally likely to hold $50 or $200, so its expected value is `½·50 + ½·200 = $125 > $100` — you should switch!" What, if anything, is wrong with this reasoning?

---

## Part 2 — Brainteaser

**Two eggs, 100 floors.**
You have two identical eggs and a 100-floor building. There is some floor `N` such that an egg dropped from floor `N` or higher breaks, and from any floor below `N` it survives (and can be reused). You want to determine `N`. Using a strategy that minimizes the number of drops **in the worst case**, how many drops do you need to guarantee finding `N`?

---

## Part 3 — Black-Scholes Lesson

### Day 11: Rho and dividends — rates and payouts

We finish the Greeks with the two inputs we've mostly held fixed: the **interest rate** (`r`, via **rho**) and **dividends** (`q`). Neither drives day-to-day option P&L as much as delta/gamma/vega, but both are essential for pricing correctly — and are common interview follow-ups.

**1. Rho — sensitivity to interest rates.**
**Rho (ρ) = ∂(option price)/∂r** — the change in value for a **1-percentage-point** change in the risk-free rate.

- **Calls have positive rho; puts have negative rho.**
- *Why?* Look at the formula: `C = S·N(d1) − K·e^(−rT)·N(d2)`. A higher `r` **shrinks `e^(−rT)`**, lowering the present value of the strike you'll pay → the **call is worth more**. Equivalently, a call lets you defer paying the strike and keep earning interest on that cash, which is more valuable when rates are high. By put-call parity, the same rate rise makes the **put worth less**.

*Worked example:* a call has rho ≈ 0.50. If rates rise from 5% to 6% (+1 point), the call gains ≈ `0.50 × 1 = **$0.50**`, all else equal.

Rho is usually the **least-watched Greek** — rates move slowly and in small steps — but it matters for **long-dated options** (LEAPS), where `T` is large and the `e^(−rT)` effect is big, and of course for interest-rate-sensitive products.

**2. Dividends — the stock "leaks" value the option holder misses.**
A stock that pays dividends transfers cash to *shareholders* — not to option holders. So holding a call means you miss those payouts, which **lowers the forward price** the option is really priced off of.

- **Dividends lower call values and raise put values.** (A call holder forgoes the dividend; a put holder benefits from the price drop on the ex-dividend date.)
- **How the formula adjusts:** for a continuous dividend yield `q`, replace `S` with `S·e^(−qT)` (discount the spot for dividends you won't receive). The drift inside `d1` becomes `(r − q + σ²/2)`:

> `d1 = [ ln(S/K) + (r − q + σ²/2)·T ] / (σ√T)`

For discrete dividends, instead subtract the present value of the expected dividends from `S` before pricing.

- **Put-call parity with dividends** becomes: `C − P = S·e^(−qT) − K·e^(−rT)` (or `S − PV(dividends) − K·e^(−rT)`).

**3. A practical consequence — early exercise.**
Dividends are the main reason it can be optimal to **exercise an American call early**, just *before* an ex-dividend date, to capture the dividend the option itself won't pay you. (European options can't be exercised early, so this is a purely American-style wrinkle — but it's a favorite interview point: "when would you ever exercise a call early?" → "right before a big dividend.")

**Key intuition to carry forward:** rates and dividends both act through the **forward price** of the stock. Higher rates push the forward *up* (good for calls, via rho); dividends push the forward *down* (bad for calls, good for puts). Neither is where a trader's daily risk lives, but getting them wrong misprices the option — especially long-dated ones and names with fat dividends.

---

## Part 4 — Lesson Quiz (5 questions)

**QZ1.** Define rho — what does it measure and in what units?

**QZ2.** What is the sign of rho for a call versus a put, and what's the intuition?

**QZ3.** How do dividends affect the value of calls versus puts, and why?

**QZ4.** How is the Black-Scholes `d1` adjusted for a continuous dividend yield `q`?

**QZ5.** Why is it sometimes optimal to exercise an *American* call early, and what event triggers it?

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Part 1 — Probability & EV

**A1 — 3 rolls.**
"5 or 6" has probability `2/6 = 1/3` per roll; the number of rolls to first success is geometric with mean `1/p = **3**`.

**A2 — 1/3.**
The equally likely two-child outcomes are BB, BG, GB, GG. Conditioning on "at least one boy" removes GG, leaving {BB, BG, GB}. Only BB has two boys → `**1/3**`. (Contrast: "the *older* child is a boy" would leave {BB, BG} → ½. The exact wording matters.)

**A3 — ≈ 0.198%.**
`4 suits × C(13,5) / C(52,5) = 4 × 1287 / 2,598,960 = 5148 / 2,598,960 ≈ **0.00198 ≈ 0.2%**` (this count includes the 40 straight/royal flushes).

**A4 — −$1/19 ≈ −$0.0526.**
`(18/38)(+1) + (20/38)(−1) = (18 − 20)/38 = −2/38 = −1/19 ≈ **−$0.053**`. That 5.26% expected loss is the American wheel's house edge (the two green zeros).

**A5 — The flaw is assuming a valid "50/50 over $50 vs $200" for the amount you saw.**
The switch argument secretly assumes that, whatever amount you observe, the other envelope is equally likely to be half or double it. That can't hold for *every* possible amount — it would require a uniform prior over all amounts of money, which doesn't exist (it can't be normalized). With any real prior over how much money was put in, seeing $100 shifts the odds of "the other is $50 vs $200" away from 50/50, and the expected gain from switching vanishes. By symmetry, before opening anything, neither envelope is better. **The $125 calculation is using probabilities that can't consistently exist.**

## Part 2 — Brainteaser

**14 drops.**
With two eggs you want the *first* egg's drop floors spaced so that each break leaves the second egg a short linear search, keeping the worst case flat. Drop the first egg from floor **14**, then **14+13=27**, then **39, 50, 60, 69, 77, 84, 90, 95, 99, 100** — the gaps shrink by one each time. If the first egg breaks after `k` jumps, you've used `k` drops and have at most `14 − k` floors to test one-by-one with the second egg, for a total of 14. Solving `x + (x−1) + … + 1 ≥ 100` gives `x(x+1)/2 ≥ 100 → x = 14`. **Worst case = 14 drops.**

## Part 4 — Lesson Quiz

**AZ1.** Rho measures the change in an option's price for a **1-percentage-point change in the risk-free interest rate** (`∂price/∂r`), quoted in dollars per rate point.

**AZ2.** **Call rho is positive; put rho is negative.** Higher rates lower the present value of the strike (`K·e^(−rT)`) — a call holder benefits from deferring that payment (worth more), while by parity the put is worth less.

**AZ3.** **Dividends lower call values and raise put values.** Dividends pay shareholders, not option holders, which reduces the stock's forward price; calls (which need the stock up) suffer, puts (which benefit from the price drop) gain.

**AZ4.** Replace the drift: `d1 = [ln(S/K) + (r − q + σ²/2)T] / (σ√T)` — i.e. subtract the dividend yield `q` from the rate (equivalently, price off `S·e^(−qT)`).

**AZ5.** Because an American call holder can **exercise just before an ex-dividend date** to capture a dividend the option itself wouldn't pay. If the dividend is large enough, grabbing it beats holding the option's remaining time value — so early exercise becomes optimal.

---

*Tomorrow (Day 12): **Implied volatility and the volatility smile** — reading the market's own view of risk — **plus the fourth big cumulative quiz, covering Days 10–12.***
