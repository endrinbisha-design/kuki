# Day 15 — 2026-08-18  ·  ⭐ FINAL comprehensive review & quiz (Days 1–15)

The last day of the core course. Work top-to-bottom — Part 3 ties the whole model together, and Part 4 is the **big final quiz** spanning everything. **Answers with explanations are at the very end.**

---

## Part 1 — Probability & Expected Value (5 questions)

**Q1. Two sixes in a row.**
You roll a fair die repeatedly until you first see two consecutive sixes (66). What is the expected number of rolls?

**Q2. The positive mammogram.**
1% of women in a screening population have breast cancer. The test detects 90% of true cancers (90% sensitivity) but also flags 9% of healthy women (9% false-positive rate). A woman tests positive. What is the probability she actually has cancer?

**Q3. Aces in a bridge hand.**
You're dealt 13 cards from a standard 52-card deck. What is the expected number of aces in your hand?

**Q4. Same mean, different fate.**
Stock A returns **+50% or −40%** each period (equally likely); Stock B returns **+10% or 0%** each period (equally likely). (a) Compare their expected one-period returns. (b) Which would you rather *hold for many periods*, and why?

**Q5. Die game with two re-rolls.**
You roll a fair die and are paid its value, but you may re-roll up to **two** times (three rolls max), always keeping the result of your final roll. Playing optimally, what is the expected value of the game? (On Day 1, one re-roll was worth $4.25 — does a second re-roll add much?)

---

## Part 2 — Brainteaser

**100 prisoners and 100 boxes.**
100 prisoners are numbered 1–100. In a room are 100 boxes, each containing one prisoner's number in random order. One at a time, each prisoner may open **up to 50 boxes**, looking for their own number, then leaves the room exactly as they found it (no communication). If **every** prisoner finds their own number, all go free; if even one fails, all are executed. Random guessing gives a survival probability of `(½)¹⁰⁰` — astronomically small. Yet there is a strategy that gives the group better than a **30%** chance. What is it, and why does it work?

---

## Part 3 — Black-Scholes Lesson

### Day 15: The whole model, end to end

Fifteen days in one page. This is the mental model to walk into an interview with.

**1. What an option is (Day 1).**
A **call/put** is the right (not obligation) to buy/sell at strike `K` by expiry. Payoffs: `max(S−K,0)` and `max(K−S,0)`. Price = **intrinsic value** (exercise-now value) + **time value** (everything else). The hard part is time value, and it's driven by volatility, time, rates, and moneyness.

**2. Where uncertainty comes from (Day 2).**
Model **returns**, not dollar prices — they're comparable and keep prices positive. **Volatility σ** is the standard deviation of returns and scales with **√time** (`σ_annual = σ_daily·√252`). Prices come out **lognormal** (positive, right-skewed). The stock follows **GBM**: `dS/S = μ dt + σ dW` (drift + diffusion).

**3. How the price is pinned down (Day 3).**
By **no-arbitrage + replication**: an option's payoff can be rebuilt from stock + cash, so it must cost what that replicating portfolio costs. This gives **risk-neutral pricing** — price = discounted expected payoff in a world where everything drifts at `r`. Crucially, the **real drift μ vanishes**; only σ matters. Two people who disagree on direction still agree on the price.

**4. The formula (Days 4–6).**
`C = S·N(d1) − K·e^(−rT)·N(d2)`, with `d1 = [ln(S/K)+(r+σ²/2)T]/(σ√T)`, `d2 = d1 − σ√T`. **`N(d2)`** = risk-neutral probability of exercise; **`N(d1)`** = the delta (and a stock-weighted exercise probability, always ≥ N(d2)). Puts follow from **put-call parity**: `C − P = S − K·e^(−rT)`.

**5. The Greeks — your risk dashboard (Days 7–11).**

| Greek | Is | Peaks at | Sign (long option) |
|-------|-----|----------|-----|
| **Delta** `N(d1)` | ∂price/∂S — hedge ratio | — | call +, put − |
| **Gamma** | ∂delta/∂S — convexity | ATM, **near** expiry | + |
| **Theta** | ∂price/∂t — time decay | ATM, near expiry | − (you pay rent) |
| **Vega** | ∂price/∂σ — vol sensitivity | ATM, **far** expiry | + (calls & puts) |
| **Rho** | ∂price/∂r — rate sensitivity | long-dated | call +, put − |

Dividends lower calls / raise puts (via the forward; `d1` uses `r − q`).

**6. Implied vol and the surface (Day 12).**
Run BS backwards: the price *is* a **volatility quote** (implied vol). BS assumes one σ, but the market shows a **smile/skew** — evidence the lognormal model is wrong in the tails. Equities skew down (OTM puts richest) from crash fear, the leverage effect, and negative spot–vol correlation. Traders manage the whole **vol surface** (strike × expiry).

**7. Running the book (Day 13).**
Delta-hedge with stock; **gamma/vega need other options** (stock is linear). Daily P&L decomposes into the Greeks: `ΔV ≈ Δ·ΔS + ½Γ(ΔS)² + Θ·Δt + Vega·Δσ + ρ·Δr`. The **gamma-theta breakeven move** is just **realized vs. implied vol** expressed as a daily price move.

**8. The limits (Day 14).**
Constant vol, no jumps, thin tails, and frictionless hedging are all false. Markets gap; tails are fat; hedging costs. BS is a **quoting language and baseline**, not truth — respect the tails it ignores. "All models are wrong; some are useful."

**The one-sentence version:** *An option is a bet on the width of the future-price distribution; Black-Scholes prices it as the cost of the stock-and-cash portfolio that replicates it — equivalently, its discounted expected payoff in a risk-neutral world — and the Greeks tell you how that price moves as the world does.*

---

## Part 4 — ⭐ FINAL BIG QUIZ (Days 1–15, 15 questions)

**FQ1.** In the risk-neutral framework, what does an option's price equal (in words)?

**FQ2.** Write the expiry payoff of a call and of a put.

**FQ3.** A stock has a daily volatility of 1.25%. Approximately what is its annualized volatility (252 days)?

**FQ4.** Why does the stock's real-world expected return (drift `μ`) not appear in the Black-Scholes price?

**FQ5.** State put-call parity, then use it: `C = $7, S = $50, K = $50, r = 0, T = 1` — what is the put worth?

**FQ6.** In the call formula, what do `N(d1)` and `N(d2)` each represent?

**FQ7.** Compute `d1` and `d2` for `S = 100, K = 100, r = 0, σ = 0.40, T = 1`.

**FQ8.** Match each Greek — delta, gamma, theta, vega, rho — to the quantity it's the derivative with respect to.

**FQ9.** For what moneyness/expiry do gamma and theta peak, and how does that differ from where vega peaks?

**FQ10.** For a delta-hedged long-option position, what daily stock move "breaks even," and what real-world comparison does that correspond to?

**FQ11.** What is implied volatility, what is the equity volatility skew, and give one reason the skew exists.

**FQ12.** You want to be both delta-neutral and gamma-neutral. Why isn't stock alone enough, and what do you need?

**FQ13.** Name three Black-Scholes assumptions that fail in real markets, and one market consequence of those failures.

**FQ14.** You expect a large move in a stock but don't know the direction. What options position expresses this, and which Greeks are you long?

**FQ15.** For a non-dividend stock, when (if ever) is it optimal to exercise an American call early — and what changes that answer?

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Part 1 — Probability & EV

**A1 — 42 rolls.**
For two consecutive occurrences of a specific face (p = 1/6), the expected wait is `1/p + 1/p² = 6 + 36 = **42**`. (Each roll of a six "arms" you; a non-six resets the pair.)

**A2 — ≈ 9.2%.**
`P(cancer | +) = (0.01·0.90) / (0.01·0.90 + 0.99·0.09) = 0.009 / (0.009 + 0.0891) = 0.009/0.0981 ≈ **0.092 ≈ 9%**`. The famous result: most positive screens are false alarms when the disease is rare — base rates dominate.

**A3 — 1.**
By linearity, each of the 4 aces lands in your 13-card hand with probability `13/52 = ¼`; `4 × ¼ = **1**`.

**A4 — (a) equal expected returns; (b) hold B.**
(a) `E[A] = ½(1.50) + ½(0.60) = 1.05` (+5%); `E[B] = ½(1.10) + ½(1.00) = 1.05` (+5%) — **identical arithmetic means.**
(b) Over many periods what compounds is the **geometric** mean: A → `√(1.50·0.60) = √0.90 ≈ 0.949` (**−5%/period**, it grinds toward zero!); B → `√(1.10·1.00) = √1.10 ≈ 1.049` (**+5%/period**). So despite equal average returns, **B grows and A decays** — the volatility drag we first met on Day 9. Hold B.

**A5 — 14/3 ≈ $4.67.**
Work backwards. With no re-rolls left, value = 3.5. With one re-roll left (Day 1's game), value = 4.25. With **two** re-rolls left, you keep the current roll only if it beats 4.25 — so keep 5 or 6, otherwise re-roll: `value = (2/6)·(5.5) + (4/6)·(4.25) = 1.833 + 2.833 = 14/3 ≈ **$4.67**`. The second re-roll adds only ~42¢ over the first — diminishing returns, since you re-roll from an already-good position.

## Part 2 — Brainteaser

**Follow the cycle — survival ≈ 31%.**
Each prisoner starts at the box **labeled with their own number**, then goes to the box numbered by the *slip inside* it, and repeats — following the chain. The box arrangement is a random **permutation**, which decomposes into cycles; a prisoner following their chain is walking their own cycle, and they find their number within 50 opens **iff the cycle containing them has length ≤ 50.** So *all* prisoners succeed exactly when the permutation has **no cycle longer than 50** — and a permutation of 100 can have at most one such long cycle. The probability that a random permutation of 100 has a cycle longer than 50 is `1/51 + 1/52 + … + 1/100 ≈ ln 2 ≈ 0.693`, so the group survives with probability `1 − 0.693 ≈ **0.31**`. Linking every prisoner's fate to one shared structure (the cycle lengths) turns `(½)¹⁰⁰` into ~31%.

## Part 4 — Final Big Quiz

**FAQ1.** The **discounted expected value of its payoff, computed under the risk-neutral measure** (where all assets drift at the risk-free rate) — equivalently, the cost of the stock-plus-cash portfolio that replicates its payoff.

**FAQ2.** Call: `max(S − K, 0)`. Put: `max(K − S, 0)`.

**FAQ3.** `1.25% × √252 ≈ 1.25% × 15.87 ≈ **19.8%**`.

**FAQ4.** Because pricing is done by **replication / risk-neutral valuation**: the option is hedged with the stock, and the hedge removes exposure to the stock's actual drift. Under the risk-neutral measure every asset grows at `r`, so `μ` never enters — only volatility `σ` does.

**FAQ5.** `C − P = S − K·e^(−rT)`. With `r = 0`: `C − P = S − K = 0`, so `P = C = **$7**`.

**FAQ6.** `N(d2)` = the risk-neutral **probability the call is exercised** (finishes ITM). `N(d1)` = the call's **delta** (hedge ratio / share-equivalent), also a stock-weighted exercise probability, always ≥ `N(d2)`.

**FAQ7.** `σ²/2 = 0.16/2 = 0.08`. `d1 = [ln(1) + (0 + 0.08)·1]/(0.40·1) = 0.08/0.40 = **0.20**`; `d2 = 0.20 − 0.40 = **−0.20**`.

**FAQ8.** Delta → ∂price/∂**S**; Gamma → ∂²price/∂**S²** (∂delta/∂S); Theta → ∂price/∂**t** (time); Vega → ∂price/∂**σ** (volatility); Rho → ∂price/∂**r** (rate).

**FAQ9.** **Gamma and theta** peak for **at-the-money options near expiry**; **vega** peaks for **at-the-money options far from expiry** (long-dated). Short end vs. long end of the calendar.

**FAQ10.** The breakeven is the move where gamma gains offset theta: `½·Γ·(ΔS)² = −Θ·Δt`. It corresponds to **realized vs. implied volatility** — if the stock's actual daily move exceeds the breakeven, long gamma (long realized vol) wins; if it's calmer, theta (the implied vol you paid) wins.

**FAQ11.** Implied vol is the `σ` that makes the BS price equal the market price — the market's volatility forecast. The **equity skew** is that **OTM puts trade at higher implied vol than OTM calls** (a downward-sloping curve). One reason: **hedging demand / crash-fear** for downside puts (also the leverage effect and negative spot–vol correlation).

**FAQ12.** Stock is **linear**, so it has **zero gamma** — it can neutralize delta but can't touch convexity. You need a **second, convex instrument (another option)** to cancel gamma, then stock to clean up the residual delta.

**FAQ13.** Any three of: **constant volatility** (fails → the smile/skew), **no jumps / continuous paths** (fails → gaps and fat tails), **normal returns** (fails → leptokurtic, negatively-skewed returns), **frictionless continuous hedging** (fails → transaction costs and hedging error). Consequence: BS with a single flat vol **systematically misprices** options — especially OTM puts — which is exactly why the vol surface exists.

**FAQ14.** A **long straddle** (or strangle) — buy a call and a put. You are **long gamma and long vega** (and paying theta); you profit if the stock moves more than the implied vol you paid for, in either direction.

**FAQ15.** For a **non-dividend** stock it is **never** optimal to exercise an American call early — you'd throw away time value and the interest earned on deferring the strike, so selling beats exercising. A sufficiently large **dividend** (exercising just before the ex-date to capture it) is what can make early exercise worthwhile.

---

## 🎓 Course complete!

You've finished the 15-day Black-Scholes arc: from *what an option is* all the way to *why the model breaks and what traders do about it.* You can now:

- explain **why μ drops out** and price an option two ways (replication and risk-neutral expectation);
- write and interpret the **formula**, `d1`/`d2`, and **put-call parity**;
- reason fluently about **all five Greeks**, where they peak, and the **gamma-theta = realized-vs-implied** relationship;
- read the **vol smile/skew** and the surface;
- run a **delta-gamma-hedged book** with **P&L attribution**; and
- speak credibly about the model's **limits** and tail risk.

**Where to go from here:**
1. Keep the **daily 5 prob/EV + brainteaser** habit — that muscle is what interviews test under time pressure.
2. Revisit `quizzes/options-comprehensive-quiz-1.md` and the four big cumulative quizzes (Days 3, 6, 9, 12) cold, then this Day-15 final — aim to explain each answer out loud.
3. Ask for **deeper follow-on modules** (exotics & path-dependence, the vol surface in depth, market-making microstructure, fixed-income/rates, or full **mock interviews** with live grading) whenever you're ready.

Good luck with the recruiting — you're well-armed.
