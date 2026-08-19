# Day 8 — 2026-08-11

Work top-to-bottom. **Don't scroll to the Answers section** until you've attempted everything.

---

## Part 1 — Probability & Expected Value (5 questions)

**Q1. Expected gap.**
You roll two fair dice. What is the expected value of the *absolute difference* between the two numbers?

**Q2. Rare gene.**
A gene is present in 1 in 1,000 people. A test never misses a true carrier (100% sensitivity) but has a 5% false-positive rate. Someone tests positive. What is the probability they actually carry the gene?

**Q3. At least two heads.**
You flip a fair coin 4 times. What is the probability of getting *at least* 2 heads?

**Q4. Face-card game.**
It costs $2 to play: you draw one card from a standard 52-card deck and win $10 if it's a face card (J, Q, or K), otherwise nothing. What is your expected net profit per play?

**Q5. Collecting all six.**
You roll a fair die repeatedly. What is the expected number of rolls until you have seen *all six* faces at least once?

---

## Part 2 — Brainteaser

**The ship's ladder.**
A rope ladder hangs over the side of a ship, its rungs spaced 1 foot apart. At the moment you look, exactly the bottom rung touches the water. The tide comes in, raising the water level by 6 inches every hour. After 6 hours, how many rungs are underwater?

---

## Part 3 — Black-Scholes Lesson

### Day 8: Gamma — how delta itself moves

Yesterday's punchline: delta doesn't stay put. **Gamma** is the Greek that measures exactly *how fast delta changes* — and it's what separates a static hedge from the real, dynamic thing.

**1. Definition.**
**Gamma (Γ) = ∂Δ/∂S = ∂²(price)/∂S²** — the rate of change of delta per $1 move in the stock. It's the *second* derivative of the option price: the **curvature** (convexity) of the price-vs-stock curve.

- A call/put with Γ = 0.04 sees its delta change by ≈ 0.04 for each $1 the stock moves.
- **Gamma is identical for a call and a put** of the same strike and expiry (they share the same curvature).
- Gamma is always **positive for a long option** (owning options gives you positive convexity).

**2. Where gamma lives.**
Gamma is **largest for at-the-money options, and grows as expiry approaches** — right at the money near expiry, delta flips from ~0 to ~1 over a tiny price range, so it's extremely sensitive. Deep ITM or deep OTM options have delta pinned near 1 or 0, so their delta barely moves → **low gamma**.

**3. Long gamma vs. short gamma — the feel of it.**

- **Long gamma** (you *own* options): as the stock rises your delta *increases* (you automatically get longer into a rally); as it falls your delta *decreases* (you get shorter into a selloff). When you re-hedge to stay neutral you end up **buying low and selling high** — big moves *make* you money. The price of this: **you pay theta** (time decay, Day 9).
- **Short gamma** (you're *short* options): the mirror image — re-hedging forces you to **buy high and sell low**, so large moves *hurt*. Your compensation: **you collect theta**.

This is the central tension of an options desk: **gamma vs. theta**. You either pay time decay to own convexity (betting realized moves will be big), or you collect time decay by being short convexity (betting moves will be small).

**4. The delta-gamma approximation.**
For a move `ΔS`, the option's price change is approximately:

> **ΔC ≈ Δ·ΔS + ½·Γ·(ΔS)²**

The first term is the delta (directional) piece; the second is the **gamma (convexity)** piece. That `½·Γ·(ΔS)²` is *always positive* for a long-option holder — which is exactly why a **delta-hedged long-option position still makes money on a big move in either direction.** The directional part is hedged away; the convexity part is pure profit from movement.

**5. Worked example.**
An option has delta 0.50 and gamma 0.04. The stock jumps **+$2**.
- New delta ≈ `0.50 + 0.04×2 = 0.58` (you're now longer).
- Convexity P&L on a delta-hedged long position ≈ `½·Γ·(ΔS)² = ½·0.04·(2²) = ½·0.04·4 = **$0.08 per share**` — and you'd earn about the same $0.08 if the stock had instead dropped $2. Movement itself is the payoff.

**Key intuition to carry forward:** delta tells you your current directional exposure; **gamma tells you how quickly that exposure changes**, and therefore how often you must re-hedge and how much big moves help or hurt you. Owning gamma = owning convexity = a bet that the stock will *move a lot*; the bill for that bet arrives as theta, which is tomorrow's lesson.

---

## Part 4 — Lesson Quiz (5 questions)

**QZ1.** Define gamma in terms of delta and in terms of the option price.

**QZ2.** For what moneyness and what time-to-expiry is gamma the largest?

**QZ3.** Is gamma the same or different for a call versus a put with the same strike and expiry?

**QZ4.** You are long options (long gamma) and delta-hedged. Do large stock moves help or hurt you — and what do you pay for that?

**QZ5.** An option has delta 0.50 and gamma 0.05. If the stock rises $3, what is the option's new approximate delta?

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Part 1 — Probability & EV

**A1 — 35/18 ≈ 1.94.**
Summing `|i − j|` over all 36 ordered pairs gives 70 (differences of 0,1,2,3,4,5 occur 6,10,8,6,4,2 times → `0+10+16+18+16+10 = 70`). Expected value = `70/36 = **35/18 ≈ 1.944**`.

**A2 — ≈ 1.96%.**
`P(gene | +) = (0.001·1) / (0.001·1 + 0.999·0.05) = 0.001 / 0.05095 ≈ **0.0196 ≈ 2%**`. Even a perfectly sensitive test with a 5% false-positive rate leaves a positive result mostly wrong when the trait is rare — base rates again.

**A3 — 11/16.**
`P(≥2 heads) = [C(4,2)+C(4,3)+C(4,4)]/2⁴ = (6+4+1)/16 = **11/16 ≈ 0.688**`.

**A4 — +$0.31.**
`P(face card) = 12/52 = 3/13`. Expected winnings = `10·(3/13) = 30/13 ≈ $2.31`. Net of the $2 cost: `2.31 − 2 = **+$0.31**` per play.

**A5 — 14.7 rolls.**
Coupon collector: `6·(1 + ½ + ⅓ + ¼ + ⅕ + ⅙) = 6·(2.45) = **14.7**`. (Each new face gets progressively harder to hit; the last one alone takes 6 rolls on average.)

## Part 2 — Brainteaser

**None — the ship floats.**
The ship rises with the incoming tide, so the ladder rises with it and the bottom rung stays at the waterline. **Zero rungs** go underwater. (The "6 rungs" trap assumes the ship is fixed to the sea floor.)

## Part 4 — Lesson Quiz

**AZ1.** Gamma = `∂Δ/∂S` (rate of change of delta per $1 stock move) = `∂²(price)/∂S²` (the second derivative / curvature of the option price in the stock).

**AZ2.** Gamma is largest for **at-the-money** options and **as expiry approaches** (short time to expiry).

**AZ3.** **The same** — a call and a put with identical strike and expiry have equal gamma.

**AZ4.** Large moves **help** you (positive convexity, `+½Γ(ΔS)²`, regardless of direction), but you **pay theta** — time decay — for holding that long-gamma position.

**AZ5.** New delta ≈ `0.50 + 0.05×3 = **0.65**`.

---

*Tomorrow (Day 9): **Theta** — time decay, the rent you pay to be long gamma — **plus the third big cumulative quiz, covering Days 7–9 (the Greeks so far).***
