# Day 9 — 2026-08-12  ·  ⭐ Big cumulative quiz day (Days 7–9)

Work top-to-bottom. **Don't scroll to the Answers section** until you've attempted everything. Today's Part 4 is a **bigger review quiz** covering the Greeks so far (Days 7–9).

---

## Part 1 — Probability & Expected Value (5 questions)

**Q1. Grabbing shoes.**
A closet holds 10 distinct pairs of shoes (20 shoes total). You grab 4 shoes at random. What is the probability that at least one *matching pair* is among them?

**Q2. Compounding returns.**
Each year, independently, a stock is equally likely to rise 20% or fall 10%. What is the *expected* total return over 2 years?

**Q3. Anagrams of BANANA.**
How many distinct arrangements are there of the letters in the word **BANANA**?

**Q4. Win-or-lose die.**
You roll a fair die. If it shows 4, 5, or 6 you win that many dollars; if it shows 1, 2, or 3 you lose that many dollars. What is the expected value of one roll?

**Q5. The lost boarding pass.**
100 passengers board a plane. The first has lost their boarding pass and sits in a random seat. Every later passenger takes their own assigned seat if it's free, otherwise a random free seat. What is the probability the **100th** passenger sits in their own assigned seat?

---

## Part 2 — Brainteaser

**25 horses, no stopwatch.**
You have 25 horses and a track that races at most **5 at a time**. You have no timer, so each race only tells you the finishing *order* of those 5. Assuming every horse runs at a consistent speed, what is the **minimum number of races** needed to identify the **3 fastest** horses overall?

---

## Part 3 — Black-Scholes Lesson

### Day 9: Theta — time decay, the rent on gamma

We've built delta (exposure) and gamma (how exposure moves). **Theta** is the third leg — the cost of *time itself* passing — and it's the natural counterweight to gamma.

**1. Definition.**
**Theta (Θ) = ∂(option price)/∂t** — how much value the option loses as one unit of time (usually a day) elapses, holding stock price, volatility, and rates constant. It's quoted as **dollars per day**.

- For a **long option, theta is negative**: all else equal, an option is worth a little less tomorrow than today, because there's less time for a favorable move. Owning options means **paying rent every day**.
- For a **short option, theta is positive**: you *collect* that decay as income.

**2. Where theta bites hardest.**
Theta is most negative for **at-the-money options near expiry** — the same place gamma is largest. That's not a coincidence (see below). Deep ITM/OTM options decay slowly; ATM options "melt" fastest in their final days, and time value collapses toward zero right at expiry.

**3. The gamma–theta trade-off — two sides of one coin.** ⭐
This is the single most important relationship on an options desk:

- **Long gamma ⇒ negative theta.** You own convexity (big moves help you) but you *pay* time decay for it.
- **Short gamma ⇒ positive theta.** You collect time decay but *lose* on big moves.

They're linked by the Black-Scholes PDE, which for a delta-hedged position reduces to roughly:

> **Θ ≈ −½·σ²·S²·Γ**  (plus a small rate term)

Read it plainly: **theta and gamma have opposite signs and are tied together by volatility.** The daily theta you pay to be long gamma is exactly what the market charges for the convexity you'd expect to harvest *if the stock realizes volatility equal to the implied σ.* So:

- If the stock **moves more than implied** → your gamma gains beat the theta you paid → long-gamma wins.
- If it **moves less than implied** → theta bleed beats your gamma gains → short-gamma wins.

That's the essence of volatility trading: **theta vs. realized gamma P&L.** "Theta is the **rent you pay to be long gamma**."

**4. Worked example.**
An at-the-money option has **theta = −$0.05 per day**. If nothing moves, it loses about **5 cents per share per day** — over a 3-day weekend, roughly **−$0.15**. If you're *long* this option and delta-hedged, you need the stock to actually bounce around enough that your gamma re-hedging (buying low, selling high) earns back more than that 15-cent bleed. If the market sits still, you lose the rent; if it whips around, your convexity pays off.

**5. Who's on each side.**
Options **market-makers are frequently short gamma** (they sell options to customers) and therefore **collect theta** as steady income — their job is to manage the tail risk of a big move that could overwhelm that income. Volatility buyers do the reverse: pay theta, pray for movement.

**Key intuition to carry forward:** theta is the price of time. It is the mirror image of gamma — you can't be long convexity without paying daily rent, and you can't collect that rent without being short convexity. Whether that trade wins comes down to **realized volatility vs. the implied volatility baked into the option's price** — which is exactly where we head next (implied vol, Day 12).

---

## Part 4 — ⭐ BIG CUMULATIVE QUIZ (Days 7–9, 10 questions)

**BQ1.** Define delta, gamma, and theta — one line each.

**BQ2.** Which Greek is the first derivative of the option price with respect to the stock? The second derivative with respect to the stock? The derivative with respect to time?

**BQ3.** You are long one call (on 100 shares) with delta 0.55. What stock trade makes you delta-neutral?

**BQ4.** For what moneyness and time-to-expiry is gamma (and the magnitude of theta) largest?

**BQ5.** Is gamma the same for a call and a put with the same strike and expiry?

**BQ6.** If a position is *long gamma*, what is the typical sign of its theta, and what does that mean in cash terms?

**BQ7.** An option has delta 0.40 and gamma 0.06. If the stock rises $5, what is its new approximate delta?

**BQ8.** You hold a delta-hedged *long* option position. Do large moves in either direction help or hurt, and which Greek is responsible?

**BQ9.** Complete the trader's saying: "Theta is the ___ you pay to be long gamma."

**BQ10.** A market-maker who is short options collects theta each day. What is the main risk they are being paid to bear, and how do they manage it?

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Part 1 — Probability & EV

**A1 — ≈ 30.6%.**
Use the complement (no pair = all 4 shoes from different pairs): `P(no pair) = [C(10,4)·2⁴] / C(20,4) = (210·16)/4845 = 3360/4845 ≈ 0.6935`. So `P(at least one pair) = 1 − 0.6935 = **0.3065 ≈ 30.6%**`.

**A2 — +10.25%.**
The expected one-year growth factor is `½(1.20) + ½(0.90) = 1.05`. Because years are independent, `E[2-year factor] = 1.05² = 1.1025`, i.e. **+10.25%**. (Worth knowing: the *median* outcome is lower than the mean here — up-then-down gives `1.20·0.90 = 1.08` — a first taste of "volatility drag" between mean and median growth.)

**A3 — 60.**
BANANA has 3 A's, 2 N's, 1 B: `6! / (3!·2!·1!) = 720 / 12 = **60**`.

**A4 — +$1.50.**
`(1/6)(4+5+6) − (1/6)(1+2+3) = (15 − 6)/6 = 9/6 = **$1.50**`.

**A5 — 1/2.**
The classic result: the 100th passenger ends in their own seat with probability **½**. Reason: the only two seats that can possibly remain for the last passenger are the first passenger's own seat or the last passenger's own seat, and by symmetry each is equally likely to be the one left. (True for any n ≥ 2.)

## Part 2 — Brainteaser

**25 horses — 7 races.**
1. Run **5 races of 5** (every horse races once). Rank within each group; label groups A–E by their winners' speeds after the next race.
2. **Race 6:** race the **5 group-winners**. This ranks the winners; say `A1 > B1 > C1 > D1 > E1`. Now `A1` is the fastest horse overall, and all of groups D and E are eliminated (their best can't crack the top 3).
3. The only remaining candidates for 2nd and 3rd are: `A2, A3` (behind A1), `B1, B2` (B1 lost only to A1), and `C1` (lost only to A1 and B1). That's **5 horses**.
4. **Race 7:** race those 5. The **top two** finishers are the overall 2nd and 3rd fastest.
Total = **7 races**.

## Part 4 — Big Cumulative Quiz (Days 7–9)

**BAQ1.** *Delta* = ∂price/∂S, the sensitivity to a $1 move (and the hedge ratio). *Gamma* = ∂delta/∂S = ∂²price/∂S², the rate at which delta changes (curvature). *Theta* = ∂price/∂t, the option's value lost per day as time passes (time decay).

**BAQ2.** First derivative in `S` → **delta**; second derivative in `S` → **gamma**; derivative in time → **theta**.

**BAQ3.** **Short 55 shares** (`0.55 × 100`).

**BAQ4.** **At-the-money**, and **near expiry** (short time remaining) — that's where both gamma and |theta| peak.

**BAQ5.** **Yes** — same strike and expiry ⇒ identical gamma for the call and the put.

**BAQ6.** Long gamma ⇒ **negative theta**: you **pay** time decay every day (cash out) in exchange for owning convexity.

**BAQ7.** `0.40 + 0.06×5 = **0.70**`.

**BAQ8.** They **help** — a delta-hedged long-option position profits from big moves in *either* direction via `+½Γ(ΔS)²`. The responsible Greek is **gamma** (convexity).

**BAQ9.** "Theta is the **rent** you pay to be long gamma."

**BAQ10.** They are short gamma, so the risk is a **large or sudden move** in the underlying, which can lose more than the theta they collect. They manage it by **continuously delta-hedging** (and often buying cheaper wing options or limiting position size) to cap the damage from big moves and tail events.

---

*Tomorrow (Day 10): **Vega** — sensitivity to volatility itself, and why it's the Greek that makes options a direct bet on σ.*
