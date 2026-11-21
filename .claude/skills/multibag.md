---
name: nse-multibagger-analyzer
description: Analyze Indian/NSE listed companies to identify potential multibagger candidates using 3-5 year financial trends, financial inflection, cash flow, balance sheet quality, valuation, promoter/governance signals, and the latest 3-4 earnings conference calls. Use this skill when the user provides an NSE stock list or asks to identify, rank, compare, or research potential Indian multibagger stocks.
---

# NSE Multibagger Analyzer

## Objective

Identify Indian/NSE listed companies where the underlying business economics are improving significantly and where the improvement could potentially support substantial future earnings growth.

The framework should NOT simply identify companies with:

- High ROE
- High ROCE
- High profit growth
- Low P/E
- Large order books

Instead, identify companies where:

> Business quality + financial performance + management commentary + future growth runway + valuation

are aligned.

The most important concept is:

> **Financial Inflection**

A company becoming materially better can be more interesting than a company that is already excellent but growing slowly.

This is an equity research and screening framework, NOT a guarantee of future returns or an investment recommendation.

---

# 1. INPUT

Accept:

- NSE symbols
- BSE symbols
- Company names
- Comma-separated stock lists
- Watchlists
- CSV files
- Excel files

Example:

COFORGE, CONCOR, DIXON, ETERNAL, HCLTECH, HEROMOTOCO, HYUNDAI, NAUKRI, LT, M&M, MAZDOCK, MOTILALOFS, PGEL, PERSISTENT, PETRONET, PNB, TECHM

Normalize company names and symbols before analysis.

If the user gives an ambiguous company name, identify the correct listed company before proceeding.

---

# 2. RESEARCH PRINCIPLE

Analyze every company using this sequence:

Financial Statements
        ↓
Financial Trend
        ↓
Financial Inflection
        ↓
Latest 3-4 Concalls
        ↓
Management Guidance
        ↓
Management Credibility
        ↓
Cross-check Management Claims
        ↓
Business Growth Drivers
        ↓
Risks / Red Flags
        ↓
Valuation
        ↓
100-point Multibagger Score
        ↓
Ranking
        ↓
Top Candidates
        ↓
Deep Dive

Do not skip the concall analysis.

---

# 3. DATA COLLECTION

For each company collect, where available:

## Financial Data

Prefer:

- Annual reports
- Quarterly results
- Investor presentations
- Company filings
- Official exchange filings
- Reliable financial databases

Collect at least:

- 5-year revenue
- 5-year EBITDA/Operating Profit
- 5-year PAT
- 5-year EPS
- 5-year ROCE
- 5-year ROE
- Debt
- Cash
- CFO
- Capex
- Free cash flow
- Receivables
- Inventory
- Payables
- Promoter holding
- Promoter pledge
- Share count/dilution
- Current valuation

Use consolidated numbers where appropriate.

---

# 4. CONCALL DATA COLLECTION

For every company collect the latest:

> **3-4 earnings conference calls**

Prefer official company sources.

Also collect:

- Investor presentations
- Earnings releases
- Management commentary
- Guidance
- Q&A sections

If an official transcript is unavailable, use reliable secondary sources and clearly identify the source.

Never pretend to have analyzed a concall if the transcript or recording was not available.

---

# 5. FINANCIAL ANALYSIS

Analyze the following dimensions.

---

## 5.1 Revenue Growth

Calculate:

- 3-year revenue CAGR
- 5-year revenue CAGR
- Latest TTM growth
- Latest quarterly YoY growth
- Revenue growth acceleration/deceleration

Look for:

Revenue:

10%
12%
18%
25%

This is a strong acceleration signal.

Do not reward only high historical growth.

Reward improving growth trajectory.

---

## 5.2 PAT Growth

Calculate:

- 3-year PAT CAGR
- 5-year PAT CAGR
- Latest quarterly PAT growth
- TTM PAT growth
- PAT growth versus revenue growth

Strong signal:

PAT growth > Revenue growth

Example:

Revenue +20%
PAT +35%

Investigate for:

- Operating leverage
- Margin expansion
- Cost efficiencies

Also investigate if PAT growth is caused by:

- Exceptional income
- Other income
- Tax benefits
- Asset sales
- One-time gains

---

## 5.3 EPS Growth

Always compare:

PAT growth vs EPS growth.

A company may grow PAT significantly while issuing new shares.

Example:

PAT +30%
EPS +10%

This should reduce the score.

Prefer:

PAT +30%
EPS +28%

---

# 6. EBITDA / OPERATING MARGIN

Analyze at least 4-5 years.

Example:

FY23: 10%
FY24: 11%
FY25: 13%
FY26: 16%

This is a strong positive signal.

Look for:

Revenue growth
+
Margin expansion

This can create operating leverage.

Also identify:

- Gross margin changes
- EBITDA margin
- EBIT margin
- Cost structure
- Pricing power

---

# 7. ROCE / ROE

Analyze:

- Current ROCE
- 3-year ROCE
- 5-year ROCE
- Current ROE
- 3-year ROE
- Trend

Do not only reward high ROCE.

Reward improvement.

Example:

12%
→
16%
→
21%
→
26%

is a strong financial inflection.

Also evaluate whether increasing ROCE is caused by:

- Better margins
- Better asset turnover
- Lower capital intensity
- Deleveraging

---

# 8. BALANCE SHEET

Analyze:

- Debt/Equity
- Net debt
- Interest coverage
- Borrowing trend
- Cash
- Net cash
- Working capital

Strong signal:

Revenue ↑
Profit ↑
Debt ↓

Example:

Revenue +25%
PAT +35%
Debt -20%

This is highly positive.

Red flags:

- Rapid debt increase
- Weak interest coverage
- Debt-funded growth with poor ROCE
- Frequent equity dilution
- Promoter pledge

---

# 9. CASH FLOW

Analyze:

- CFO
- CFO/PAT
- Free cash flow
- FCF trend
- CFO growth

Ideal:

CFO >= PAT over a multi-year period.

Investigate:

PAT +40%
CFO +5%

Potential concern.

Strong red flag:

PAT growing consistently while CFO remains weak or negative.

Determine why.

Possible reasons:

- Working capital buildup
- Receivables
- Inventory
- Aggressive accounting
- Expansion phase
- One-time effects

Do not automatically classify negative FCF as bad if the company is investing heavily in productive capacity.

---

# 10. WORKING CAPITAL

Analyze:

- Receivable days
- Inventory days
- Payable days
- Cash conversion cycle

Compare:

Revenue growth vs receivable growth.

Good:

Revenue +30%
Receivables +10%

Warning:

Revenue +20%
Receivables +60%

Also investigate:

Inventory growing much faster than sales.

Identify whether working capital is:

- Improving
- Stable
- Deteriorating

---

# 11. CAPEX AND CAPACITY

Analyze:

- Historical capex
- Current capex
- Planned capex
- New plants
- Capacity expansion
- Capacity utilization
- Asset turnover
- Order book
- New products
- New geographies

Ask:

> "Is the company investing today to support future earnings?"

Then ask:

> "Will the incremental capital generate attractive ROCE?"

Positive signal:

Capacity expansion
+
Strong demand
+
High utilization
+
High incremental ROCE

Negative signal:

Large capex
+
Weak demand
+
Low utilization
+
Poor returns

---

# 12. PROMOTER / GOVERNANCE

Analyze:

- Promoter holding
- Promoter holding trend
- Promoter pledge
- Insider selling
- Related-party transactions
- Share dilution
- Warrants
- Preferential allotments
- Auditor issues
- Contingent liabilities

Prefer:

- Stable/increasing promoter holding
- Zero promoter pledge
- Low dilution
- Clean governance

Flag serious governance concerns separately.

---

# 13. CONCALL INTELLIGENCE

This is a mandatory part of the analysis.

Analyze the latest 3-4 concalls.

Do NOT analyze only the latest call.

The objective is to determine:

> What has changed in management's expectations over the last 3-4 quarters?

---

# 14. CONCALL TREND TABLE

Create:

| Parameter | Q-4 | Q-3 | Q-2 | Latest |
|---|---|---|---|---|
| Demand | | | | |
| Revenue outlook | | | | |
| Margin outlook | | | | |
| Order book | | | | |
| Capacity | | | | |
| Utilization | | | | |
| New customers | | | | |
| New products | | | | |
| Geography | | | | |
| Capex | | | | |
| Guidance | | | | |
| Risks | | | | |

Identify the direction:

Improving
Stable
Deteriorating

---

# 15. CONCALL KEY FINDINGS

Extract the 5-8 most important developments across the last 3-4 calls.

Prioritize:

1. Demand
2. Growth
3. Margins
4. Order book
5. Capacity
6. New customers
7. New products
8. Market share
9. Pricing
10. Capex
11. Cash flow
12. Guidance

Avoid summarizing the entire call.

Focus on information that can affect future earnings.

---

# 16. MANAGEMENT GUIDANCE

Track management guidance across quarters.

Create:

| Quarter | Guidance | Actual | Result |
|---|---|---|---|
| Q1 | | | |
| Q2 | | | |
| Q3 | | | |
| Q4 | | | |

Determine:

- Guidance achieved
- Guidance exceeded
- Guidance missed
- Guidance delayed
- Guidance withdrawn

---

# 17. MANAGEMENT CREDIBILITY

This is extremely important.

Compare previous statements with actual results.

Example:

Q1:

"Margins will improve over the next two quarters."

Q2:

Margins decline.

Q2:

"Margins should recover in H2."

Q3:

Margins decline again.

Classify:

🔴 Management credibility concern.

Repeatedly postponed guidance should receive a significant penalty.

Conversely:

Management guidance
+
Actual execution
+
Repeated achievement

should increase the score.

---

# 18. MANAGEMENT LANGUAGE TREND

Track how management language changes.

Positive:

"Stable demand"

→

"Improving demand"

→

"Strong demand"

→

"Capacity constrained"

This is a strong GREEN signal.

Negative:

"Temporary weakness"

→

"Recovery next quarter"

→

"Recovery in H2"

→

"Recovery next year"

This is a RED signal.

---

# 19. CONCALL GREEN FLAGS

Identify explicit GREEN flags.

Examples:

🟢 Demand accelerating

🟢 Strong order pipeline

🟢 Market share gains

🟢 Capacity expansion

🟢 Capacity utilization improving

🟢 Margin expansion expected

🟢 New customer wins

🟢 New product ramp-up

🟢 New geography

🟢 Pricing power

🟢 Strong order book

🟢 Debt reduction

🟢 Strong cash generation

🟢 Guidance upgrade

🟢 Successful execution against previous guidance

List the strongest 3-5.

---

# 20. CONCALL RED FLAGS

Identify explicit RED flags.

Examples:

🔴 Guidance cut

🔴 Demand deterioration

🔴 Order cancellations

🔴 Margin compression

🔴 Capacity utilization falling

🔴 Project delays

🔴 Customer concentration

🔴 Rising working capital

🔴 Receivable problems

🔴 Regulatory issues

🔴 Commodity pressure

🔴 Pricing pressure

🔴 Repeated guidance delays

🔴 Management commentary inconsistent with financial data

🔴 Promoter/governance concerns

List the strongest 3-5.

---

# 21. YELLOW / WATCH ITEMS

Identify items that are not yet red flags but need monitoring.

Examples:

🟡 Temporary margin pressure

🟡 New plant ramp-up

🟡 Customer concentration

🟡 High valuation

🟡 Rising capex

🟡 Temporary working-capital increase

🟡 Currency headwinds

🟡 Dependence on one product

List 2-5 important watch items.

---

# 22. MANAGEMENT VS FINANCIAL DATA CROSS-CHECK

This is one of the most important parts of the skill.

Compare:

Management statements
vs
Financial evidence.

Example:

Management:

"Demand remains strong."

Financials:

Revenue growth declining
Order book declining
Inventory increasing
Receivables increasing

Flag:

🔴 MANAGEMENT / FINANCIAL DATA MISMATCH

---

Another example:

Management:

"We are seeing strong demand and expanding capacity."

Financials:

Revenue accelerating
Order book increasing
Capex increasing
ROCE improving

Flag:

🟢 MANAGEMENT COMMENTARY CONFIRMED BY FINANCIAL DATA

This should receive high conviction.

---

# 23. REPEATED THEMES

Identify themes mentioned repeatedly across the last 3-4 calls.

Examples:

- AI
- Capacity
- Export
- China+1
- Premiumization
- Market share
- New plant
- New product
- Order book
- Pricing
- Utilization
- Margin

Classify each recurring theme:

### Emerging

Mentioned recently.

### Developing

Mentioned repeatedly and supported by execution.

### Monetizing

Already contributing to revenue/profit.

### Delayed

Repeatedly discussed but not yet producing results.

### Failed

Previously expected but no longer progressing.

---

# 24. CONCALL SCORE

Give Concall Intelligence a score out of 20.

Base scoring:

| Signal | Points |
|---|---:|
| Demand improving | +3 |
| Revenue outlook improving | +2 |
| Margin outlook improving | +3 |
| Order book improving | +2 |
| Capacity expansion | +2 |
| New customers/products | +2 |
| Guidance upgraded | +3 |
| Strong execution against guidance | +3 |

Maximum:

20 points.

Subtract for:

- Guidance cuts
- Repeated delays
- Margin deterioration
- Demand weakness
- Order cancellations
- Working capital deterioration
- Management credibility concerns

Do not allow the score to exceed 20 or fall below 0.

---

# 25. CONCALL VERDICT

Classify:

### 🚀 Strong Positive

Management commentary and financial evidence both improving.

### 🟢 Positive

Mostly positive with limited concerns.

### 🟡 Mixed

Positive business but meaningful uncertainty.

### 🟠 Caution

Several warning signals.

### 🔴 Negative

Management commentary and financial data deteriorating.

---

# 26. FINANCIAL INFLECTION SCORE

Evaluate the direction of:

1. Revenue growth
2. EBITDA margin
3. PAT growth
4. EPS growth
5. ROCE
6. Debt
7. CFO
8. Working capital
9. Capex
10. Capacity utilization

Classify:

### STRONG INFLECTION

Most important metrics improving simultaneously.

### MODERATE INFLECTION

Some metrics improving.

### NO INFLECTION

Business stable but no meaningful change.

### NEGATIVE INFLECTION

Business economics deteriorating.

---

# 27. VALUATION

Analyze:

- P/E
- EV/EBITDA
- PEG
- Price/Sales where appropriate
- Historical P/E
- Historical valuation range
- Sector valuation
- Expected earnings growth

Do NOT automatically reject high P/E companies.

Instead ask:

> "What earnings growth is already priced into the stock?"

A high P/E with strong accelerating growth may be justified.

A high P/E with slowing growth is dangerous.

---

# 28. 100-POINT MULTIBAGGER SCORE

Use:

| Component | Weight |
|---|---:|
| Revenue Growth & Acceleration | 10 |
| PAT / EPS Growth | 10 |
| EBITDA Margin Expansion | 10 |
| ROCE / ROE | 10 |
| Balance Sheet | 10 |
| Cash Flow | 10 |
| Working Capital | 5 |
| Capex / Capacity | 5 |
| Promoter / Governance | 5 |
| Valuation | 5 |
| Concall Intelligence | 20 |
| **TOTAL** | **100** |

---

# 29. SCORE INTERPRETATION

### 85-100

🚀 Exceptional candidate

Strong financials + strong inflection + strong management commentary.

Requires deep research.

### 75-84

🟢 Strong candidate

Good fundamentals with meaningful growth drivers.

### 65-74

🟡 Watchlist

Good company or emerging opportunity but some uncertainty.

### 50-64

🟠 Average / speculative

Needs significant improvement.

### Below 50

🔴 Weak multibagger candidate

---

# 30. REQUIRED OUTPUT FOR EACH COMPANY

Produce:

## Company Name

### Overall Score

`82/100`

### Financial Score

`65/80`

### Concall Score

`17/20`

### Financial Inflection

`STRONG`

### Concall Verdict

`🟢 POSITIVE`

### Management Credibility

`8.5/10`

---

## Financial Snapshot

| Metric | Value | Trend | Signal |
|---|---:|---|---|
| Revenue CAGR | | | |
| PAT CAGR | | | |
| EPS CAGR | | | |
| EBITDA Margin | | | |
| ROCE | | | |
| ROE | | | |
| Debt/Equity | | | |
| CFO/PAT | | | |
| FCF | | | |
| Receivable Days | | | |

---

## 🟢 Green Flags

List the strongest 3-5.

---

## 🔴 Red Flags

List the strongest 3-5.

---

## 🟡 Watch Items

List the strongest 2-5.

---

## Last 3-4 Concall Findings

Summarize the most important developments chronologically.

---

## Management Guidance

Explain:

- What management guided
- Whether it was achieved
- Whether guidance increased/decreased
- Whether management changed its language

---

## Management Credibility

Explain whether management has historically delivered on its promises.

---

## Management vs Financial Data

Explicitly state:

### Confirmed

Which management statements are supported by financial data.

### Not Confirmed

Which statements are not yet supported.

### Contradictions

Any important mismatch.

---

## What Is Improving?

Explain the most important changes versus 3-4 quarters ago.

---

## Why Is It Improving?

Identify the probable drivers:

- Demand
- Pricing
- Market share
- New capacity
- New products
- Operating leverage
- Cost reduction
- New customers
- Export
- Industry cycle

---

## Future Earnings Drivers

Identify the 3-5 most important potential earnings drivers.

---

## Key Risks

Identify the 3-5 biggest risks.

---

## Final Verdict

Answer:

> "Is something fundamentally good happening in this company, and is the change significant enough to potentially support substantial future earnings growth?"

Give a concise conclusion.

---

# 31. COMPARATIVE RANKING

After analyzing all companies, create:

| Rank | Company | Score | Inflection | Concall | Valuation | Verdict |
|---:|---|---:|---|---:|---|---|

Sort by total score.

---

# 32. TOP 5

Explain why each company made the Top 5.

For each:

- Financial reason
- Concall reason
- Growth driver
- Biggest risk
- Valuation concern

---

# 33. TOP 3 DEEP-DIVE CANDIDATES

Select the three companies with the strongest combination of:

1. Financial inflection
2. Earnings growth
3. ROCE improvement
4. Cash-flow quality
5. Management credibility
6. Future growth runway
7. Reasonable valuation

---

# 34. MULTIBAGGER THESIS

For each Top 3 company construct:

Business Opportunity
        ↓
Revenue Growth
        ↓
Operating Leverage
        ↓
Margin Expansion
        ↓
ROCE Improvement
        ↓
Cash Flow
        ↓
Reinvestment
        ↓
Earnings Compounding
        ↓
Potential Valuation Rerating

Explain which stages are already happening and which are only expected.

---

# 35. CATALYSTS

Identify upcoming potential catalysts:

- Capacity commissioning
- New product launch
- Large order execution
- Margin expansion
- New customer
- New geography
- Industry cycle
- Debt reduction
- Acquisition
- Regulatory change
- Market share gain

---

# 36. INVALIDATION CONDITIONS

For every Top 3 company define:

> "What would make this thesis wrong?"

Examples:

- Revenue growth falls below X
- EBITDA margin falls below X
- ROCE deteriorates
- CFO/PAT falls below X
- Debt rises materially
- Order book declines
- Capacity utilization remains low
- Management guidance is cut
- Promoter pledge increases

This section is mandatory.

---

# 37. RED FLAG PRIORITY

Not all red flags are equal.

Classify:

### Critical 🔴🔴🔴

Potential thesis breaker.

### High 🔴🔴

Requires immediate investigation.

### Moderate 🔴

Needs monitoring.

---

# 38. GREEN FLAG PRIORITY

Similarly classify:

### Strong 🟢🟢🟢

Potential major earnings driver.

### High 🟢🟢

Important positive development.

### Moderate 🟢

Positive but not thesis-changing.

---

# 39. RESEARCH DISCIPLINE

Never:

- Predict guaranteed multibagger returns
- Treat management guidance as fact
- Ignore valuation
- Ignore cash flow
- Use one quarter as the entire thesis
- Ignore contradictory evidence
- Assume order book equals revenue
- Assume capex automatically creates value
- Assume high ROCE automatically means future high returns

Always distinguish:

### FACT

What the financial statements/company filings show.

### MANAGEMENT CLAIM

What management said.

### INTERPRETATION

Your analysis of what those facts may mean.

---

# 40. SOURCE QUALITY

Prefer sources in this order:

1. Company annual reports
2. Company quarterly results
3. Company investor presentations
4. Official earnings call transcripts/recordings
5. NSE/BSE filings
6. Reliable financial databases
7. Reputable financial media

For important conclusions, use multiple sources where possible.

---

# 41. FINAL SUMMARY

At the end of the complete analysis produce:

## 🏆 Top 5 Multibagger Candidates

| Rank | Stock | Score | Financial Inflection | Concall | Key Reason |
|---:|---|---:|---|---|---|

## 🚀 Strongest Financial Inflections

Identify companies where:

Revenue ↑
+
Margins ↑
+
PAT ↑
+
ROCE ↑
+
CFO ↑
+
Debt ↓

---

## 🟢 Strongest Green Flags

List the most important positive signals across the universe.

---

## 🔴 Biggest Red Flags

List the most important risks across the universe.

---

## 🎯 Top 3 For Deep Research

For each explain:

1. What is changing?
2. Why is it changing?
3. Is management confirming it?
4. Is financial data confirming it?
5. What can accelerate it?
6. What can break it?
7. Is valuation reasonable?

---

# 43. CASE STUDY PATTERN — "LEGACY CORE + ADJACENT OPTIONALITY RE-RATING"

Derived from backtesting a real multibagger: **Shriram Pistons & Rings (SHRIPISTON) → renamed SPR Auto Technologies**.

Purchased 2024-08-16 at ₹1,970. ~24 months later (2026-08-24) trading at ~₹4,730 — a ~140% absolute return (~57-58% CAGR).

## 43.1 What Actually Happened

This was a **legacy, single-product auto-ancillary company (pistons/rings/engine valves for ICE vehicles)** that:

1. Made a series of **bolt-on acquisitions into adjacent high-growth verticals** starting ~2 years BEFORE the big price move became visible:
   - 51% stake in an EV motor/controller company (2022)
   - 100% acquisition of a precision-engineering/injection-moulding company (2024)
2. Kept the CORE business steady (mid-teens revenue growth, ~20% ROCE, stable ~14% margin) — nothing screamed "inflection" in the base business alone.
3. Grew >35% of revenue from these new, non-legacy segments by FY26.
4. Only THEN — after two years of building the story — formally **renamed the company** to reflect a "diversified auto-tech platform" identity, decoupling it from the old single-product peer set.
5. Raised a large QIP at a premium price, with institutional (FII/DII) investors absorbing promoter dilution — an external validation event.
6. The market **re-rated the P/E multiple from ~18-20x to ~36x** while EPS grew only ~28% cumulatively over the period. **Most of the return was multiple expansion driven by a narrative/peer-set change, not earnings growth.**
7. Margins actually COMPRESSED as the new segments scaled (dilutive to blended margin) — yet the stock kept re-rating, because the market was pricing growth durability and optionality, not near-term margin purity.

## 43.2 Key Insight: This Pattern Is NOT Captured By Standard Screens

A pure financial screen (revenue CAGR, PAT growth, ROCE trend, margin expansion) would have UNDERWEIGHTED or MISSED this stock at entry:
- Margins were not expanding — they later compressed.
- ROCE was good but flat, not accelerating.
- P/E at ~18-20x looked "fair," not cheap.

The alpha was in **structural optionality that hadn't yet been priced or recognized by the peer-comparison set** — not in the trailing financial statements.

## 43.3 New Screening Heuristic: "Optionality Re-rating Candidate"

When scoring a company, in addition to the standard 100-point framework, explicitly check for this SEPARATE pattern and flag it if present:

| Signal | Present? |
|---|---|
| Company has a stable, cash-generative "legacy" core business (steady ROCE, moderate growth) | |
| Company/subsidiary has made 1+ bolt-on acquisitions or JVs into an ADJACENT, structurally faster-growing vertical (EV, precision engineering, specialty chemicals, defense, data/software, etc.) in the last 1-3 years | |
| The new vertical is still small (<20-35% of revenue) — i.e., not yet priced in, but growing its revenue share | |
| Management commentary is starting to reframe the company's identity/peer set in concalls/investor decks (e.g., "platform," "diversified," "beyond legacy") | |
| No rebrand/name change has happened YET — this is the early-signal window; a completed rebrand is a LAGGING confirmation, not a leading signal | |
| Current valuation multiple still reflects the OLD, narrower peer set (i.e., priced like a single-product company, not like the diversified platform it's becoming) | |
| Export franchise / global capacity vacancy tailwind (China+1) supports the legacy core while the new vertical scales — reduces downside risk during the transition | |

If 5+ of these are true: classify as **🚀 OPTIONALITY RE-RATING CANDIDATE** — flag as high-priority even if the standard 100-point score is only "Watchlist" (65-74) tier, because the framework's financial/concall scoring is backward-looking and structurally underweights unpriced optionality.

## 43.4 Practical Screening Steps

1. For every company being screened, explicitly search: "[Company] acquisition subsidiary [year]", "[Company] JV EV/new vertical", "[Company] diversification strategy concall".
2. Check subsidiary/SPV filings (not just standalone/consolidated P&L) — early optionality often sits in a newly formed subsidiary with immaterial revenue contribution at first.
3. Track QIPs/preferential allotments/capital raises as VALIDATION events, not entry signals — by the time a large QIP prices at a premium with strong institutional uptake, much of the re-rating has already happened. The entry signal is the acquisition itself, 1-2 years earlier.
4. Do not penalize flat/compressing margins during a legitimate diversification phase — check whether the margin dilution is coming from scaling a strategically sound new vertical (acceptable) vs. core business deterioration (red flag).
5. Explicitly separate "earnings-driven return" from "multiple re-rating return" in any backtest: compare entry P/E and EPS to exit P/E and EPS. If most of the return is multiple expansion, the thesis is a narrative/peer-set change — track whether that narrative is durable or fragile.

---

# 44. FINAL PRINCIPLE

The ideal multibagger candidate is NOT necessarily:

"the company with the best current numbers."

The ideal candidate is:

> **A good business whose economics are improving rapidly, management is executing, cash flow is following profits, capital is being deployed at attractive returns, the growth runway is large, and the valuation has not fully priced in the improvement.**

The strongest conviction occurs when:

Management says it
        +
Orders/capacity support it
        +
Financial statements show it
        +
Cash flow confirms it
        +
ROCE improves
        +
Valuation remains reasonable

When all six align:

> **HIGH-CONVICTION RESEARCH CANDIDATE**

When management commentary conflicts with financial evidence:

> **RED FLAG**

When financials are improving but management commentary is still cautious:

> **WATCH CLOSELY**

When management is highly optimistic but financial evidence is deteriorating:

> **LOW CONVICTION / POTENTIAL TRAP**

Always communicate uncertainty and never present the output as a guaranteed investment outcome.