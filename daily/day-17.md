# Day 17 — 2026-08-20  ·  Phase 2, Day 2 (two tracks)

Two tracks again — **Track G (generalist S&T)** and **Track D (vol trading)**. Work top-to-bottom; **answers with explanations are at the very end.**

---

## Part 1 — Probability & Expected Value (5 questions)

**Q1. Larger of two draws.**
Two numbers are drawn independently and uniformly from [0, 1]. What is the expected value of the *larger* of the two?

**Q2. The recession signal.**
An indicator fires ahead of 80% of actual recessions, and gives a false alarm 10% of the time when no recession is coming. Recessions happen 15% of the time. The indicator just fired. What's the probability a recession is actually coming?

**Q3. Five-trade book.**
You put on 5 independent trades, each returning **+$100 with probability 0.6** or **−$100 with probability 0.4**. (a) What is your expected total P&L? (b) What is the probability the book finishes with a *net profit* (i.e., at least 3 winners)?

**Q4. Price the zero.**
A zero-coupon bond pays $100 in exactly one year. If the one-year interest rate is 5%, what is the bond's fair price today?

**Q5. First to flip heads.**
You and a friend alternate flipping a fair coin; the first to flip heads wins. You go first. What is your probability of winning?

---

## Part 2 — Brainteaser

**The painted cube.**
A 3×3×3 cube is painted on all six outer faces, then cut into 27 unit cubes. How many of the small cubes have paint on *exactly two* faces?

---

## Part 3 — Track G (Generalist S&T)

### The macro map — "what's your view?"

Nearly every S&T interview asks some version of *"What's your view on markets?"* They are **not** grading whether you're right — they're checking that you can hold a **coherent, defensible thesis** and reason across asset classes. Here's the map.

**1. The four drivers.**
Almost everything traces back to four variables: **growth**, **inflation**, **monetary policy (interest rates)**, and **employment**. Central banks move the policy rate to balance inflation against growth/jobs; that rate ripples through every asset.

**2. How a rate move propagates (the reflexes to know cold).**
When the central bank **raises rates** (all else equal):
- **Bonds** fall (yields rise) — existing fixed coupons are worth less.
- **Equities** tend to fall — future cash flows are discounted harder, and growth may slow.
- **The currency** tends to rise — higher yields attract capital (carry).
- **Inflation** cools (the intent).
Higher **inflation** → hawkish central bank → higher rates, and the chain repeats.

**3. The yield curve as a signal.**
Normally the curve slopes **up** (longer maturities yield more). When it **inverts** (short rates above long), it traditionally signals the market expects the central bank to **cut** rates ahead — i.e., a **recession** is anticipated. The 2s10s spread is the classic gauge.

**4. Risk-on vs. risk-off — the single most useful lens.**
- **Risk-on:** equities up, **credit spreads tighten**, high-beta / emerging markets rally, safe havens (US dollar, JPY, gold, Treasuries) soften.
- **Risk-off:** the mirror — stocks and credit sell off, safe havens bid. Framing a day or a thesis as risk-on/off instantly organizes cross-asset moves.

**5. How to pitch a view (memorize this 4-part structure).** ⭐
1. **Thesis** — one crisp sentence.
2. **Drivers** — 2–3 reasons.
3. **The trade** — how you'd actually express it.
4. **The risk** — what would make you wrong.

*Example:* "**Thesis:** the Fed is near the end of its hiking cycle. **Drivers:** inflation is decelerating, the labor market is softening, and financial conditions are already tight. **Trade:** I'd be long the front end of the curve — receive 2-year rates — and I'd add duration. **Risk:** a re-acceleration in inflation (e.g., an energy shock) that forces more hikes." That structure — even with a view they disagree with — is what makes you sound like a trader.

**Key intuition:** you don't need a genius call; you need a *thesis → drivers → trade → risk* chain that hangs together and shows you understand how rates, growth, and risk appetite move markets together.

**Track G Quiz**
**GQ1.** Name the four core macro variables that drive markets.
**GQ2.** All else equal, when the central bank *raises* rates, what typically happens to bond prices and to the currency?
**GQ3.** What does an *inverted* yield curve traditionally signal?
**GQ4.** What are the four parts of a good market-view pitch?

---

## Part 4 — Track D (Volatility Trading)

### Variance & volatility swaps — trading vol as an asset

Options give you volatility exposure, but it's *contaminated*: you must delta-hedge, and your realized-vol P&L depends on the path (where spot spends its time relative to your strikes — recall gamma is local). **Variance swaps** strip all that away and give **clean, direct exposure to realized volatility.**

**1. What a variance swap is.**
A forward contract on **realized variance**. Payoff at expiry:

> **Notional × ( realized variance − strike variance )**

where realized variance is the annualized sum of squared daily log returns over the life. You agree today on the **strike** (the "fair" variance, ≈ implied²); at expiry you're paid the difference. Long a variance swap = a pure bet that **realized vol > implied vol**, with no delta or gamma to manage.

**2. Volatility swap vs. variance swap.**
A **volatility swap** pays on realized *vol* (the square root of variance) rather than variance. It's more intuitive (linear in vol), but **harder to replicate** because the square root is nonlinear. **Variance swaps dominate** in practice precisely because variance *can* be replicated with a static option portfolio.

**3. The log-strip replication (the beautiful result).** ⭐
A variance swap can be replicated by a **static portfolio of options across all strikes, weighted by `1/K²`**, plus a dynamic delta hedge — the so-called **log contract** (it replicates the payoff `−2·ln(S_T/S_0)`). Key consequences:
- You capture **total realized variance** regardless of the path — no gamma-vs-strike dependence, because you hold *every* strike.
- This static strip is exactly the machinery behind the **VIX**: `VIX²` is computed as a variance-swap-style weighted sum of S&P option prices across strikes (then annualized and rooted).

**4. Two properties interviewers probe.**
- **The strike is above ATM implied vol.** Because the replication weights *all* strikes (including the high-vol OTM puts from the skew), the fair variance is a **skew-weighted average** — so a variance swap is structurally **long skew**.
- **Convexity in vol.** Since variance = vol², a variance swap is **convex** in volatility — it gains more from a vol spike than it loses from an equal vol drop (long "vol-of-vol"). That convexity is part of what you pay for in the strike.

**5. Why desks use them.**
Pure implied-vs-realized expression, clean **vega hedging**, and — most importantly for where we're headed — the building block of **dispersion**: going long single-name variance and short index variance (Day 18).

**Key intuition:** a variance swap turns "I think realized vol will beat implied" into a single clean instrument, replicable by a `1/K²`-weighted strip of options. It's the bridge from *hedging options* to *trading volatility itself*.

**Track D Quiz**
**DQ1.** What does a variance swap pay off on?
**DQ2.** Why are variance swaps, rather than volatility swaps, the standard tool for replication and hedging?
**DQ3.** How is a variance swap replicated using options?
**DQ4.** Why is a variance swap's strike typically *above* the at-the-money implied vol?

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Part 1 — Probability & EV

**A1 — 2/3.**
For the maximum of two independent U(0,1) draws, `P(max ≤ x) = x²`, so the density is `2x` and `E[max] = ∫₀¹ x·2x dx = 2/3`. (Check: `E[min] = 1/3`, and `E[max]+E[min] = 1 = ` the total.)

**A2 — ≈ 58.5%.**
`P(recession | fire) = (0.15·0.8)/(0.15·0.8 + 0.85·0.1) = 0.12/(0.12 + 0.085) = 0.12/0.205 ≈ **0.585 ≈ 58.5%**`.

**A3 — (a) +$100; (b) ≈ 68.3%.**
(a) Each trade's EV = `0.6·100 − 0.4·100 = +$20`; five of them → `**+$100**`. (b) `P(≥3 winners) = C(5,3)(0.6)³(0.4)² + C(5,4)(0.6)⁴(0.4) + (0.6)⁵ = 0.3456 + 0.2592 + 0.0778 ≈ **0.683**`.

**A4 — $95.24.**
`Price = 100 / 1.05 ≈ **$95.24**` — the present value of $100 discounted one year at 5%.

**A5 — 2/3.**
You win on flip 1 (½), or both miss and you're back to the start: `P = (½)/(1 − ¼) = (½)/(¾) = **2/3**`. Going first is a real edge. (Compare the die version — first to roll a six — which was 6/11 on Day 4; the coin's higher per-turn success makes first-mover advantage bigger.)

## Part 2 — Brainteaser

**12 cubes.**
The small cubes with exactly two painted faces are the **edge** cubes that aren't corners. A cube has **12 edges**, and on a 3×3×3 each edge has exactly **one** middle cube (the corners take the ends). So `12 × 1 = **12**`. (Full census: 8 corners with 3 faces, 12 edges with 2, 6 face-centers with 1, 1 core with 0 — totaling 27. ✓)

## Part 3 — Track G Quiz

**GAQ1.** **Growth, inflation, monetary policy (interest rates), and employment.**

**GAQ2.** Bond prices **fall** (yields rise); the currency tends to **strengthen** (higher yields attract carry).

**GAQ3.** That the market expects the central bank to **cut rates** — i.e., an anticipated **economic slowdown / recession**.

**GAQ4.** **Thesis** (one line) → **Drivers** (2–3 reasons) → **The trade** (how you'd express it) → **The risk** (what would make you wrong).

## Part 4 — Track D Quiz

**DAQ1.** The difference between **realized variance and the strike variance**, times the notional — i.e., annualized realized variance (sum of squared daily log returns) minus the agreed strike.

**DAQ2.** Because **variance is replicable with a static strip of options** (the log contract), making it cleanly hedgeable; volatility is the square root of variance — **nonlinear and not statically replicable**, so vol swaps are harder to price and hedge.

**DAQ3.** With a **static portfolio of options across all strikes weighted by `1/K²`** (the log contract), combined with a dynamic delta hedge. This is also the basis of the VIX calculation.

**DAQ4.** Because the replicating strip weights **all** strikes, including high-implied-vol OTM puts from the skew, so the fair variance is a **skew-weighted average** that sits above the single ATM implied vol — a variance swap is structurally long skew.

---

*Tomorrow (Day 18): **big cumulative quiz day** — Track G: rates & fixed income I (the yield curve, duration, DV01); Track D: correlation & dispersion — and Part 5 reviews Days 16–18 across both tracks.*
