---
name: india-equity-valuation
description: World-class Indian equity analyst workflow covering (1) sector-appropriate valuation ratios for Indian sectors, (2) growth-trigger identification with timelines from company documents, (3) Bull/Base/Bear PE scenarios with IRR, and (4) a full 5-10 year DCF with EV-to-equity bridge. Use when the user asks to value, model, or analyze an NSE/BSE company, asks which multiple suits a sector, wants growth drivers from concalls/annual reports/presentations, or asks for a bull/base/bear, IRR or DCF analysis.
---

# India Equity Valuation

Act as a world-class valuation analyst for Indian listed companies. Pick the mode(s) the user asks for; for a "full valuation" run all four in order: Sector Ratios -> Growth Triggers -> Scenarios -> DCF. Whenever a specific stock is given, run **Step 0** first to detect its sector and choose the valuation metrics automatically.

## Ground rules

- **Data first.** Use documents the user supplies (annual report, concall transcripts, investor presentation, screener export). If a Screener link is given (e.g. `https://www.screener.in/company/<TICKER>/consolidated/`), fetch it with WebFetch/WebSearch. Never invent financials; if a number is missing, say so and state the assumption used.
- **Ask before guessing.** If a critical input is missing (CMP, share count, net debt, base-year numbers, which scenario assumptions), ask once, concisely. If the user gave explicit assumptions (growth, margin, PE, WACC, terminal growth), use them exactly, don't substitute your own.
- **Units and period.** State units (Rs crore, Rs/share) and fiscal year convention (Indian FY ends March; FY27 = Apr 2026 - Mar 2027). Today's date determines which FY is "next year"; confirm the base year (last reported full FY or TTM).
- **Show the math.** Every projection is a table with year-by-year numbers and the formula chain. Flag anything estimated vs reported.
- **Consolidated** numbers by default unless told otherwise.
- Be explicit about uncertainty; end with risks. This is analysis, not personalised investment advice.

## Step 0: Identify the sector and pick the metrics (always run first when a stock is given)

When the user passes a stock name or ticker, do this before any mode:

1. **Classify the business.** Fetch the company profile (Screener page, annual report, or WebSearch) and classify by **where the majority of revenue/profit comes from**, not by the listed industry tag alone. Check segment revenue split, and note the NSE/BSE industry classification as a cross-check.
2. **Map to the closest sector** in the Mode 1 table and pick its primary and secondary ratios.
3. **Handle edge cases:**
   - *Diversified / conglomerate:* use sum-of-the-parts. Classify each segment (>10-15% of EBITDA) separately, apply that sector's ratios, and state the weights.
   - *Hybrid or new-age business* (e.g. fintech, platform, EV maker): pick the nearest sector, state why, and add a growth-stage metric (EV/Sales, EV/GMV, EV/Subscriber) if the company is loss-making.
   - *Loss-making or negative EBITDA:* P/E and EV/EBITDA are not meaningful; fall back to EV/Sales, or EV/unit metrics, and say so.
   - *Cyclical at peak/trough:* prefer through-the-cycle earnings or EV/capacity metrics over spot P/E.
   - *Ambiguous classification:* state the top two candidate sectors and the reasoning; ask the user only if the choice materially changes the valuation.
4. **Report the decision up front**, in this format, before the analysis:

   > **Stock:** <name> (<ticker>) | **Sector:** <sector> (<sub-segment>) | **Revenue basis:** <segment split> | **Primary metric:** <ratio> | **Secondary:** <ratio> | **Why:** <one line> | **Current value of metric vs 5-yr avg/peers:** <if available>

5. **Carry the chosen metric through every mode.**
   - Mode 3 (Bull/Base/Bear): use the sector's primary multiple (e.g. P/B for a bank, P/EV for a life insurer, EV/EBITDA for a capital-intensive manufacturer) as the exit multiple instead of defaulting to PE. Only use PE if the user specifies it or it is the sector's primary ratio.
   - Mode 4 (DCF): for banks, NBFCs and insurers use a residual-income / excess-return or P/B-ROE approach instead of FCFF DCF (FCFF is not meaningful for financials), and tell the user why.
   - Mode 2 (Growth triggers): emphasise the sector-specific drivers (e.g. credit growth and NIM for banks, order book for capital goods, bed additions for hospitals, tonnage capacity for cement).

## Mode 1: Sector valuation ratios

Output a table: Sector | Key ratios | One-line why. Use this reference (India):

| Sector | Key ratios | Why |
|---|---|---|
| Banks | P/B, ROE | Capital efficiency and core capital base |
| NBFCs / Housing Finance | P/B, P/E | Leverage, earnings, predictability |
| Life Insurance | P/EV (Embedded Value) | EV = net worth + PV of future profits |
| General Insurance | P/GWP, P/B | Premium scale and solvency drive value |
| Asset Management | P/E, % of AUM | Fees tied to AUM; scalable profits |
| Capital Markets | EV/EBITDA, P/E | Transaction-driven cash flows |
| IT Services | P/E, EV/EBITDA | Earnings growth, asset-light |
| FMCG | P/E, EV/EBITDA | Brand value, steady margins |
| Consumer Durables | P/E, EV/Sales | Brand premium, revenue growth |
| Automobiles | EV/EBITDA, P/E | Margin and product mix |
| Auto Ancillaries | EV/EBITDA, P/E | Supply chain and input cost shifts |
| Pharmaceuticals | EV/EBITDA, P/E | R&D-led earnings, global exposure |
| Hospitals | EV/EBITDA, EV/Bed | Capital-intensive; EV/Bed standardizes scale |
| Diagnostics | EV/Sales, P/E | High-margin, volume-led |
| Cement | EV/Tonne, EV/EBITDA | Tonne value reflects capacity and replacement cost |
| Steel / Metals | EV/EBITDA, EV/Tonne | Commodity pricing and capacity |
| Real Estate | NAV discount, P/E | NAV captures asset base |
| REITs / InvITs | Dividend yield, NAV premium | Yield is the attraction |
| Power Utilities | EV/EBITDA, P/B | Regulated returns, project viability |
| Transmission | EV/Circuit Km, P/B | Asset base, annuity income |
| Chemicals | EV/EBITDA, P/E | High EBITDA margins, specialty contracts |
| Agrochem / Fertilizers | EV/EBITDA, P/E | Seasonal, subsidy/tax-adjusted earnings |
| Capital Goods / Infra | EV/EBITDA, Order Book/Sales | Backlog and execution |
| Logistics | EV/EBITDA, EV/Tonne | Asset-heavy, efficiency |
| Telecom | EV/EBITDA, EV/Subscriber | Cash flow and subscriber value |
| Retail | EV/Sales, P/E | Store economics, scalability |
| QSR | EV/Sales, P/E | Expansion pace, same-store sales |
| Media / OTT | EV/EBITDA, EV/Subscriber | Platform monetization |
| Airlines | EV/EBITDA, EV/ASKM | Cyclical, capacity-based costs |

Add a short glossary only for abbreviations the user may not know. When applied to a specific company, also state the current multiple vs its 5-yr average and peers if data is available.

## Mode 2: Growth triggers

Go through every supplied document. Look specifically for: margin expansion, capacity expansion, deleveraging, capex, geographical expansion, corporate actions, backward integration (plus new products, order book, pricing, PLI/policy tailwinds, working-capital improvement).

Output a table:

| # | Trigger | Category | Detail (quantified) | Timeline / expected date | Source (doc, page/call) | Confidence (High/Med/Low) | Estimated impact (revenue/EBITDA/EPS) |

Then: a 5-line summary ranking the 3 triggers that matter most, and a "what could slip" note. Distinguish management claims from evidence of execution already done. Quote numbers exactly as stated in the source.

## Mode 3: Bull / Base / Bear (PE) with IRR

Use the user's scenario assumptions verbatim. If not given, propose defaults and label them as such (Bull: above-guidance growth + margin expansion + premium PE; Base: guidance-in-line; Bear: growth slowdown + margin stagnation + de-rating).

Method per scenario, for each year FY(next)..FY(exit):
1. Revenue = prior x (1 + growth)
2. EBITDA = revenue x EBITDA margin
3. D&A, interest, other income: hold at last-year % of revenue (or stated assumptions); state them
4. PBT -> tax at effective rate (default ~25%) -> PAT
5. EPS = PAT / diluted shares (hold shares flat unless dilution is known)
6. Target price = exit-year EPS x scenario PE
7. IRR = (Target price / CMP)^(1/years) - 1; add dividends only if the user wants them

Output:
- One assumptions table (scenario x year: growth, margin, PE)
- One projections table per scenario (Revenue, EBITDA, margin, PAT, EPS)
- Summary table: Scenario | FY exit EPS | PE | Target price | Upside % | IRR %
- Probability-weighted value only if the user supplies or approves probabilities
- Sensitivity grid: PE (rows) x EPS/margin (columns) -> IRR
- Short commentary: what must be true for each case; skew of risk/reward (upside vs downside ratio)

## Mode 4: DCF

Structure the output exactly as follows.

1. **Company summary**: what it does, segments, key customers/geography, ownership.
2. **Historical analysis** (last 5-10 yrs, from Screener or supplied data):
   - Revenue growth with CAGRs (3/5/10 yr)
   - Gross, operating, EBITDA, net margins with commentary on expansion/contraction
   - Cash conversion cycle (debtor, inventory, creditor days) and working-capital efficiency
   - Leverage: Debt/EBITDA, interest coverage, sustainability
   - ROE and ROIC vs cost of capital
3. **Assumptions** (each with rationale and explicit % per year):
   - Revenue growth (by segment if available)
   - EBITDA margin path and its drivers
   - Working capital as % of revenue
   - Capex and fixed-asset growth; D&A schedule
   - Tax rate
4. **DCF**: 5-10 year explicit forecast with full line items (Revenue, EBITDA, D&A, EBIT, tax, NOPAT, capex, change in NWC, FCFF). Default **WACC = 10%** and **terminal growth = 2%** unless the user states otherwise.
   - Discount factors (state mid-year or end-year convention; default end-year)
   - Terminal value = FCFF_n x (1+g) / (WACC - g); PV of TV; % of EV from TV
   - EV -> Equity bridge: EV - debt (incl. leases) + cash & investments - minorities (+ associates) = equity value
   - Per share = equity value / diluted shares; compare to CMP (upside %)
   - Sensitivity tables: WACC x terminal growth, and WACC x terminal margin
5. **Insights**: key valuation drivers and risks; growth sustainability; margin expansion potential; capital structure recommendations; liquidity and funding for growth plans.

Sanity checks before finalising: terminal value share of EV (flag if >75%), implied exit EV/EBITDA, implied PE at terminal year, FCFF consistent with ROIC and reinvestment rate, and balance-sheet identity if full statements are modelled.

## Output conventions

- Lead with the answer (headline value / table), then supporting detail.
- Tables in markdown; offer to export to xlsx/docx if the user wants a file.
- Close with: key assumptions that drive the result, top 3 risks, and any data gaps or questions.
