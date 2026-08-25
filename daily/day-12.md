# Day 12 — 2026-08-15  ·  ⭐ Big cumulative quiz day (Days 10–12)

Work top-to-bottom. **Don't scroll to the Answers section** until you've attempted everything. Today's Part 4 is a **bigger review quiz** covering Days 10–12.

---

## Part 1 — Probability & Expected Value (5 questions)

**Q1. Waiting for heads-then-tails.**
You flip a fair coin repeatedly until you first see the sequence **HT** (a head immediately followed by a tail). What is the expected number of flips? (For contrast, recall HH took 6 — does HT differ?)

**Q2. Drug test base rate.**
A workplace drug test is 98% accurate in both directions (98% sensitivity, 98% specificity). Only 0.5% of employees actually use the drug. An employee tests positive. What is the probability they are truly a user?

**Q3. Random handshakes.**
Ten people are at a party. Each *pair* of people shakes hands independently with probability ½. What is the expected number of handshakes?

**Q4. Product of two dice.**
You roll two fair dice and are paid, in dollars, the *product* of the two numbers. What is your expected payout?

**Q5. Red-or-black stop game.**
A deck of 5 red and 5 black cards is shuffled and dealt face-up one at a time. Exactly once, just before a card is revealed, you may say "stop" and bet that the *next* card is red (you win $1 if it is, $0 if not). Is there a strategy that gives you better than a 50% chance — and what's the expected value of your best play?

---

## Part 2 — Brainteaser

**Three ants on a triangle.**
Three ants sit at the three corners of a triangle. At the same instant, each ant independently picks one of the two edges leaving its corner (at random, 50/50) and starts walking along it at the same speed. What is the probability that **none** of the ants collide?

---

## Part 3 — Black-Scholes Lesson

### Day 12: Implied volatility and the volatility smile

We've treated `σ` as a single known number. In the real market it's the opposite: price is observed, and `σ` is *backed out*. That inversion — and the fact that it doesn't come out constant — is where Black-Scholes meets reality.

**1. Implied volatility (IV).**
Black-Scholes maps `σ → price`. **Implied volatility runs it backwards:** given an option's *market price*, IV is the volatility you must plug into Black-Scholes to reproduce that price. There's no closed form — you solve for it numerically — but conceptually it's simple: **IV is the market's forward-looking forecast of volatility**, expressed in the one number the model cares about.

This is why traders **quote and think in vol, not dollars.** "The 25-delta put is trading at 22 vol" is more meaningful than a dollar price, because it's comparable across strikes, expiries, and underlyings. (The **VIX** is essentially the 30-day implied vol of the S&P 500.)

**2. The problem: BS assumes *one* σ, but the market shows many.**
Black-Scholes assumes a *single, constant* volatility for a stock. If that were true, every option on the same stock — every strike, every expiry — would imply the **same** IV. Plot IV against strike and you'd get a flat line.

You don't. You get a **curve.**

**3. The smile and the skew.**

- **Volatility smile:** in many markets (FX, commodities), plotting IV vs. strike gives a **U-shape** — OTM puts *and* OTM calls trade at higher IV than at-the-money options. The wings are "expensive."
- **Volatility skew / smirk:** in **equity index** options, the curve is **downward-sloping** — low strikes (OTM puts) carry *much* higher IV than high strikes (OTM calls). Downside protection is bid up.

**4. Why the skew exists.**
Black-Scholes' lognormal assumption **underprices the tails** — real return distributions have **fatter tails and negative skew** (crashes are sharper and more common than a bell curve predicts). The market corrects for this by charging **more implied vol** on the strikes that pay off in those tail scenarios. Specific drivers in equities:
- **Crash-o-phobia / hedging demand:** investors pay up for OTM puts as portfolio insurance.
- **The leverage effect:** as a stock falls, its debt-to-equity rises and it becomes *more* volatile — so low prices and high vol go together.
- **Negative spot–vol correlation:** markets tend to drop *and* get volatile at the same time, making downside puts worth more than a symmetric model implies.

**5. The vol surface.**
IV also varies with **time to expiry** (the *term structure* of vol — e.g. calm now, event risk in three months). Put the two dimensions together — IV as a function of **strike and expiry** — and you get the **volatility surface**, the object an options desk actually manages. Black-Scholes isn't discarded; it's used as the *language* (a price ⇄ vol translator) on top of which traders model the surface's shape.

**6. What it means for you.**
- "Is this option cheap?" is really "is its **implied vol** low relative to what I think **realized vol** will be?"
- Skew is tradeable: a **risk reversal** (short put / long call) is a bet on the skew flattening; **butterflies** trade the curvature of the smile.
- The single most common vol-desk question: *implied vs. realized.* You make money being long options when **realized > implied**, and short options when **realized < implied**.

**Key intuition to carry forward:** implied volatility is Black-Scholes run in reverse — the market's price *is* a volatility quote. The smile/skew is the market openly admitting the lognormal model is wrong in the tails, and pricing the correction strike-by-strike. Reading that surface is much of what an options trader actually does.

---

## Part 4 — ⭐ BIG CUMULATIVE QUIZ (Days 10–12, 10 questions)

**BQ1.** Define vega — what it measures and in what units.

**BQ2.** Is vega positive or negative for a long put? Why?

**BQ3.** Where does vega peak (moneyness and time), and how does that contrast with where gamma and theta peak?

**BQ4.** What is the sign of rho for a call versus a put, and what's the one-line intuition?

**BQ5.** How do dividends affect calls versus puts, and how is `d1` adjusted for a continuous dividend yield `q`?

**BQ6.** Define implied volatility.

**BQ7.** What is the *volatility skew* in equity index options (which strikes have higher IV), and give one reason it exists.

**BQ8.** Distinguish *implied* volatility from *realized* volatility, and say which Greek exposes you to each.

**BQ9.** For a non-dividend stock, is it ever optimal to exercise an American call early? What single event would change that answer?

**BQ10.** You are long a straddle (long gamma *and* long vega). Describe a scenario in which the stock moves a fair amount over the week yet you still *lose* money on the position.

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Part 1 — Probability & EV

**A1 — 4 flips.**
HT is faster than HH. Once you get your first head, *every* subsequent tail completes the pattern, and heads before that tail just keep you "armed." Expected wait to the first head is 2, then expected wait to the next tail is 2, for `2 + 2 = **4**`. (HH is slower — 6 — because a tail after your first head resets you completely; HT has no such wasteful reset.)

**A2 — ≈ 19.8%.**
`P(user | +) = (0.005·0.98) / (0.005·0.98 + 0.995·0.02) = 0.0049 / (0.0049 + 0.0199) = 0.0049/0.0248 ≈ **0.198 ≈ 20%**`. Despite "98% accurate," a positive test is right only ~1 in 5 times when the base rate is tiny — the false positives from the 99.5% clean majority swamp the true positives.

**A3 — 22.5.**
There are `C(10,2) = 45` possible pairs, each shaking hands w.p. ½. By linearity, expected handshakes = `45 × ½ = **22.5**`.

**A4 — $12.25.**
The two dice are independent, so `E[XY] = E[X]·E[Y] = 3.5 × 3.5 = **12.25**`.

**A5 — No strategy beats 50%; EV = $0.50.**
Surprisingly, **no stopping rule does better than ½.** By a martingale/symmetry argument, at every moment the fraction of red cards remaining equals the probability the next card is red, and there's no way to systematically stop when that fraction exceeds ½ — for every sequence where reds are "saved for later," there's an equally likely mirror image. Whatever rule you use (including "always bet on the last card"), the expected value is exactly **$0.50**.

## Part 2 — Brainteaser

**1/4.**
The ants avoid all collisions only if they **all walk the same way around** the triangle — all clockwise or all counter-clockwise. Any other combination forces at least one head-on meeting on some edge. There are `2³ = 8` equally likely direction choices, and `2` of them are all-same-direction, so `P(no collision) = 2/8 = **1/4**`.

## Part 4 — Big Cumulative Quiz (Days 10–12)

**BAQ1.** Vega measures the change in an option's price per **1-percentage-point change in volatility** (`∂price/∂σ`), in dollars per vol point.

**BAQ2.** **Positive.** Higher volatility widens the future-price distribution; a put's one-sided payoff (bounded loss, gains as the stock falls toward zero) is worth more with more dispersion — same reasoning as a long call.

**BAQ3.** Vega peaks for **at-the-money, long-dated** options. Gamma and |theta| peak for **at-the-money, near-expiry** options — the opposite end of the calendar.

**BAQ4.** **Call rho positive, put rho negative.** Higher rates cut the present value of the strike (`K·e^(−rT)`), which helps the call (defer paying) and, by parity, hurts the put.

**BAQ5.** **Dividends lower calls and raise puts** (they cut the stock's forward price, which option holders don't receive). Adjust the drift: `d1 = [ln(S/K) + (r − q + σ²/2)T]/(σ√T)` — subtract `q` from `r`.

**BAQ6.** Implied volatility is the value of `σ` that, put into Black-Scholes, makes the model price equal the option's observed **market price** — the market's forward-looking volatility forecast.

**BAQ7.** The skew slopes **downward**: low strikes (**OTM puts**) trade at higher implied vol than high strikes (OTM calls). Reasons include crash-fear / hedging demand for downside puts, the leverage effect, and negative spot–vol correlation — all making the left tail richer than a lognormal model assumes.

**BAQ8.** **Realized** vol is how much the stock *actually* moves (harvested through **gamma** re-hedging). **Implied** vol is the vol *priced into* the option (your exposure to it is **vega**). You can win on one and lose on the other in the same period.

**BAQ9.** For a **non-dividend** stock, it is **never** optimal to exercise an American call early (you'd forfeit time value and the interest on the deferred strike). A large enough **dividend** (exercising just before the ex-date to capture it) is the event that can make early exercise worthwhile.

**BAQ10.** Any scenario where your **vega loss beats your gamma gain**. Classic case: a feared event passes (earnings, a Fed meeting) and **implied vol collapses** ("vol crush"); the stock moves some, but not as much as the rich implied vol you paid for. Your long-vega position gets marked down hard, and the gamma P&L from the actual move plus a couple days of theta bleed don't make up the difference — so you lose even though the stock "moved." (Equivalently: **realized vol < the implied vol you paid.**)

---

*Tomorrow (Day 13): **practical hedging** — putting the Greeks together into delta-gamma hedging and P&L attribution on a real position.*
