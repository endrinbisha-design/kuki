# Day 1 — 2026-07-20

Work top-to-bottom. **Don't scroll to the Answers section** until you've attempted everything.

---

## Part 1 — Probability & Expected Value (5 questions)

**Q1. Dice game with a re-roll.**
You roll a fair six-sided die and are paid, in dollars, the number that shows. But before you're paid, you may choose to *re-roll once* — if you do, you must accept the second roll. Playing optimally, what is the fair value of this game?

**Q2. Two coins, one is rigged.**
A box holds two coins: one fair, one double-headed. You pick one at random and flip it — it lands heads. What is the probability you picked the double-headed coin?

**Q3. Same-color draw.**
A bag has 3 red and 2 blue balls. You draw 2 without replacement. What's the probability both are the same color?

**Q4. Is there an edge?**
A game pays you **+$10** with probability 0.45 and costs you **–$8** with probability 0.55. What is the expected value of one play? Would you play it repeatedly?

**Q5. Expected max of two dice.**
You roll two fair dice and are paid the *larger* of the two values (if they tie, that value). What is the expected payout?

---

## Part 2 — Brainteaser

**The two ropes.**
You have two ropes and a lighter. Each rope takes exactly 60 minutes to burn from one end to the other, but the ropes burn *unevenly* — half the rope might burn in 5 minutes and the other half in 55. Using only these two ropes and the lighter, how do you measure exactly **45 minutes**?

---

## Part 3 — Black-Scholes Lesson

### Day 1: Options foundations — and why we need a pricing model

Before any formula, you need a crisp mental model of the instrument itself. Black-Scholes exists to answer one question — *"what is a fair price for this option today?"* — so first, what is the thing?

**Options in one paragraph.**
An **option** is a contract giving its holder the *right, but not the obligation,* to trade an underlying asset at a fixed price by a fixed date.

- A **call** gives the right to **buy** the underlying at the **strike price** `K`.
- A **put** gives the right to **sell** the underlying at the strike price `K`.
- The **expiration** is the last date the right can be used. (We'll assume *European* style — exercisable only at expiry — because that's what Black-Scholes prices.)

**Payoff at expiry.** This is the anchor for everything. Let `S` be the stock price at expiry.

- Call payoff: `max(S − K, 0)` — you only exercise if the stock is above the strike.
- Put payoff: `max(K − S, 0)` — you only exercise if the stock is below the strike.

The "`max(…, 0)`" is the whole point: the *right-but-not-obligation* means your payoff is never negative at expiry. The most you can lose is the premium you paid up front.

**Moneyness** — where the stock sits relative to the strike:

| Term | Call | Put |
|------|------|-----|
| **In-the-money (ITM)** | `S > K` | `S < K` |
| **At-the-money (ATM)** | `S ≈ K` | `S ≈ K` |
| **Out-of-the-money (OTM)** | `S < K` | `S > K` |

**Intrinsic value vs. time value.** The price (premium) of an option splits into two pieces:

- **Intrinsic value** = what you'd get if it expired *right now* = `max(S − K, 0)` for a call. Never negative.
- **Time value** = premium − intrinsic value = everything you're paying for the *chance* the option gets more valuable before expiry.

Example: stock at $58, a $50-strike call trades at $10. Intrinsic value = `58 − 50 = $8`. Time value = `10 − 8 = $2`. That $2 is what the market charges for the remaining uncertainty and time.

**So why do we need a model?** Intrinsic value is easy. *Time value is the hard part.* It depends on:

1. How much time is left (`T`).
2. How volatile the stock is (`σ`) — more volatility → more chance of a big favorable move → more valuable option.
3. The risk-free interest rate (`r`).
4. The current stock price relative to strike (`S` vs. `K`).

Black-Scholes is precisely a formula that takes these inputs and outputs a fair time-value-inclusive price. The rest of this course builds up to *how* it does that — and the single most important input, the one traders obsess over, is **volatility**. That's where we go next (Day 2).

**Key intuition to carry forward:** an option is a bet on *where the stock ends up*, and its value is driven by the *distribution* of possible ending prices — not just the current price. Widen the distribution (more volatility) and both calls and puts get more valuable.

---

## Part 4 — Lesson Quiz (5 questions)

**QZ1.** A call option gives its holder the right to do what, and with what obligation?

**QZ2.** A call has strike $50. At expiry the stock is at $58. What is the call's payoff?

**QZ3.** That same call is trading (before expiry) at $10 while the stock is $58. What is its intrinsic value, and what is its time value?

**QZ4.** A put has strike $70 and the stock is at $82. Is the put in-, at-, or out-of-the-money? What is its intrinsic value?

**QZ5.** Two calls are identical except one expires in 1 week and the other in 6 months. Which is worth more, and which of the two value components explains the difference?

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Part 1 — Probability & EV

**A1 — $4.25.**
The re-roll is worth taking only when your first roll is *below* what you'd expect from a fresh roll (3.5). So you keep 4, 5, 6 and re-roll on 1, 2, 3.
- Keep (first roll is 4/5/6): happens with prob 1/2, average value = (4+5+6)/3 = 5.
- Re-roll (first roll is 1/2/3): happens with prob 1/2, and a fresh roll averages 3.5.
- Value = ½(5) + ½(3.5) = 2.5 + 1.75 = **$4.25**.

**A2 — 2/3.**
Bayes. P(heads | double-headed) = 1; P(heads | fair) = ½; each coin picked with prob ½.
P(double | heads) = (½·1) / (½·1 + ½·½) = (½) / (¾) = **2/3**. Intuition: the double-header produces heads twice as often as the fair coin, so seeing heads makes it twice as likely — 2:1 → 2/3.

**A3 — 0.4.**
Total ways to draw 2 of 5 = C(5,2) = 10. Both red = C(3,2) = 3. Both blue = C(2,2) = 1. Same color = (3+1)/10 = **0.4**.

**A4 — EV = +$0.10; yes, play it repeatedly.**
EV = 0.45·(+10) + 0.55·(−8) = 4.5 − 4.4 = **+$0.10** per play. It's a small positive edge, so over many independent plays you expect to profit (subject to bankroll — the swings are large relative to the tiny edge, so size accordingly).

**A5 — 161/36 ≈ $4.47.**
For the max `M` of two dice, P(M = k) = (2k−1)/36 (the number of pairs whose larger value is exactly k). So
E[M] = Σ k·(2k−1)/36 = (1/36)Σ(2k²−k) = (1/36)(2·91 − 21) = 161/36 ≈ **4.47**.
Sanity check: E[max] + E[min] = E[sum] = 7, and 161/36 + 91/36 = 252/36 = 7. ✓

## Part 2 — Brainteaser

**The two ropes — light three ends at once.**
At time 0: light **both ends of rope A** and **one end of rope B**.
- Rope A, burning from both ends, is consumed in **30 minutes** (the two flames meet after half the total burn time, regardless of unevenness).
- The instant rope A finishes (t = 30), **light rope B's other end.** Rope B had 30 minutes of burn left; lighting the second end halves that to **15 minutes**.
- Rope B finishes at t = 30 + 15 = **45 minutes**. ✓
Key trick: burning a rope from both ends always consumes it in half its total time, no matter how unevenly it burns.

## Part 4 — Lesson Quiz

**AZ1.** The right — *but not the obligation* — to **buy** the underlying at the strike price on/by expiry. The "no obligation" is what caps the holder's loss at the premium.

**AZ2.** `max(58 − 50, 0) = $8`.

**AZ3.** Intrinsic value = `max(58 − 50, 0) = $8`. Time value = price − intrinsic = `10 − 8 = $2`.

**AZ4.** Stock $82 > strike $70, so a *put* is **out-of-the-money** (you'd never sell at 70 when the market is 82). Intrinsic value = `max(70 − 82, 0) = $0`.

**AZ5.** The **6-month** call is worth more. Both have the same intrinsic value (identical strike & current stock); the difference is entirely **time value** — more time means more chance for a favorable move, so the market charges more for it.

---

*Tomorrow (Day 2): where price uncertainty actually comes from — returns, volatility, and the lognormal picture that Black-Scholes is built on.*
