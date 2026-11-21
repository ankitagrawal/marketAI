"""
Adaptive SIP Backtest — Streamlit Panel
Automates the Sequence.xlsx experiment: monthly SIP that grows on losses / shrinks on gains,
exit everything at +target%, restart next day. Test on any stock or sector index.

Run with:
    streamlit run sipBacktestPanel.py
"""

import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import requests
import streamlit as st

from sipBacktest import (Params, backtest, fetch_prices, rolling_scan, scan_summary,
                         to_yf_symbol)

NIFTY500_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
SEQUENCE_XLSX = Path.home() / "Downloads" / "Sequence.xlsx"

SECTORS = {
    "Nifty 50": "^NSEI", "Nifty Bank": "^NSEBANK", "Nifty IT": "^CNXIT",
    "Nifty Auto": "^CNXAUTO", "Nifty Pharma": "^CNXPHARMA", "Nifty FMCG": "^CNXFMCG",
    "Nifty Metal": "^CNXMETAL", "Nifty Energy": "^CNXENERGY", "Nifty Realty": "^CNXREALTY",
    "Nifty Infra": "^CNXINFRA", "Nifty PSU Bank": "^CNXPSUBANK",
    "Nifty Financial Services": "NIFTY_FIN_SERVICE.NS",
    "Nifty Next 50": "^NSMIDCP", "Nifty Consumption": "^CNXCONSUM",
    "Nifty PSE": "^CNXPSE",
}

st.set_page_config(page_title="Adaptive SIP Backtest", layout="wide")
st.title("🔁 Adaptive SIP Backtest")
st.caption("Monthly SIP = base × (1 − multiplier × gain%). Loss ⇒ invest more, gain ⇒ invest less. "
           "Sell everything at the target gain, restart from the next trading day.")


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Strategy")
    base = st.number_input("Base SIP (₹)", 10_000, 10_000_000, 100_000, 10_000)
    mult = st.number_input("Multiplier on gain/loss %", 0.0, 20.0, 4.0, 0.5,
                           help="4 ⇒ a 4% loss adds 16% to the SIP (1L → 1.16L). 0 = plain fixed SIP.")
    target = st.number_input("Target gain % (exit)", 1.0, 50.0, 6.28, 0.01,
                             help="Your sheet uses 6.28 (countSequential628). Set 6 for a flat 6%.")
    win = st.slider("History window (years ago)", -15, 0, (-5, 0), format="%d yr",
                    help="Drag both ends. (-3, -2) = start the strategy 3 years ago and stop 2 years ago. "
                         "Right end 0 = up to today.")
    years, end_ago = -win[0], -win[1]      # years = how far back we start, end_ago = where we stop
    span = years - end_ago
    if span < 1:
        st.error("Window must be at least 1 year wide.")
        st.stop()
    st.caption(f"Testing {pd.Timestamp.today().normalize() - pd.DateOffset(years=years):%d %b %Y} → "
               f"{pd.Timestamp.today().normalize() - pd.DateOffset(years=end_ago):%d %b %Y}")
    with st.expander("Safety limits (optional)"):
        cap = st.number_input("Max SIP as × base (0 = no cap)", 0.0, 20.0, 0.0, 0.5,
                              help="Stops the SIP exploding in a deep crash.")
        floor = st.number_input("Min SIP (₹)", 0, 1_000_000, 0, 10_000)
    params = Params(base=float(base), mult=float(mult), target=float(target),
                    min_sip=float(floor), max_sip_x=float(cap))


# ── Helpers ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=6 * 3600, show_spinner=False)
def get_prices(symbol: str, years: int) -> pd.Series:
    return fetch_prices(symbol, years)


@st.cache_data(ttl=24 * 3600, show_spinner="Downloading Nifty 500 list…")
def load_nifty500() -> list[str]:
    r = requests.get(NIFTY500_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))["Symbol"].tolist()


def load_stocklist() -> list[str]:
    """Stocklist sheet from Sequence.xlsx, if present."""
    try:
        df = pd.read_excel(SEQUENCE_XLSX, sheet_name="Stocklist", header=None)
        return [str(x).strip().upper() for x in df[0].dropna()]
    except Exception:
        return []


def window_prices(symbol: str) -> pd.Series:
    prices = get_prices(symbol, years)
    if end_ago > 0:
        prices = prices[prices.index <= pd.Timestamp.today().normalize() - pd.DateOffset(years=end_ago)]
    return prices


def run_one(label: str, symbol: str):
    prices = window_prices(symbol)
    if len(prices) < 60:
        return dict(label=label, symbol=symbol, error="No / too little data")
    bt = backtest(prices, params)
    fixed = backtest(prices, Params(base=params.base, mult=0.0, target=params.target))
    scan = rolling_scan(prices, params)
    return dict(label=label, symbol=symbol, prices=prices, bt=bt, fixed=fixed,
                scan=scan, scan_sum=scan_summary(scan))


def run_many(items: dict[str, str]) -> list[dict]:
    out, total = [], len(items)
    bar = st.progress(0.0, text=f"0 / {total}")
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(run_one, lb, sym): lb for lb, sym in items.items()}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                out.append(f.result())
            except Exception as e:
                out.append(dict(label=futs[f], symbol="", error=str(e)))
            bar.progress(i / total, text=f"{i} / {total}  ({futs[f]})")
    bar.empty()
    return out


def inr(x):
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"₹{x:,.0f}"


def leaderboard(results: list[dict]) -> pd.DataFrame:
    rows = []
    for r in results:
        if "error" in r:
            rows.append(dict(Name=r["label"], Note=r["error"]))
            continue
        s, sc, fx = r["bt"]["summary"], r["scan_sum"], r["fixed"]["summary"]
        rows.append({
            "Name": r["label"], "Symbol": r["symbol"],
            "Cycles": s["cycles"], "Target hit": s["closed"], "Open": s["open"],
            "Win % (sequential)": round(s["win_rate"], 1),
            "Win % (any start month)": round(sc["hit_rate"], 1),
            "Median days to target": s["median_days"], "Longest cycle (days)": s["max_days"],
            "Total P&L ₹": round(s["total_profit"]), "Open P&L ₹": round(s["open_pnl"]),
            "XIRR %": round(s["xirr_pct"], 1) if not np.isnan(s["xirr_pct"]) else np.nan,
            "Fixed-SIP XIRR %": round(fx["xirr_pct"], 1) if not np.isnan(fx["xirr_pct"]) else np.nan,
            "Max capital in one cycle ₹": round(s["max_peak_capital"]),
            "Worst drawdown %": round(s["worst_drawdown_pct"], 1),
        })
    df = pd.DataFrame(rows)
    return df.sort_values("XIRR %", ascending=False, na_position="last") if "XIRR %" in df else df


def detail_view(r: dict):
    s, sc, fx = r["bt"]["summary"], r["scan_sum"], r["fixed"]["summary"]
    st.subheader(f"{r['label']}  ·  {r['symbol']}")

    st.markdown("**Sequential run** — start once, restart the day after every exit")
    c = st.columns(5)
    c[0].metric("Win rate", f"{s['win_rate']:.1f}%", f"{s['closed']} of {s['cycles']} cycles hit target")
    c[1].metric("Total P&L", inr(s["total_profit"]), f"realised {inr(s['realised_profit'])}")
    c[2].metric("XIRR", f"{s['xirr_pct']:.1f}%" if not np.isnan(s["xirr_pct"]) else "–",
                f"fixed SIP: {fx['xirr_pct']:.1f}%" if not np.isnan(fx["xirr_pct"]) else None,
                delta_color="off")
    c[3].metric("Median days to target",
                f"{s['median_days']:.0f}" if not np.isnan(s["median_days"]) else "–",
                f"longest {s['max_days']:.0f}d" if not np.isnan(s["max_days"]) else None,
                delta_color="off")
    c[4].metric("Biggest capital in one cycle", inr(s["max_peak_capital"]),
                f"worst dip {s['worst_drawdown_pct']:.1f}%", delta_color="off")
    if s["open"]:
        st.warning(f"Last cycle is still **open** (never hit {params.target}%): "
                   f"unrealised P&L {inr(s['open_pnl'])}. It is not counted as a win.")

    st.markdown("**Any-start test** — begin a fresh cycle at the start of *every* month and see "
                "if it reaches the target before data ends")
    c = st.columns(4)
    c[0].metric("Starts that hit target", f"{sc['hit_rate']:.1f}%", f"of {sc['starts']} start months")
    c[1].metric("Median days", f"{sc['median_days']:.0f}" if not np.isnan(sc["median_days"]) else "–")
    c[2].metric("90% finish within", f"{sc['p90_days']:.0f} days" if not np.isnan(sc["p90_days"]) else "–")
    c[3].metric("Avg capital deployed", inr(sc["avg_peak"]))

    # price chart with buys / sells
    prices = r["prices"]
    pdf = prices.rename("Close").reset_index()
    pdf.columns = ["Date", "Close"]
    buys, sells = [], []
    for cy in r["bt"]["raw"]:
        buys += [dict(Date=d, Price=float(p), Amount=a) for d, p, a in cy["buys"]]
        if cy["sell"]:
            d, p, v = cy["sell"]
            sells.append(dict(Date=d, Price=float(p), Amount=v))
    line = alt.Chart(pdf).mark_line(color="#888").encode(x="Date:T", y=alt.Y("Close:Q", scale=alt.Scale(zero=False)))
    layers = [line]
    if buys:
        layers.append(alt.Chart(pd.DataFrame(buys)).mark_circle(color="#1f77b4", size=45).encode(
            x="Date:T", y="Price:Q", tooltip=["Date:T", "Price:Q", alt.Tooltip("Amount:Q", format=",.0f", title="SIP ₹")]))
    if sells:
        layers.append(alt.Chart(pd.DataFrame(sells)).mark_point(color="#2ca02c", shape="triangle-up", size=110, filled=True).encode(
            x="Date:T", y="Price:Q", tooltip=["Date:T", "Price:Q", alt.Tooltip("Amount:Q", format=",.0f", title="Sold ₹")]))
    st.altair_chart(alt.layer(*layers).properties(height=320), width='stretch')
    st.caption("Blue dots = SIP buys · green triangles = exits at target")

    tab4, tab1, tab2, tab3 = st.tabs(["Window comparison", "Cycles", "SIP ledger", "Any-start results"])
    with tab4:
        st.caption("Same strategy, as if you had started N years ago (N years before the end of your window; needs a wide enough window).")
        rows = []
        for w in [1, 2, 3, 4, 5, 7, 10, 15]:
            if w > span:
                continue
            pw = prices[prices.index >= prices.index[-1] - pd.DateOffset(years=w)]
            if len(pw) < 40:
                continue
            b = backtest(pw, params)["summary"]
            ss = scan_summary(rolling_scan(pw, params))
            rows.append({"Started": f"{w} yr ago", "Cycles": b["cycles"], "Target hit": b["closed"],
                         "Open": b["open"], "Win %": round(b["win_rate"], 1),
                         "Any-start hit %": round(ss["hit_rate"], 1),
                         "Median days": b["median_days"], "Longest cycle (d)": b["max_days"],
                         "Total P&L ₹": round(b["total_profit"]), "XIRR %": round(b["xirr_pct"], 1),
                         "Max capital ₹": round(b["max_peak_capital"]),
                         "Worst dip %": round(b["worst_drawdown_pct"], 1)})
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    with tab1:
        cy = r["bt"]["cycles"].copy()
        if not cy.empty:
            cy["start"], cy["end"] = cy["start"].dt.date, cy["end"].dt.date
            cy = cy.rename(columns={"days": "days", "invested": "invested ₹", "proceeds": "value ₹",
                                    "profit": "profit ₹", "ret_pct": "return %", "sips": "# buys",
                                    "peak_invested": "peak capital ₹", "worst_gain_pct": "worst dip %",
                                    "worst_pnl": "worst P&L ₹"})
            st.dataframe(cy.round(2), width='stretch', hide_index=True)
    with tab2:
        led = []
        for i, cy in enumerate(r["bt"]["raw"], 1):
            for j, (d, p, a) in enumerate(cy["buys"], 1):
                led.append({"cycle": i, "buy #": j, "date": d.date(), "price": round(float(p), 2), "SIP ₹": round(a)})
        st.dataframe(pd.DataFrame(led), width='stretch', hide_index=True)
    with tab3:
        sc_df = r["scan"].copy()
        if not sc_df.empty:
            sc_df["start"], sc_df["end"] = sc_df["start"].dt.date, sc_df["end"].dt.date
            st.dataframe(sc_df.round(2), width='stretch', hide_index=True)


def render(results: list[dict], key: str):
    if not results:
        return
    ok = [r for r in results if "error" not in r]
    lb = leaderboard(results)
    if len(results) > 1:
        st.subheader("Leaderboard")
        st.dataframe(lb, width='stretch', hide_index=True)
        st.download_button("Download CSV", lb.to_csv(index=False), f"sip_backtest_{key}.csv", "text/csv")
    bad = [r for r in results if "error" in r]
    if bad:
        st.warning("Skipped: " + ", ".join(f"{r['label']} ({r['error']})" for r in bad))
    if not ok:
        return
    names = [r["label"] for r in ok]
    pick = st.selectbox("Drill into", names, key=f"pick_{key}") if len(ok) > 1 else names[0]
    detail_view(next(r for r in ok if r["label"] == pick))


# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_stock, tab_sector, tab_sweep = st.tabs(["📈 Stocks", "🏭 Sectors / Indices", "🎯 Best target (π sweep)"])

with tab_stock:
    raw = st.text_input("NSE codes (comma-separated)", placeholder="e.g. HCLTECH, LT, ANGELONE, APOLLOHOSP",
                        key="stock_codes")
    c1, c2 = st.columns(2)
    use_list = c1.checkbox("Add my Stocklist from Sequence.xlsx", value=False,
                           help=f"Reads sheet 'Stocklist' from {SEQUENCE_XLSX}")
    use_500 = c2.checkbox("Whole Nifty 500 (slow)", value=False)
    if st.button("Backtest stocks", type="primary", key="go_stock"):
        codes = [c.strip().upper() for c in raw.replace("\n", ",").split(",") if c.strip()]
        if use_list:
            codes += load_stocklist()
        if use_500:
            try:
                codes += load_nifty500()
            except Exception as e:
                st.error(f"Couldn't load Nifty 500: {e}")
        codes = list(dict.fromkeys(codes))
        if not codes:
            st.info("Enter at least one code.")
        else:
            st.session_state["stock_results"] = run_many({c: to_yf_symbol(c) for c in codes})
    render(st.session_state.get("stock_results", []), "stocks")

with tab_sector:
    chosen = st.multiselect("Sector indices", list(SECTORS), default=["Nifty IT", "Nifty Bank"])
    custom = st.text_input("Extra Yahoo tickers (optional)", placeholder="e.g. ^CNXSERVICE, ^NSEMDCP50",
                           key="sector_custom")
    if st.button("Backtest sectors", type="primary", key="go_sector"):
        items = {n: SECTORS[n] for n in chosen}
        for t in [x.strip() for x in custom.split(",") if x.strip()]:
            items[t] = t
        if not items:
            st.info("Pick at least one sector.")
        else:
            st.session_state["sector_results"] = run_many(items)
    render(st.session_state.get("sector_results", []), "sectors")


def sweep_one(label: str, symbol: str, targets: list[float]):
    prices = window_prices(symbol)
    if len(prices) < 60:
        return dict(label=label, error="No / too little data")
    rows = []
    for t in targets:
        p = Params(base=params.base, mult=params.mult, target=t,
                   min_sip=params.min_sip, max_sip_x=params.max_sip_x)
        b = backtest(prices, p)["summary"]
        ss = scan_summary(rolling_scan(prices, p))
        rows.append({"Name": label, "Target %": round(t, 2),
                     "Cycles": b["cycles"], "Target hit": b["closed"], "Open": b["open"],
                     "Win %": round(b["win_rate"], 1), "Any-start hit %": round(ss["hit_rate"], 1),
                     "Median days": b["median_days"], "Longest (d)": b["max_days"],
                     "Total P&L ₹": round(b["total_profit"]), "XIRR %": round(b["xirr_pct"], 1) if not np.isnan(b["xirr_pct"]) else np.nan,
                     "Max capital ₹": round(b["max_peak_capital"]), "Worst dip %": round(b["worst_drawdown_pct"], 1)})
    return dict(label=label, rows=rows)


with tab_sweep:
    st.caption("Runs the same strategy at target = k × step (default step π = 3.14) and shows which target "
               "suits each stock/sector, using the window and settings in the sidebar.")
    c1, c2, c3 = st.columns([2, 1, 1])
    sw_codes = c1.text_input("NSE codes (comma-separated)", placeholder="e.g. LT, HCLTECH, APOLLOHOSP", key="sw_codes")
    step = c2.number_input("Step (π = 3.14159)", 0.5, 20.0, 3.14, 0.01)
    kmax = c3.slider("Multiples (k = 1…)", 2, 12, 8)
    sw_sectors = st.multiselect("…and/or sector indices", list(SECTORS), key="sw_sectors")
    if st.button("Find best target", type="primary", key="go_sweep"):
        items = {c.strip().upper(): to_yf_symbol(c) for c in sw_codes.split(",") if c.strip()}
        items.update({n: SECTORS[n] for n in sw_sectors})
        targets = [step * k for k in range(1, kmax + 1)]
        if not items:
            st.info("Enter at least one code or pick a sector.")
        else:
            res, bar = [], st.progress(0.0)
            with ThreadPoolExecutor(max_workers=4) as ex:
                futs = {ex.submit(sweep_one, lb, sym, targets): lb for lb, sym in items.items()}
                for i, fu in enumerate(as_completed(futs), 1):
                    try:
                        res.append(fu.result())
                    except Exception as e:
                        res.append(dict(label=futs[fu], error=str(e)))
                    bar.progress(i / len(items), text=f"{i} / {len(items)} ({futs[fu]})")
            bar.empty()
            st.session_state["sweep_results"] = res

    res = st.session_state.get("sweep_results", [])
    good = [r for r in res if "rows" in r]
    for r in res:
        if "error" in r:
            st.warning(f"{r['label']}: {r['error']}")
    if good:
        allrows = pd.DataFrame([x for r in good for x in r["rows"]])
        st.subheader("Best target per name")
        best = []
        for name, g in allrows.groupby("Name", sort=False):
            gx = g.dropna(subset=["XIRR %"])
            if gx.empty:
                continue
            b = gx.loc[gx["XIRR %"].idxmax()]
            best.append({"Name": name, "Best target % (by XIRR)": b["Target %"], "XIRR %": b["XIRR %"],
                         "Win %": b["Win %"], "Total P&L ₹": b["Total P&L ₹"], "Median days": b["Median days"],
                         "Best by P&L": g.loc[g["Total P&L ₹"].idxmax(), "Target %"],
                         "Best by Win %": g.loc[g["Win %"].idxmax(), "Target %"]})
        st.dataframe(pd.DataFrame(best), width="stretch", hide_index=True)

        metric = st.radio("Heatmap metric", ["XIRR %", "Win %", "Any-start hit %", "Total P&L ₹", "Median days"],
                          horizontal=True)
        piv = allrows.pivot(index="Name", columns="Target %", values=metric)
        st.dataframe(piv.style.background_gradient(cmap="RdYlGn", axis=1,
                     **({"gmap": -piv} if metric == "Median days" else {})).format("{:,.1f}"),
                     width="stretch")
        pick = st.selectbox("Full table for", [r["label"] for r in good], key="sw_pick")
        st.dataframe(allrows[allrows["Name"] == pick].drop(columns="Name"), width="stretch", hide_index=True)
        st.download_button("Download CSV", allrows.to_csv(index=False), "sip_target_sweep.csv", "text/csv")
        st.caption("Low targets exit fast and win often but leave gains on the table; high targets pay more per "
                   "cycle but tie capital up for longer. Pick by XIRR plus the longest cycle / max capital, "
                   "not win rate alone, and prefer a target that is good across several windows.")

with st.expander("How the backtest works / caveats"):
    st.markdown(f"""
- **Day 0:** buy ₹{base:,.0f}. **Each month after** (same calendar day, next trading day if closed):
  SIP = base × (1 − {mult:g} × gain%) where gain% is the position's P&L vs its **average cost**.
- **Exit:** the first daily close with gain ≥ **{target:g}%** sells the whole position; new cycle begins next trading day.
- **Win rate caveat:** with a fixed target, every *closed* cycle is a win by construction. The real risk
  is the cycle that never closes, so check **open cycles, longest cycle, max capital, worst dip** and the
  **any-start test**.
- Sector indices are not tradable; use the matching ETF / index fund for a real run. Prices are
  split-adjusted closes (no dividends, brokerage or taxes). Yahoo index tickers for some sectors may be
  missing — add your own in the extra-tickers box.
- XIRR treats an open cycle as sold at the last close. "Fixed-SIP XIRR" runs the same dates with multiplier 0 for comparison.
""")
