"""
Swing Trade Checker — Streamlit Panel
Enter comma-separated company codes, get the 4-gate analysis for each.

Run with:
    streamlit run swingTradePanel.py
"""

import streamlit as st
import pandas as pd

from swingTradeChecker import analyze_stocks_parallel, gate_passed, parse_symbols
from pnlHistory import load_trade_history

st.set_page_config(page_title="Swing Trade Checker", layout="wide")

st.title("📈 Swing Trade Checker")
st.caption("4-Gate Framework: Trend → Strength → Timing → Trigger")

trade_history = load_trade_history()

raw_input = st.text_input(
    "Company codes (comma-separated)",
    placeholder="e.g. TCS, INFY, RELIANCE, TATASTEEL",
)

use_my_trades = st.checkbox(
    f"Include my previously traded stocks ({len(trade_history)} found in P&L statement)",
    value=False,
    disabled=not trade_history,
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
    if result.get("in_trading_zone"):
        header = "🔁 " + header + "  — RE-ENTRY ZONE"

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

        if any(v.get(k) is not None for k in ("coppock_daily", "coppock_weekly", "coppock_monthly")):
            cop_col0, cop_col1, cop_col2 = st.columns(3)
            with cop_col0:
                if v.get("coppock_daily") is not None:
                    st.metric("Coppock Curve (daily)", v["coppock_daily"], v["coppock_daily_verdict"])
            with cop_col1:
                if v.get("coppock_weekly") is not None:
                    st.metric("Coppock Curve (weekly)", v["coppock_weekly"], v["coppock_weekly_verdict"])
            with cop_col2:
                if v.get("coppock_monthly") is not None:
                    st.metric("Coppock Curve (monthly)", v["coppock_monthly"], v["coppock_monthly_verdict"])

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

        my_trade = result.get("my_trade")
        if my_trade:
            st.markdown("**My Trade History**")
            if result.get("in_trading_zone"):
                tag = "at/below your last sell price" if result.get("below_last_sell") else "back within 3% of your last sell price"
                st.success(f"🔁 Currently {tag} — potential re-entry zone")
            mt_col1, mt_col2, mt_col3, mt_col4 = st.columns(4)
            with mt_col1:
                st.metric("Avg Buy Price", f"₹{my_trade['avg_buy_price']}", f"{my_trade['quantity']:g} shares")
            with mt_col2:
                st.metric("Avg Sell Price", f"₹{my_trade['avg_sell_price']}" if my_trade['avg_sell_price'] else "Still holding")
            with mt_col3:
                st.metric("Last Sell Date", my_trade["last_sell_date"] or "N/A")
            with mt_col4:
                st.metric("Realized P&L", f"₹{my_trade['realized_pl']:,.0f}", f"{my_trade['realized_pl_pct']:+.1f}%")

        quality = result.get("quality")
        if quality and quality.get("flags"):
            st.markdown("**Fundamental Quality Flags**")
            icon_by_severity = {"red": "🔴", "yellow": "🟡", "green": "🟢"}
            for f in quality["flags"]:
                icon = icon_by_severity.get(f["severity"], "•")
                st.markdown(f"{icon} **{f['flag']}** — {f['description']}")
        elif quality and quality.get("error"):
            st.caption(f"Quality flags unavailable: {quality['error']}")

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
    symbols = parse_symbols(raw_input) if raw_input.strip() else []

    if use_my_trades:
        traded_symbols = parse_symbols(",".join(trade_history.keys()))
        symbols = list(dict.fromkeys(symbols + traded_symbols))  # de-dupe, keep order

    if not symbols:
        st.warning("Enter at least one company code, or check the box to include your traded stocks.")
    else:
        st.write(f"Analyzing {len(symbols)} stock(s): {', '.join(symbols)}")

        progress = st.progress(0)
        status = st.empty()

        def _on_progress(done, total):
            progress.progress(done / total)
            status.write(f"Processed {done}/{total}")

        results = analyze_stocks_parallel(
            symbols, chunk_size=50, max_workers=8, progress_cb=_on_progress,
        )
        progress.empty()
        status.empty()

        st.session_state["results"] = results

if "results" in st.session_state:
    results = st.session_state["results"]

    available_stages = sorted(
        {stage_key(r) for r in results if "error" not in r},
        key=lambda s: STAGE_ORDER.index(s) if s in STAGE_ORDER else len(STAGE_ORDER),
    )
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([3, 1, 1, 1])
    with filter_col1:
        selected_stages = st.multiselect(
            "Filter by stage",
            options=available_stages,
            default=available_stages,
        )
    with filter_col2:
        only_my_trades = st.checkbox("Only my previously traded stocks", value=False)
    with filter_col3:
        only_coppock_turnup = st.checkbox("Monthly Coppock turning up, value 3-10", value=False)
    with filter_col4:
        only_coppock_daily_turnup = st.checkbox("Daily Coppock turning up, value 3-10", value=False)

    def _on_gate_toggle(gk):
        val = st.session_state[f"gate_all_{gk}"]
        for ck in GATE_LABELS[gk]:
            st.session_state[f"chk_{gk}_{ck}"] = val

    def _on_check_toggle(gk):
        st.session_state[f"gate_all_{gk}"] = all(
            st.session_state.get(f"chk_{gk}_{ck}", False) for ck in GATE_LABELS[gk]
        )

    with st.expander("Filter by gates & attributes (stock must pass every ticked check)", expanded=True):
        required_checks = {}  # {(gate, check_key)}
        gate_cols_f = st.columns(4)
        for gc, gk in zip(gate_cols_f, ["G1", "G2", "G3", "G4"]):
            with gc:
                st.checkbox(f"**{GATE_NAMES[gk]}** (all)", key=f"gate_all_{gk}",
                            on_change=_on_gate_toggle, args=(gk,))
                for ck, label in GATE_LABELS[gk].items():
                    if st.checkbox(label, key=f"chk_{gk}_{ck}",
                                   on_change=_on_check_toggle, args=(gk,)):
                        required_checks[(gk, ck)] = True

    def _gates_hit(r):
        return all(r["gates"][gk][ck] for gk, ck in required_checks)

    def _coppock_turnup_hit(r, tf="monthly"):
        v = r["value"]
        cop, cop_prev = v.get(f"coppock_{tf}"), v.get(f"coppock_{tf}_prev")
        if cop is None or cop_prev is None:
            return False
        return cop > cop_prev and 3 <= cop <= 10

    filtered = [
        r for r in results
        if ("error" in r or stage_key(r) in selected_stages)
        and (not only_my_trades or ("error" not in r and r.get("my_trade")))
        and (not only_coppock_turnup or ("error" not in r and _coppock_turnup_hit(r)))
        and (not only_coppock_daily_turnup or ("error" not in r and _coppock_turnup_hit(r, "daily")))
        and (not required_checks or ("error" not in r and _gates_hit(r)))
    ]

    st.caption(f"Showing {len(filtered)} of {len(results)} stock(s)")

    zone_hits = [r for r in filtered if "error" not in r and r.get("in_trading_zone")]
    if zone_hits:
        st.info(
            f"🔁 {len(zone_hits)} of your previously traded stock(s) are back at/near your "
            f"last sell price: {', '.join(r['symbol'] for r in zone_hits)}"
        )

    def _cop_cell(v, tf):
        if v.get(f"coppock_{tf}") is None:
            return "N/A"
        return f"{v[f'coppock_{tf}']} — {v[f'coppock_{tf}_verdict']}"

    summary_rows = []
    for r in filtered:
        if "error" in r:
            summary_rows.append({"Symbol": r["symbol"], "Status": f"ERROR: {r['error']}"})
        else:
            tr      = r["trade"]
            pv      = r.get("pe_valuation") or {}
            peg     = r.get("peg") or {}
            quality = r.get("quality") or {}
            n_red    = sum(1 for f in quality.get("flags", []) if f["severity"] == "red")
            n_yellow = sum(1 for f in quality.get("flags", []) if f["severity"] == "yellow")
            flags_str = f"🔴{n_red} 🟡{n_yellow}" if (n_red or n_yellow) else "clean"
            my_trade = r.get("my_trade")
            summary_rows.append({
                "Symbol":       r["symbol"],
                "Price":        r["latest"]["price"],
                "Gates":        r["gates_score"],
                "RSI":          r["latest"]["rsi"],
                "Value":        f"{r['value']['value_score']}/4",
                "Coppock (D)":  _cop_cell(r["value"], "daily"),
                "Coppock (W)":  _cop_cell(r["value"], "weekly"),
                "Coppock (M)":  _cop_cell(r["value"], "monthly"),
                "5Y PE":        pv.get("verdict", "N/A"),
                "PEG":          peg.get("peg", "N/A"),
                "Flags":        flags_str,
                "Stage":        stage_key(r),
                "R:R":          tr["rr_ratio"] if tr else "N/A",
                "Buy":          "🚨" if r["buy_signal"] else "",
                "My Last Sell": f"₹{my_trade['avg_sell_price']} ({my_trade['last_sell_date']})" if my_trade else "",
                "Re-entry":     "🔁" if r.get("in_trading_zone") else "",
            })

    st.subheader("Summary")
    st.dataframe(pd.DataFrame(summary_rows), hide_index=True, use_container_width=True)

    st.subheader("Details")
    for r in filtered:
        render_result(r)
