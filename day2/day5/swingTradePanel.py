"""
Swing Trade Checker — Streamlit Panel
Enter comma-separated company codes, get the 4-gate analysis for each.

Run with:
    streamlit run swingTradePanel.py
"""

import streamlit as st
import pandas as pd

from swingTradeChecker import analyze_stock, gate_passed, parse_symbols

st.set_page_config(page_title="Swing Trade Checker", layout="wide")

st.title("📈 Swing Trade Checker")
st.caption("4-Gate Framework: Trend → Strength → Timing → Trigger")

raw_input = st.text_input(
    "Company codes (comma-separated)",
    placeholder="e.g. TCS, INFY, RELIANCE, TATASTEEL",
)

run = st.button("Analyze", type="primary")

GATE_LABELS = {
    "G1": {
        "price_above_200ma": "Price above 200 MA",
        "ema20_above_200ma": "20 EMA above 200 MA",
        "ema5_above_ema20":  "5 EMA above 20 EMA",
    },
    "G2": {
        "adx_above_25":  "ADX > 25 (strong trend)",
        "di_plus_leads": "DI+ > DI- (bullish)",
    },
    "G3": {
        "rsi_entry_zone":    "RSI 45–62 (entry zone)",
        "price_near_ema20":  "Price within -1% to +3% of 20 EMA",
        "higher_low_intact": "Higher low structure intact",
    },
    "G4": {
        "green_candle":       "Green candle (close > open)",
        "close_above_ema20":  "Close above 20 EMA",
        "volume_above_avg":   "Volume > 20-day average",
        "strong_candle_body": "Candle body > 50% of range",
    },
}
GATE_NAMES = {
    "G1": "Gate 1 — Trend",
    "G2": "Gate 2 — Strength",
    "G3": "Gate 3 — Timing",
    "G4": "Gate 4 — Trigger",
}

STAGE_ORDER = [
    "STAGE 1",
    "STAGE 2",
    "STAGE 2/3",
    "STAGE 4",
    "STAGE 3",
    "STAGE 3→4",
]


def stage_key(result):
    """Short stage label (e.g. 'STAGE 3') used for filtering/display."""
    return result["stage"].split("—")[0].strip()


def render_result(result):
    symbol = result["symbol"]

    if "error" in result:
        st.error(f"**{symbol}** — {result['error']}")
        return

    l = result["latest"]
    v = result["value"]
    tr = result["trade"]

    header = f"{symbol} — ₹{l['price']}  |  Gates: {result['gates_score']}"
    if result["buy_signal"]:
        header = "🚨 " + header + "  — BUY SIGNAL"

    with st.expander(header, expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Price", f"₹{l['price']}")
            st.metric("RSI", l["rsi"])
            st.metric("ADX", l["adx"])
        with col2:
            st.metric("EMA5 / EMA20", f"{l['ema5']} / {l['ema20']}")
            st.metric("MA200", l["ma200"])
            st.metric("% from 20 EMA", f"{l['pct_from_e20']}%")
        with col3:
            st.metric("Value Score", f"{v['value_score']}/4", v["value_label"])
            st.metric("P/E", v["pe"] if v["pe"] else "N/A", v["pe_verdict"])
            st.metric("52w Position", f"{v['week52_position']}%" if v["week52_position"] is not None else "N/A")

        pv = result.get("pe_valuation")
        if pv and pv["median_pe"] is not None:
            st.markdown("**5-Year Median PE Valuation**")
            pe_col1, pe_col2, pe_col3 = st.columns(3)
            with pe_col1:
                st.metric("Current P/E", pv["current_pe"])
            with pe_col2:
                st.metric("5Y Median P/E", pv["median_pe"])
            with pe_col3:
                pct = pv["pct_from_median"]
                st.metric("vs Median", f"{pct:+.1f}%" if pct is not None else "N/A", pv["verdict"])

        peg = result.get("peg")
        if peg and peg["peg"] is not None:
            st.markdown("**PEG Ratio** (P/E ÷ 3Y EPS growth rate)")
            peg_col1, peg_col2, peg_col3 = st.columns(3)
            with peg_col1:
                st.metric("PEG", peg["peg"])
            with peg_col2:
                st.metric("P/E", peg["current_pe"])
            with peg_col3:
                st.metric("3Y EPS CAGR", f"{peg['eps_cagr_pct']}%")

        st.markdown(f"**Stage:** {result['stage']}")
        st.markdown(f"**Next Trigger:** {result['trigger']}")

        gate_cols = st.columns(4)
        for gc, gk in zip(gate_cols, ["G1", "G2", "G3", "G4"]):
            checks = result["gates"][gk]
            passed = gate_passed(checks)
            with gc:
                st.markdown(f"**{GATE_NAMES[gk]}** {'✅' if passed else '❌'}")
                for ck, cv in checks.items():
                    st.write(("✅ " if cv else "❌ ") + GATE_LABELS[gk][ck])

        if tr:
            st.markdown("**Trade Plan**")
            trade_df = pd.DataFrame([{
                "Entry":    l["price"],
                "Stop":     tr["stop_loss"],
                "Risk":     tr["risk_points"],
                "Target 1": tr["target_1"],
                "Target 2": tr["target_2"],
                "R:R":      tr["rr_ratio"],
            }])
            st.dataframe(trade_df, hide_index=True, use_container_width=True)


if run:
    if not raw_input.strip():
        st.warning("Enter at least one company code.")
    else:
        symbols = parse_symbols(raw_input)
        st.write(f"Analyzing {len(symbols)} stock(s): {', '.join(symbols)}")

        results = []
        progress = st.progress(0)
        for i, sym in enumerate(symbols):
            with st.spinner(f"Fetching {sym}..."):
                results.append(analyze_stock(sym))
            progress.progress((i + 1) / len(symbols))
        progress.empty()

        st.session_state["results"] = results

if "results" in st.session_state:
    results = st.session_state["results"]

    available_stages = sorted(
        {stage_key(r) for r in results if "error" not in r},
        key=lambda s: STAGE_ORDER.index(s) if s in STAGE_ORDER else len(STAGE_ORDER),
    )
    selected_stages = st.multiselect(
        "Filter by stage",
        options=available_stages,
        default=available_stages,
    )

    filtered = [
        r for r in results
        if "error" in r or stage_key(r) in selected_stages
    ]

    summary_rows = []
    for r in filtered:
        if "error" in r:
            summary_rows.append({"Symbol": r["symbol"], "Status": f"ERROR: {r['error']}"})
        else:
            tr  = r["trade"]
            pv  = r.get("pe_valuation") or {}
            peg = r.get("peg") or {}
            summary_rows.append({
                "Symbol":   r["symbol"],
                "Price":    r["latest"]["price"],
                "Gates":    r["gates_score"],
                "RSI":      r["latest"]["rsi"],
                "Value":    f"{r['value']['value_score']}/4",
                "5Y PE":    pv.get("verdict", "N/A"),
                "PEG":      peg.get("peg", "N/A"),
                "Stage":    stage_key(r),
                "R:R":      tr["rr_ratio"] if tr else "N/A",
                "Buy":      "🚨" if r["buy_signal"] else "",
            })

    st.subheader("Summary")
    st.dataframe(pd.DataFrame(summary_rows), hide_index=True, use_container_width=True)

    st.subheader("Details")
    for r in filtered:
        render_result(r)
