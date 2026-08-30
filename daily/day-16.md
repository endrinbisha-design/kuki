# Day 16 — 2026-08-19  ·  Phase 2, Day 1 (two tracks)

Phase 2 begins: two tracks a day — **Track G (generalist S&T)** and **Track D (vol trading)**. Work top-to-bottom; **answers with explanations are at the very end.**

---

## Part 1 — Probability & Expected Value (5 questions)

**Q1. Make a market on the coins.**
You will flip a fair coin 10 times and count the heads. What is the fair value (the mid you'd quote), and roughly what is the standard deviation of the outcome?

**Q2. The cheerful trader.**
A trader is profitable on 60% of days. When profitable he's cheerful 90% of the time; when not, cheerful only 30% of the time. He walks in cheerful today. What's the probability he's having a profitable day?

**Q3. Sum of three dice.**
You roll three fair dice. What is the probability the sum equals exactly 10?

**Q4. Adverse selection.**
You buy an asset at your bid of $48. Normally its true value is $50 (you make $2), but 30% of the time you're trading against someone informed and the true value is actually $45. What is your expected profit on a buy?

**Q5. No two heads in a row.**
You flip a fair coin 4 times. What is the probability that no two heads are adjacent?

---

## Part 2 — Brainteaser

**Fair result from a biased coin.**
You have a coin that lands heads with some *unknown* probability `p` (0 < p < 1), possibly far from ½. Using only this biased coin, how can you generate a perfectly fair 50/50 decision?

---

## Part 3 — Track G (Generalist S&T)

### Market-making & microstructure

A market-maker is the counterparty who's *always* willing to trade — quoting a price to buy (**bid**) and a price to sell (**ask/offer**) — and gets paid for providing that liquidity. Understanding how they make (and lose) money is the backbone of trading intuition, and it comes up in nearly every S&T interview ("make me a market on X").

**1. The basic edge: the spread.**
Quote `48 bid / 52 ask` on something worth 50. Buy at 48 or sell at 52 and you capture the **half-spread** ($2) versus fair value. If buys and sells arrive equally and randomly, you earn the half-spread per trade — that's the liquidity provider's bread and butter (you priced this on Day 2/Day 13).

**2. The main cost: adverse selection.**
Not all flow is random. Some counterparties know something you don't (news, a big order coming). When you trade against **informed flow**, your fills are systematically on the wrong side — you buy right before it drops, sell right before it pops. **Net edge = spread captured − adverse-selection cost.** This is *the* central tension: quote tight to win flow, but tight quotes get picked off harder.

**3. Inventory risk and quote skewing.**
Every fill leaves you holding a position you didn't necessarily want. If you're **long too much inventory**, you *skew your quotes down* — lower both your bid and your ask — so you're more likely to sell (offload) and less likely to buy more. Skewing is how a maker steers its book back toward flat without crossing the spread and paying up.

**4. What sets the spread width.**
You **widen** when: volatility is high, liquidity is thin, size is large, you fear informed flow, or there's an event pending. You **tighten** when competition is fierce and flow is benign. The spread is a risk premium for immediacy and adverse selection.

**5. The interview version.**
"Make me a market on [the number of home runs this season / the temperature tomorrow / a stock]." A good answer: state a *tight, confident two-way* around your fair estimate, size it, and — when they trade against you — **update and skew** ("you lifted my offer, so I'll move both up"). They're testing whether you price around an estimate, manage risk, and stay composed as information arrives, not whether you're exactly right.

**Key intuition:** a market-maker sells *immediacy* and buys *adverse selection*; profit is the spread minus what the informed take out of you, and inventory is managed by skewing quotes, not by hoping.

**Track G Quiz**
**GQ1.** What is a market-maker's basic source of profit, and what is its main offsetting cost?
**GQ2.** You're holding too much long inventory and want to reduce it. How do you adjust your two-way quote?
**GQ3.** Name two conditions under which you'd widen your bid-ask spread.
**GQ4.** In one sentence, what is adverse selection?

---

## Part 4 — Track D (Volatility Trading)

### The volatility surface in depth

You know implied vol varies by **strike** (skew/smile, Day 12). It also varies by **expiry** (term structure). Put both dimensions together and you get the **vol surface** — the object a derivatives desk actually risk-manages. Today: how the surface is shaped and, crucially, how it *moves*.

**1. Two axes.**
- **Skew / smile** (across strike, fixed expiry): equities slope down (OTM puts richest); often quoted as a **25-delta risk reversal** (25Δ put vol minus 25Δ call vol) and a **butterfly** (wing vol vs. ATM).
- **Term structure** (across expiry, fixed moneyness): usually **upward-sloping in calm markets** (longer options imply more vol — "contango"), and it **inverts/backwardates before a known event or in a crisis**, when *short*-dated vol spikes above long-dated.

**2. Forward volatility.**
Just as a yield curve implies forward interest rates, the vol term structure implies **forward vol** — the volatility expected *between* two future dates. Calendar spreads are essentially trades on forward vol (e.g., "is the vol the market implies for months 2–3 too high given the event calendar?").

**3. The part that trips people up: how does the surface move with spot?** ⭐
This determines your *actual* hedge. Two idealized regimes:
- **Sticky strike:** implied vol at each *fixed strike* stays put as spot moves. Then as spot rises, the ATM point slides *down* the skew to a lower vol.
- **Sticky delta (sticky moneyness):** implied vol at each *delta/moneyness* stays put; the whole smile **shifts sideways with spot**, so ATM vol is unchanged.

Reality is somewhere between (and in fast selloffs, vol often rises *more* than either predicts). Why care? Because on a skewed surface, **vol changes as spot moves**, so your true delta isn't the textbook Black-Scholes delta — there's an extra `vega × (∂σ/∂S)` term. Get the sticky assumption wrong and your "delta-hedged" book is quietly long or short the market.

**4. Managing the surface.**
A vol book's risk is **vega spread across strikes and expiries** — desks bucket it (short-dated vs. long-dated vega, skew exposure, term-structure exposure) rather than tracking one number. You can be net-flat vega yet dangerously exposed to the skew *steepening* or the term structure *inverting*.

**Key intuition:** the surface is a live, moving object. Its **shape** (skew + term structure) prices the market's fear across strikes and horizons; its **dynamics** (sticky-strike vs. sticky-delta) quietly change your delta and are where a lot of real P&L — and a lot of interview follow-ups — actually live.

**Track D Quiz**
**DQ1.** What are the two dimensions that define the volatility surface?
**DQ2.** Explain the difference between "sticky strike" and "sticky delta."
**DQ3.** A vol term structure that slopes *downward* (short-dated vol above long-dated) usually signals what?
**DQ4.** Why can your true delta differ from the Black-Scholes delta when the surface is skewed?

---
---

# ANSWERS

*(Scroll here only after attempting everything above.)*

## Part 1 — Probability & EV

**A1 — Mid 5; standard deviation ≈ 1.58.**
Heads in 10 fair flips is Binomial(10, ½): mean = `np = 5`, variance = `np(1−p) = 10·¼ = 2.5`, so SD = `√2.5 ≈ **1.58**`. You'd quote around 5, perhaps 4.5 / 5.5.

**A2 — 9/11 ≈ 0.818.**
Bayes: `P(profit | cheerful) = (0.6·0.9)/(0.6·0.9 + 0.4·0.3) = 0.54/(0.54+0.12) = 0.54/0.66 = **9/11 ≈ 0.818**`.

**A3 — 1/8.**
There are 27 ways for three dice to sum to 10 (one of the two modal sums, along with 11), out of 216: `27/216 = **1/8**`.

**A4 — +$0.50.**
`0.7·($50 − $48) + 0.3·($45 − $48) = 0.7·(2) + 0.3·(−3) = 1.4 − 0.9 = **+$0.50**`. Adverse selection cut your naive $2 edge to 50¢ — exactly the market-maker's core problem.

**A5 — 1/2.**
Length-4 binary strings with no two adjacent heads number `F(6) = 8` (Fibonacci), out of `2⁴ = 16`: `8/16 = **1/2**`.

## Part 2 — Brainteaser

**Von Neumann's trick — flip twice.**
Flip the biased coin **in pairs**. Map **HT → "heads"** and **TH → "tails"**; if you get **HH or TT, discard and repeat.** Since `P(HT) = p(1−p) = P(TH)` regardless of `p`, the two accepted outcomes are exactly equally likely — a perfect 50/50 — no matter how biased the coin is. (Expected pairs needed = `1 / [2p(1−p)]`.)

## Part 3 — Track G Quiz

**GAQ1.** Profit comes from **capturing the bid-ask spread** (buying at the bid, selling at the ask, around fair value); the main offsetting cost is **adverse selection** — losses to better-informed counterparties.

**GAQ2.** **Skew your quote down** — lower both your bid and your ask. That makes you more likely to sell (reduce the long) and less likely to add to it, steering inventory back toward flat.

**GAQ3.** Any two of: **high volatility**, **thin liquidity**, **large trade size**, **elevated adverse-selection/informed-flow risk**, or a **pending event/uncertainty**.

**GAQ4.** Adverse selection is trading against a counterparty with superior information, so your fills are systematically on the losing side (you buy just before drops, sell just before rallies).

## Part 4 — Track D Quiz

**DAQ1.** **Strike** (the skew/smile) and **expiry/time** (the term structure of volatility).

**DAQ2.** **Sticky strike:** each fixed strike keeps its implied vol as spot moves (so ATM vol changes, sliding along the skew). **Sticky delta:** each fixed delta/moneyness keeps its implied vol, so the whole smile shifts sideways with spot and ATM vol stays constant.

**DAQ3.** **Near-term stress or a pending event** — short-dated implied vol is elevated above long-dated (backwardation), typical of crises or right before a known catalyst.

**DAQ4.** Because on a skewed surface **implied vol moves as spot moves**, the option's value changes through vega as well as delta; the true (total) delta includes an extra `vega × (∂σ/∂S)` term, so it differs from the fixed-vol Black-Scholes delta.

---

*Tomorrow (Day 17): Track G — the macro map ("what's your view"); Track D — variance & volatility swaps and the log-strip replication.*
