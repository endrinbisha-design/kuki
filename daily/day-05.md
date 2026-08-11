# Day 5 — 2026-08-08

Work top-to-bottom. **Don't scroll to the Answers section** until you've attempted everything.

---

## Part 1 — Probability & Expected Value (5 questions)

**Q1. Prime sum.**
You roll two fair dice. What is the probability their sum is a *prime* number?

**Q2. Which urn?**
Urn A holds 2 white and 1 black ball; Urn B holds 1 white and 3 black. You pick an urn at random and draw one ball — it's white. What is the probability it came from Urn A?

**Q3. Sit together.**
Five people take five seats in a row at random. What is the probability that two specific people, Alice and Bob, end up sitting next to each other?

**Q4. Square payoff.**
You pay $5 to roll a fair die and are paid, in dollars, the *square* of the number shown. What is your expected net profit per play — is it worth playing?

**Q5. Two heads in a row.**
You flip a fair coin repeatedly until you first see two heads in a row (HH). What is the expected number of flips?

---

## Part 2 — Brainteaser

**The bridge at night.**
Four people must cross a rickety bridge in the dark. They have one flashlight, and at most two people can cross at a time — and anyone crossing must carry the flashlight (so someone has to bring it back). They walk at different speeds: they take **1, 2, 5, and 10 minutes** respectively to cross, and a pair moves at the *slower* person's pace. What is the minimum total time to get all four across, and how?

---

## Part 3 — Black-Scholes Lesson

### Day 5: Pricing puts, and put-call parity

Yesterday we priced a call. Two questions remain: how do we price a *put*, and is there a shortcut linking the two? Yes — and the link is one of the cleanest no-arbitrage results in finance.

**1. The put formula.**
Using the *same* `d1` and `d2` from Day 4, the European put price is:

> **P = K · e^(−rT) · N(−d2) − S · N(−d1)**

Same ingredients, mirrored: `N(−d2)` is the risk-neutral probability the put finishes in the money (stock *below* strike). But you rarely need to memorize this separately — because of the next result.

**2. Put-call parity.** ⭐
For European options on a non-dividend stock, with the same strike `K` and expiry `T`:

> **C − P = S − K · e^(−rT)**

*Why it's true (pure no-arbitrage).* Consider being **long one call and short one put**, same `K` and `T`. At expiry the payoff is:
`max(S − K, 0) − max(K − S, 0) = S − K` — *in every scenario* (if S > K the call pays S−K and the put is worthless; if S < K you're assigned on the put for −(K−S) = S−K; if S = K both are zero). So "long call + short put" pays exactly `S − K` at expiry — that's a **forward** on the stock.

A portfolio that delivers `S − K` at expiry can be built today as: **own the stock** (worth `S`) and **borrow the present value of the strike** (owe `K·e^(−rT)`). Its cost today is `S − K·e^(−rT)`. Since both packages have identical payoffs, no-arbitrage forces identical prices:
`C − P = S − K·e^(−rT)`. ∎

**3. What parity buys you.**
- **Derive one from the other:** `P = C − S + K·e^(−rT)`. Price a call, get the put for free.
- **Spot arbitrage:** if market prices make `C − P ≠ S − K·e^(−rT)`, you can lock a riskless profit by buying the cheap package and selling the rich one.
- **Build synthetics:** rearranging gives, e.g., *synthetic long stock = long call + short put + lend K·e^(−rT)*. Desks use this constantly to convert between exposures.

**4. Worked example.**
From Day 4: `S = 100, K = 100, r = 5%, T = 1`, and we found `C ≈ $10.45`. The put:
`P = C − S + K·e^(−rT) = 10.45 − 100 + 100·e^(−0.05) = 10.45 − 100 + 95.12 = **$5.57**`.
Check straight from the put formula: `P = 95.12·N(−0.15) − 100·N(−0.35) = 95.12·0.4404 − 100·0.3632 = 41.89 − 36.32 = $5.57` ✓.

Notice `C > P` even though the option is exactly at-the-money. That's the interest rate at work: the call holder gets to *defer* paying the strike, and that deferral is worth `K − K·e^(−rT) = $4.88` — exactly the gap `10.45 − 5.57`.

**Key intuition to carry forward:** puts aren't a separate mystery — a call and a put on the same strike are two faces of the same forward. Put-call parity ties their prices together by pure no-arbitrage, no model required. It's also a favorite interview check: "if the call is worth X, what's the put worth?"

---

## Part 4 — Lesson Quiz (5 questions)

**QZ1.** State put-call parity for European options on a non-dividend-paying stock.

**QZ2.** A call and put share strike $100, with `S = $100`, `r = 0`, `T = 1`. If the call is worth $8, what is the put worth?

**QZ3.** "Long one call and short one put" (same strike & expiry) replicates what simple position?

**QZ4.** Suppose the market shows `C − P > S − K·e^(−rT)`. Sketch the trade that captures the arbitrage.

**QZ5.** Using Day 4's numbers (`C ≈ $10.45, S = 100, K = 100, r = 5%, T = 1`), what is the put worth, and why is it less than the call?

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Part 1 — Probability & EV

**A1 — 5/12.**
Prime sums are 2, 3, 5, 7, 11. Their counts out of 36: 2→1, 3→2, 5→4, 7→6, 11→2, totaling `1+2+4+6+2 = 15`. So `15/36 = **5/12 ≈ 0.417**`.

**A2 — 8/11.**
`P(white | A) = 2/3`, `P(white | B) = 1/4`, each urn chosen w.p. ½.
`P(A | white) = (½·⅔) / (½·⅔ + ½·¼) = (1/3) / (1/3 + 1/8) = (1/3)/(11/24) = 8/11 ≈ **0.727**`.

**A3 — 2/5.**
Adjacent seat-pairs in a row of 5: there are 4, each usable as AB or BA (×2), with the other 3 people in `3!` orders: favorable `= 4·2·3! = 48`. Total arrangements `= 5! = 120`. `48/120 = **2/5**`.

**A4 — +$10.17 (yes, play).**
`E[face²] = (1 + 4 + 9 + 16 + 25 + 36)/6 = 91/6 ≈ 15.17`. Net of the $5 cost: `15.17 − 5 = **+$10.17**` per play — a strongly positive edge.

**A5 — 6 flips.**
Let `E` be the expected flips to get HH. Condition on the first flip: with a tail (p ½) you've wasted 1 flip and restart; with a head (p ½) you need a second head — if it comes (½) you're done in 2, else (½) you restart having used 2. Solving `E = ½(1 + E) + ½[½·2 + ½·(2 + E)]` gives `E = **6**`. (Pattern with a self-overlap like HH waits longer than a naive guess.)

## Part 2 — Brainteaser

**The bridge — 17 minutes.**
Send the **two fastest first, and shuttle the flashlight back with the fastest**:
1. **1 & 2 cross** → 2 min (both on far side).
2. **1 returns** → 1 min.
3. **5 & 10 cross** → 10 min (get the two slowpokes over *together*).
4. **2 returns** → 2 min.
5. **1 & 2 cross** → 2 min.
Total = `2 + 1 + 10 + 2 + 2 = **17 minutes**`. The key insight: don't let the 10-minute person cross with the 5-minute person *and* also make either escort the slow crossings — pair the two slowest together so you only "pay" 10 once, and use the fastest two as ferriers.

## Part 4 — Lesson Quiz

**AZ1.** `C − P = S − K·e^(−rT)` (same strike `K` and expiry `T`).

**AZ2.** With `r = 0`, parity is `C − P = S − K = 100 − 100 = 0`, so `P = C = **$8**`.

**AZ3.** A **forward** (synthetic long stock): it pays `S − K` at expiry regardless of where the stock lands.

**AZ4.** The left side (`C − P`) is too rich, so **sell the call, buy the put, buy the stock, and borrow `K·e^(−rT)`**. The options + stock deliver a guaranteed `S − K` offset while you collected more than `S − K·e^(−rT)` up front — the difference is locked-in riskless profit.

**AZ5.** `P = C − S + K·e^(−rT) = 10.45 − 100 + 95.12 = **$5.57**`. It's cheaper than the call because, at the same strike, the call holder defers paying `K` and earns interest on it in the meantime — worth `K − K·e^(−rT) = $4.88`, exactly the `10.45 − 5.57` gap.

---

*Tomorrow (Day 6): a deeper look at what `N(d1)` and `N(d2)` really mean — **plus the second big cumulative quiz, covering Days 4–6.***
