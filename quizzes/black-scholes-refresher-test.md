# Black-Scholes Refresher Test

**A standalone theory test on the whole Black-Scholes model** — for knocking the rust off after time away. 24 questions across four sections (foundations, pricing, the Greeks, implied vol & limits), including a few short calculations.

No peeking: work all four sections first. **Answers with explanations are at the very end.** Give yourself ~40 minutes; a score of 19+/24 says you're sharp again.

---

## Section A — Foundations & Assumptions

**A1.** What right does a *call* give its holder, and what right does a *put* give? Write each one's payoff at expiry in terms of the stock price `S` and strike `K`.

**A2.** Define *intrinsic value* and *time value*. A $50-strike call trades at $8.20 while the stock is $54 — split the premium into the two components.

**A3.** Give two reasons Black-Scholes models a stock's *returns* as lognormal rather than modeling raw dollar price changes as normal.

**A4.** A stock has a daily volatility of 1.5%. Approximately what is its annualized volatility (252 trading days)?

**A5.** List four assumptions the Black-Scholes model makes.

**A6.** The stock is at $47. Classify as in-, at-, or out-of-the-money: (a) a $50-strike call; (b) a $50-strike put.

---

## Section B — Pricing & Risk-Neutral Valuation

**B1.** Write the Black-Scholes formula for a European call, and the definitions of `d1` and `d2`.

**B2.** Why does the stock's real-world expected return (the drift `μ`) *not* appear anywhere in the option's price?

**B3.** Explain, in one or two sentences, the *replication / no-arbitrage* argument that underlies the price.

**B4.** State the principle of risk-neutral valuation in one sentence.

**B5.** State put-call parity for European options on a non-dividend stock. Then use it: `C = $6, S = $40, K = $40, r = 0, T = 1` — what is the put worth?

**B6.** Compute `d1` and `d2` for `S = 100, K = 100, r = 0, σ = 0.20, T = 1`. Then say what `N(d1)` and `N(d2)` each represent.

---

## Section C — The Greeks

**C1.** Name the Greek that is the derivative of the option price with respect to each of: (a) the stock price; (b) the stock price, second derivative; (c) time; (d) volatility; (e) the interest rate.

**C2.** What is a call's delta equal to (in terms of `N(·)`), and what range does it occupy? What is a put's delta?

**C3.** For what moneyness and time-to-expiry are *gamma* and *theta* largest? For what moneyness and time is *vega* largest?

**C4.** Explain the gamma-theta trade-off. If you are *long gamma*, what is the sign of your theta, and what does that mean in cash terms?

**C5.** An option has delta 0.55 and gamma 0.04. If the stock rises $3, what is its new approximate delta?

**C6.** Is *vega* positive or negative for a long put? Explain why it has the same sign as a long call's vega.

**C7.** What is the sign of *rho* for a call versus a put? And how do *dividends* affect call versus put values?

---

## Section D — Implied Volatility & the Model's Limits

**D1.** Define implied volatility.

**D2.** In equity index options, which strikes trade at higher implied vol — low strikes (OTM puts) or high strikes (OTM calls)? Name this pattern and give one reason it exists.

**D3.** What is the difference between *implied* and *realized* volatility, and which Greek exposes you to each?

**D4.** You want to be both delta-neutral and gamma-neutral. Why isn't trading the stock enough, and what else do you need?

**D5.** Name one Black-Scholes assumption that fails in real markets, and one market consequence of that failure.

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Section A — Foundations & Assumptions

**A1.** A **call** gives the right (not obligation) to **buy** the underlying at strike `K`; payoff at expiry `= max(S − K, 0)`. A **put** gives the right to **sell** at `K`; payoff `= max(K − S, 0)`.

**A2.** Intrinsic value = value if exercised now = `max(S − K, 0)` for a call = `max(54 − 50, 0) = $4`. Time value = premium − intrinsic = `8.20 − 4 = $4.20`.

**A3.** Any two of: (i) percentage returns are **comparable** across price levels and time (a $1 move means different things on a $10 vs $500 stock); (ii) a return-based (lognormal) price stays **strictly positive** — a normal-dollar-change model could send the stock below zero; (iii) the lognormal is **right-skewed**, matching stocks' unlimited upside and floored-at-zero downside.

**A4.** `1.5% × √252 ≈ 1.5% × 15.87 ≈ **23.8%**`.

**A5.** Any four of: constant (known) volatility; lognormal returns / geometric Brownian motion with **continuous paths (no jumps)**; constant risk-free rate; no dividends (relaxable); frictionless markets (no transaction costs, continuous trading); European-style exercise.

**A6.** (a) $50 call with stock at $47: **out-of-the-money** (`S < K`). (b) $50 put with stock at $47: **in-the-money** (`S < K`), intrinsic `max(50 − 47, 0) = $3`.

## Section B — Pricing & Risk-Neutral Valuation

**B1.** `C = S·N(d1) − K·e^(−rT)·N(d2)`, where
`d1 = [ln(S/K) + (r + σ²/2)·T] / (σ√T)` and `d2 = d1 − σ√T`; `N(·)` is the standard normal CDF.

**B2.** Because the option is priced by **hedging/replication**: a stock-plus-cash portfolio reproduces its payoff, and the hedge removes exposure to the stock's actual drift. Under the resulting **risk-neutral measure** every asset grows at `r`, so `μ` drops out — only volatility `σ` matters.

**B3.** An option's payoff can be **replicated** by a continuously-adjusted portfolio of the stock and cash (borrow/lend). Since that portfolio and the option have identical payoffs in every future state, **no-arbitrage forces them to have the same price today** — so the option's fair value is the cost of building the replicating portfolio.

**B4.** An option's price equals the **discounted expected value of its payoff, computed under the risk-neutral probability measure** (in which all assets are assumed to drift at the risk-free rate).

**B5.** `C − P = S − K·e^(−rT)`. With `r = 0`: `C − P = S − K = 40 − 40 = 0`, so `P = C = **$6**`.

**B6.** `σ²/2 = 0.04/2 = 0.02`. `d1 = [ln(1) + (0 + 0.02)·1] / (0.20·1) = 0.02/0.20 = **0.10**`; `d2 = 0.10 − 0.20 = **−0.10**`.
`N(d2)` = the risk-neutral **probability the call finishes in the money** (is exercised). `N(d1)` = the call's **delta** (hedge ratio / share-equivalent), also a stock-weighted exercise probability, and always ≥ `N(d2)`.

## Section C — The Greeks

**C1.** (a) **Delta**; (b) **Gamma**; (c) **Theta**; (d) **Vega**; (e) **Rho**.

**C2.** Call delta `= N(d1)`, in the range **(0, 1)**. Put delta `= N(d1) − 1`, in the range **(−1, 0)** (negative — a put gains as the stock falls).

**C3.** **Gamma and theta** are largest for **at-the-money options near expiry**. **Vega** is largest for **at-the-money options far from expiry** (long-dated) — the opposite end of the calendar.

**C4.** Owning convexity and paying for time are two sides of one coin: **long gamma ⇒ negative theta** — you profit from big moves (positive convexity) but **pay time-decay "rent" every day**. So a long-gamma position has **negative theta**, meaning a daily cash cost that your gamma re-hedging must beat (realized > implied vol) to profit.

**C5.** New delta ≈ `0.55 + 0.04 × 3 = 0.55 + 0.12 = **0.67**`.

**C6.** **Positive** for a long put, same sign as a long call. Higher volatility widens the distribution of future prices; because both calls and puts have **one-sided payoffs** (limited downside, open-ended gains), more dispersion raises the value of *both*.

**C7.** **Call rho positive, put rho negative** — higher rates cut the present value of the strike (`K·e^(−rT)`), helping the call (deferring payment) and, by parity, hurting the put. **Dividends lower call values and raise put values** — they transfer value to shareholders (not option holders), reducing the stock's forward price.

## Section D — Implied Volatility & the Model's Limits

**D1.** Implied volatility is the value of `σ` that, plugged into Black-Scholes, makes the model's price equal the option's observed **market price** — i.e., the market's forward-looking volatility forecast, read out of the price.

**D2.** **Low strikes (OTM puts)** trade at higher implied vol — the downward-sloping **volatility skew (or "smirk")**. Reasons: hedging demand / crash-fear for downside puts, the leverage effect (falling stocks get more volatile), and negative spot–vol correlation — all making the left tail richer than a lognormal model assumes.

**D3.** **Realized** vol is how much the stock *actually* moves (harvested through **gamma** re-hedging). **Implied** vol is the vol *priced into* the option; your exposure to it is **vega**. You can win on one and lose on the other in the same period.

**D4.** Stock is **linear**, so it has **zero gamma** — trading it changes your delta but adds no convexity. To neutralize gamma you need a **second, convex instrument (another option)**; you cancel gamma with the option, then use stock to clean up the residual delta.

**D5.** Any one, with its consequence: **constant volatility** fails → the **volatility smile/skew**; **no jumps / continuous paths** fails → markets **gap** and returns have **fat tails**; **normal returns** fails → **leptokurtic, negatively-skewed** distributions; **frictionless continuous hedging** fails → **transaction costs and hedging error**. General consequence: BS fed a single flat vol **systematically misprices** options (especially OTM puts), which is exactly why traders manage a vol *surface* instead.

---

*Scoring: 22–24 excellent (interview-ready), 19–21 solid (light review), 15–18 revisit the Greeks and risk-neutral pricing, <15 re-read Days 1–9. To drill deeper, see the four cumulative quizzes (Days 3, 6, 9, 12), the Day-15 final, and `options-comprehensive-quiz-1.md`.*
