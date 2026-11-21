"""
Candlestick Technical Analysis Panel (Streamlit)

Run:  streamlit run panel.py
"""
import altair as alt
import pandas as pd
import streamlit as st

from data import load_ohlc, parse_symbols
from patterns import (BEAR, BULL, REFERENCE, Params, detect_patterns,
                      market_trend, score_signals)

st.set_page_config(page_title="Candlestick Analyzer", layout="wide")
st.title("🕯️ Candlestick Technical Analysis")
st.caption("Reversal & continuation patterns from the EIFS charting notes, with stop-loss and trade plan.")

# ------------------------------ sidebar ------------------------------
with st.sidebar:
    raw = st.text_area("Symbols (comma-separated)", "TCS, INFY, RELIANCE, SBIN", height=80)
    suffix = st.selectbox("Exchange suffix", [".NS", ".BO", ""], help="NSE=.NS, BSE=.BO, none for US/indices")
    period = st.selectbox("History", ["3mo", "6mo", "1y", "2y", "5y"], index=2)
    interval = st.selectbox("Candle size", ["1d", "1wk", "1mo"], index=0)
    show_bars = st.slider("Bars shown on chart", 30, 250, 90)
    recent = st.slider("'Recent' window for scanner (bars)", 1, 20, 5)
    with st.expander("Pattern parameters"):
        pr = Params(
            trend_lookback=st.slider("Trend lookback (bars)", 3, 15, 5),
            trend_min_move=st.slider("Min trend move %", 0.0, 10.0, 1.0, 0.5) / 100,
            shadow_ratio=st.slider("Umbrella/star shadow ÷ body", 1.5, 4.0, 2.0, 0.5),
            penetration=st.slider("Piercing / dark cloud penetration", 0.3, 0.9, 0.5, 0.05),
            rr_target=st.slider("Target reward:risk", 1.0, 4.0, 2.0, 0.5),
        )
    kinds = st.multiselect("Pattern kinds", ["reversal", "continuation"], ["reversal", "continuation"])
    bias_f = st.multiselect("Bias", [BULL, BEAR], [BULL, BEAR])
    run = st.button("Analyze", type="primary")


@st.cache_data(ttl=900, show_spinner=False)
def _load_cached(sym, period, interval):
    df = load_ohlc(sym, period, interval)
    if df is None:
        raise ValueError("no data")   # exceptions are not cached, so failures retry
    return df


def _load(sym, period, interval):
    try:
        return _load_cached(sym, period, interval)
    except Exception:
        return None


def candle_chart(df, hits, n):
    d = df.tail(n).reset_index()
    d.columns = ["Date"] + list(d.columns[1:])
    d["dir"] = (d.Close >= d.Open).map({True: "Up", False: "Down"})
    color = alt.Color("dir:N", scale=alt.Scale(domain=["Up", "Down"], range=["#26a69a", "#ef5350"]), legend=None)
    base = alt.Chart(d).encode(x=alt.X("Date:T", title=None))
    tip = ["Date:T", "Open", "High", "Low", "Close", "Volume"]
    wick = base.mark_rule().encode(y=alt.Y("Low:Q", scale=alt.Scale(zero=False), title="Price"), y2="High:Q", color=color)
    body = base.mark_bar(size=max(2, 600 // n)).encode(y="Open:Q", y2="Close:Q", color=color, tooltip=tip)
    layers = [wick, body]
    if not hits.empty:
        h = hits[hits.date >= d.Date.iloc[0]].copy()
        if not h.empty:
            h["y"] = [df.High.loc[x] * 1.01 if b == BEAR else df.Low.loc[x] * 0.99 for x, b in zip(h.date, h.bias)]
            h["lbl"] = h.pattern
            pts = alt.Chart(h).mark_point(filled=True, size=90, shape="triangle-down").encode(
                x="date:T", y="y:Q",
                color=alt.Color("bias:N", scale=alt.Scale(domain=[BULL, BEAR], range=["#1b8a5a", "#c62828"]), legend=alt.Legend(title="Signal")),
                tooltip=["date:T", "pattern", "bias", "status", "entry", "stop", "target"])
            bull = pts.transform_filter(alt.datum.bias == BULL).mark_point(filled=True, size=90, shape="triangle-up")
            bear = pts.transform_filter(alt.datum.bias == BEAR)
            txt = alt.Chart(h).mark_text(dy=-12, fontSize=10).encode(x="date:T", y="y:Q", text="lbl:N")
            layers += [bull, bear, txt]
    return alt.layer(*layers).properties(height=420).interactive(bind_y=False)


def volume_chart(df, n):
    d = df.tail(n).reset_index()
    d.columns = ["Date"] + list(d.columns[1:])
    d["dir"] = (d.Close >= d.Open).map({True: "Up", False: "Down"})
    return alt.Chart(d).mark_bar().encode(
        x=alt.X("Date:T", title=None), y=alt.Y("Volume:Q", title="Volume"),
        color=alt.Color("dir:N", scale=alt.Scale(domain=["Up", "Down"], range=["#26a69a", "#ef5350"]), legend=None)
    ).properties(height=90)


tab_scan, tab_ref = st.tabs(["Analysis", "Pattern guide"])

with tab_ref:
    ref = pd.DataFrame(REFERENCE, columns=["Pattern", "Bias", "Candles", "Rules", "Trade rule"])
    st.dataframe(ref, hide_index=True, width="stretch")
    st.markdown("""
**Conventions:** white candle = close > open, black = close < open. Reversal patterns need a prior trend.
Always define a stop-loss — it marks the price where you know you were wrong.
Hanging Man and Inverted Hammer require a confirming next candle.  
*Educational tool — not investment advice. Patterns are probabilistic, so combine them with trend, volume and support/resistance.*
""")

with tab_scan:
    symbols = parse_symbols(raw, suffix)
    if not (run or st.session_state.get("ran")):
        st.info("Enter symbols and click **Analyze**.")
        st.stop()
    st.session_state["ran"] = True
    if not symbols:
        st.warning("No symbols given.")
        st.stop()

    results, summary = {}, []
    bar = st.progress(0.0, text="Loading…")
    for k, sym in enumerate(symbols):
        bar.progress((k + 1) / len(symbols), text=f"Loading {sym}")
        df = _load(sym, period, interval)
        if df is None or len(df) < 20:
            summary.append(dict(Symbol=sym, Trend="–", Rating="No data", Score=0, Patterns="", CMP=None))
            continue
        hits = detect_patterns(df, pr)
        if not hits.empty:
            hits = hits[hits.kind.isin(kinds) & hits.bias.isin(bias_f)]
        sc = score_signals(hits, len(df), recent)
        results[sym] = (df, hits)
        def outcome(h):
            """What price did after the pattern: stop hit first, target hit first, or still open."""
            if h.status == "Not confirmed":
                return "No trade (failed)"   # confirmation never came, so no entry was ever valid
            start = int(h.idx) + (2 if h.needs_confirm and h.status == "Confirmed" else 1)
            for hi, lo in zip(df.High.iloc[start:], df.Low.iloc[start:]):
                if h.bias == BULL:
                    s_hit, t_hit = lo <= h.stop, hi >= h.target
                else:
                    s_hit, t_hit = hi >= h.stop, lo <= h.target
                if s_hit:          # stop checked first: conservative when both hit in one bar
                    return "Stopped out"
                if t_hit:
                    return "Target hit"
            return "Active" if h.status in ("Complete", "Confirmed") else h.status

        row = dict(Symbol=sym, Trend=market_trend(df, pr), Rating=sc["rating"], Score=sc["score"],
                   CMP=round(float(df.Close.iloc[-1]), 2), Patterns=", ".join(sc["patterns"]))
        if not hits.empty:
            lt = hits.sort_values(["date", "idx"]).iloc[-1]
            row.update({"Latest pattern": lt.pattern, "Date": lt.date.strftime("%Y-%m-%d"),
                        "Bars ago": len(df) - 1 - int(lt.idx), "Status": lt.status, "Outcome": outcome(lt),
                        "Entry": lt.entry, "Stop": lt.stop, "Risk %": lt.risk_pct, "Target": lt.target,
                        "% from Entry": round((row["CMP"] / lt.entry - 1) * 100, 2),
                        "% to Target": round((lt.target / row["CMP"] - 1) * 100, 2)})
        summary.append(row)
    bar.empty()

    st.subheader(f"Scanner — signals in last {recent} bars")
    sm = pd.DataFrame(summary)
    cols = ["Symbol", "Trend", "Rating", "Score", "CMP", "Latest pattern", "Date", "Bars ago",
            "Status", "Outcome", "Entry", "% from Entry", "Stop", "Risk %", "Target", "% to Target", "Patterns"]
    sm = sm.reindex(columns=cols)
    num2 = ["Score", "CMP", "Entry", "% from Entry", "Stop", "Risk %", "Target", "% to Target"]
    sty = (sm.style.map(lambda v: "color:#1b8a5a" if v in ("Buy", "Strong Buy", "up") else "color:#c62828" if v in ("Sell", "Strong Sell", "down") else "",
                        subset=["Rating", "Trend"])
           .format("{:.2f}", subset=num2, na_rep="").format("{:.0f}", subset=["Bars ago"], na_rep=""))
    st.dataframe(sty, hide_index=True, width="stretch")

    for sym, (df, hits) in results.items():
        with st.expander(f"{sym} — {sm.loc[sm.Symbol == sym, 'Rating'].iloc[0]}", expanded=len(results) == 1):
            st.altair_chart(candle_chart(df, hits, show_bars), width="stretch")
            st.altair_chart(volume_chart(df, show_bars), width="stretch")
            if hits.empty:
                st.caption("No patterns detected with current settings.")
                continue
            view = hits.sort_values("date", ascending=False).copy()
            view["date"] = view.date.dt.strftime("%Y-%m-%d")
            st.dataframe(view[["date", "pattern", "bias", "kind", "status", "entry", "stop", "risk_pct", "target", "note"]]
                         .rename(columns={"risk_pct": "risk %"}), hide_index=True, width="stretch",
                         column_config={c: st.column_config.NumberColumn(format="%.2f") for c in ["entry", "stop", "risk %", "target"]})
            latest = view.iloc[0]
            st.markdown(f"**Latest:** {latest.pattern} on {latest.date} ({latest.bias}, {latest.status}). "
                        f"Stop **{latest.stop}**, target **{latest.target}** at {pr.rr_target:g}R." +
                        (f" Confirmation: *{latest.confirm_rule}*." if latest.needs_confirm else ""))
