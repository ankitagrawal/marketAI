"""
Covered Call / Collar Planner - Streamlit panel (live NSE option chain).

Run with:
    streamlit run coveredCallPanel.py
"""
import os, sys
import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "coveredcall"))
from ccLive import fetch, parse, call_delta  # noqa: E402

st.set_page_config(page_title="Covered Call Planner", layout="wide")
st.title("💰 Covered Call / Collar Planner")
st.caption("Sell an OTM call against shares you own for monthly income; optionally buy an OTM put as a floor. "
           "Live NSE chain · sell at bid, buy at ask · educational, not advice.")


@st.cache_data(ttl=60, show_spinner="Fetching NSE option chain…")
def get_chain(symbol, expiry=None):
    return fetch(symbol, expiry)


# ── Inputs ───────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns([2, 2, 1])
symbol = c1.text_input("Symbol (F&O stock)", "HCLTECH").strip().upper()
try:
    rec0, _ = get_chain(symbol)
    expiries = rec0["expiryDates"]
except Exception as e:
    st.error(f"Could not fetch chain for {symbol}: {e}  (NSE may be rate-limiting; retry in a minute)")
    st.stop()
expiry = c2.selectbox("Expiry", expiries)
lots = c3.number_input("Lots held", 1, 100, 1)

with st.sidebar:
    st.header("Strategy rules")
    tgt_delta = st.slider("Target call delta", 0.10, 0.40, 0.22, 0.01,
                          help="~0.20-0.25 balances income vs. upside (see backtest).")
    use_put = st.checkbox("Add protective put (collar)", False)
    put_dist = st.slider("Put distance below spot (%)", 3, 15, 8, disabled=not use_put)
    max_spread = st.slider("Max bid-ask spread (%)", 1, 25, 15)
    min_oi = st.number_input("Min open interest (contracts)", 0, 100000, 100)
    st.header("Your position & costs")
    buy_price = st.number_input("Your average buy price (₹, 0 = use spot)", 0.0, 100000.0, 0.0, 1.0)
    tax_rate = st.slider("Tax rate on option income (%)", 0, 40, 30,
                         help="F&O income is generally business income at your slab rate - confirm with a CA.")
    brokerage = st.number_input("Brokerage per option order (₹)", 0.0, 500.0, 20.0, 5.0)
    sl_pct = st.slider("Stop-loss below buy price (%)", 3, 20, 8)
    st.caption("Backtest result: 0.20Δ call + ~8% OTM put cut max drawdown ~30% → ~15% "
               "with ~3 pts lower CAGR. Plain covered calls barely reduced drawdown.")

rec, _ = get_chain(symbol, expiry)
S, dte, rows, lot_inf = parse(rec, expiry)
lot = c3.number_input("Lot size", 1, 100000, int(lot_inf or 1), help="Inferred from order book — verify on NSE.")
T = max(dte, 1) / 365
qty = lot * lots

# ── Build candidates ─────────────────────────────────────────────────────────
calls, puts = [], []
for r in rows:
    c, p = r.get("CE"), r.get("PE")
    if c and c.get("strikePrice") and c["buyPrice1"] and c["sellPrice1"] and c["strikePrice"] > S:
        mid = (c["buyPrice1"] + c["sellPrice1"]) / 2
        calls.append(dict(Strike=c["strikePrice"], **{"OTM %": (c["strikePrice"] / S - 1) * 100},
                          Delta=call_delta(S, c["strikePrice"], T, c["impliedVolatility"] / 100),
                          IV=c["impliedVolatility"], Bid=c["buyPrice1"], Ask=c["sellPrice1"],
                          **{"Spread %": (c["sellPrice1"] - c["buyPrice1"]) / mid * 100},
                          OI=c["openInterest"], Volume=c["totalTradedVolume"],
                          **{"Prem % spot": c["buyPrice1"] / S * 100,
                             "Annualised %": c["buyPrice1"] / S * 100 * 365 / max(dte, 1)}))
    if p and p.get("strikePrice") and p["buyPrice1"] and p["sellPrice1"] and p["strikePrice"] < S:
        mid = (p["buyPrice1"] + p["sellPrice1"]) / 2
        puts.append(dict(Strike=p["strikePrice"], **{"Below spot %": (p["strikePrice"] / S - 1) * 100},
                         Bid=p["buyPrice1"], Ask=p["sellPrice1"],
                         **{"Spread %": (p["sellPrice1"] - p["buyPrice1"]) / mid * 100},
                         OI=p["openInterest"], IV=p["impliedVolatility"]))
cdf, pdf_ = pd.DataFrame(calls), pd.DataFrame(puts)
if cdf.empty:
    st.warning("No two-sided OTM call quotes for this expiry."); st.stop()

cand = cdf[(cdf.Delta.between(0.08, 0.45))]
liq = cand[(cand["Spread %"] <= max_spread) & (cand.OI >= min_oi)]
pool = liq if not liq.empty else cand
if liq.empty:
    st.warning("No strikes pass the liquidity filters; showing all candidates.")

options = pool.Strike.tolist()
default = int(pool.iloc[(pool.Delta - tgt_delta).abs().argmin()].Strike)
Kc = st.selectbox("Call strike to sell", options, index=options.index(default),
                  help="Defaults to the strike closest to the target delta.")
call = cdf[cdf.Strike == Kc].iloc[0]

put = None
if use_put and not pdf_.empty:
    pp = pdf_[(pdf_["Spread %"] <= 25)] if (pdf_["Spread %"] <= 25).any() else pdf_
    put = pp.iloc[(pp.Strike - S * (1 - put_dist / 100)).abs().argmin()]
    pk = st.selectbox("Put strike to buy", pdf_.Strike.tolist(),
                      index=pdf_.Strike.tolist().index(put.Strike))
    put = pdf_[pdf_.Strike == pk].iloc[0]

# ── Metrics ──────────────────────────────────────────────────────────────────
Kp = put.Strike if put is not None else None
put_ask = put.Ask if put is not None else 0.0
credit = call.Bid - put_ask
max_profit = (Kc - S) + credit
max_loss = (S - Kp) + (-credit) if Kp else S - credit
breakeven = S - credit

st.subheader(f"{symbol} · spot ₹{S:,.2f} · {expiry} ({dte} days) · {rec['timestamp']}")
m = st.columns(5)
m[0].metric("Net premium / share", f"₹{credit:.2f}", f"{credit / S * 100:.2f}% · {credit / S * 100 * 365 / max(dte,1):.1f}% ann.")
m[1].metric("Income (all lots)", f"₹{credit * qty:,.0f}")
m[2].metric("Max profit", f"₹{max_profit * qty:,.0f}", f"{max_profit / S * 100:.2f}%")
m[3].metric("Break-even", f"₹{breakeven:,.1f}", f"{(breakeven / S - 1) * 100:.2f}%")
m[4].metric("Max loss" + (" (floored)" if Kp else " (stock → 0)"), f"₹{max_loss * qty:,.0f}",
            f"{max_loss / S * 100:.1f}%", delta_color="inverse")
if put is not None:
    st.info(f"Sell **{Kc:.0f} CE @ {call.Bid:.2f}** (Δ {call.Delta:.2f}) + buy **{Kp:.0f} PE @ {put_ask:.2f}** "
            f"→ the put costs {put_ask / call.Bid * 100:.0f}% of the call premium.")
else:
    st.info(f"Sell **{Kc:.0f} CE @ {call.Bid:.2f}** (Δ {call.Delta:.2f}). No downside protection beyond the premium.")


# ── Real take-home (after charges & tax) ─────────────────────────────────────
st.markdown("### 🧾 Real take-home & safety checks")
cost_basis = buy_price if buy_price > 0 else S
prem_val = call.Bid * qty
put_val = put_ask * qty if Kp else 0.0
orders = 1 + (1 if Kp else 0)
stt_sell = 0.0015 * prem_val                           # STT on option premium (sell side)
txn = 0.000355 * (prem_val + put_val)                  # approx NSE option transaction charge
gst = 0.18 * (brokerage * orders + txn)
charges = brokerage * orders + stt_sell + txn + gst
pre_tax = credit * qty - charges
tax = max(pre_tax, 0) * tax_rate / 100
take_home = pre_tax - tax
deployed = S * qty
fd_alt = deployed * 0.07 * dte / 365
t = st.columns(5)
t[0].metric("Gross premium", f"₹{credit * qty:,.0f}")
t[1].metric("Charges (est.)", f"-₹{charges:,.0f}")
t[2].metric(f"Tax @ {tax_rate}%", f"-₹{tax:,.0f}")
t[3].metric("Take-home", f"₹{take_home:,.0f}", f"{take_home / deployed * 100:.2f}% of capital")
t[4].metric(f"FD @7% for {dte}d", f"₹{fd_alt:,.0f}",
            "beats FD" if take_home > fd_alt else "below FD", delta_color="normal" if take_home > fd_alt else "inverse")
st.caption("Charges: flat brokerage + STT 0.15% on sold premium + ~0.0355% exchange fee + 18% GST on those. "
           "If assigned, extra STT 0.15% on intrinsic value applies. Estimates only - check your contract note.")

# safety checks
msgs = []
if Kc < cost_basis:
    msgs.append(("error", f"Strike {Kc:.0f} is BELOW your buy price {cost_basis:.0f} - if assigned you lock in a loss of "
                          f"₹{(cost_basis - Kc) * qty:,.0f} on the shares. Pick a higher strike."))
else:
    msgs.append(("success", f"Strike {Kc:.0f} is above your buy price {cost_basis:.0f}: if assigned you still gain "
                            f"₹{(Kc - cost_basis) * qty:,.0f} on shares plus premium."))
try:
    import yfinance as yf
    h = yf.download(symbol + ".NS", period="1y", auto_adjust=True, progress=False)
    if isinstance(h.columns, pd.MultiIndex):
        h.columns = [c[0] for c in h.columns]
    ma50, ma200 = h.Close.rolling(50).mean().iloc[-1], h.Close.rolling(200).mean().iloc[-1]
    sl_cost = cost_basis * (1 - sl_pct / 100)
    sl = st.columns(3)
    sl[0].metric("50-day average", f"₹{ma50:,.1f}", f"{(S / ma50 - 1) * 100:+.1f}% vs spot")
    sl[1].metric("200-day average", f"₹{ma200:,.1f}", f"{(S / ma200 - 1) * 100:+.1f}% vs spot")
    sl[2].metric(f"Stop-loss ({sl_pct}% below buy)", f"₹{sl_cost:,.1f}",
                 f"loss if hit ₹{(cost_basis - sl_cost) * qty:,.0f}", delta_color="off")
    if S < ma50:
        msgs.append(("warning", f"Spot is below the 50-day average (₹{ma50:,.0f}): trend is weak. Rule: close below it "
                                f"= exit shares and buy back the call."))
    if S < sl_cost:
        msgs.append(("error", f"Spot is already below your stop-loss ₹{sl_cost:,.0f}."))
except Exception as e:
    st.caption(f"(Moving averages unavailable: {e})")
msgs.append(("info", "Check the results date before selling: skip the cycle if results fall before expiry."))
for kind, text in msgs:
    getattr(st, kind)(text)

# ── Payoff chart & table ─────────────────────────────────────────────────────
grid = np.linspace(S * 0.8, S * 1.15, 71)
stock = grid - S
cc = stock + call.Bid - np.maximum(grid - Kc, 0)
col = cc + ((np.maximum(Kp - grid, 0) - put_ask) if Kp else 0)
chart = pd.DataFrame({"Spot at expiry": grid, "Stock only": stock * qty,
                      "Covered call": cc * qty, "Collar": col * qty}).set_index("Spot at expiry")
if Kp is None:
    chart = chart.drop(columns="Collar")
st.markdown("**P&L at expiry (₹, all lots)**")
st.line_chart(chart)

sc = []
for pct in (-20, -15, -10, -8, -5, 0, 3, 5, 8, 12):
    s1 = S * (1 + pct / 100)
    a = (s1 - S) + call.Bid - max(s1 - Kc, 0)
    b = a + ((max(Kp - s1, 0) - put_ask) if Kp else 0)
    sc.append({"Move %": pct, "Spot": round(s1, 1), "Stock ₹": round((s1 - S) * qty),
               "Covered call ₹": round(a * qty), **({"Collar ₹": round(b * qty)} if Kp else {})})
st.dataframe(pd.DataFrame(sc), hide_index=True, width='stretch')

# ── Chain tables ─────────────────────────────────────────────────────────────
with st.expander("Call candidates"):
    st.dataframe(cand.round(2), hide_index=True, width='stretch')
with st.expander("Put candidates"):
    st.dataframe(pdf_.round(2), hide_index=True, width='stretch')

st.caption("Excludes brokerage, STT (0.15% of intrinsic if assigned), margin, interest and tax. "
           "Check results dates before selling calls. Lot size must be verified on NSE.")
