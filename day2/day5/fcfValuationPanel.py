"""
FCF / Net-Income Valuation — Streamlit Panel
Automates the vS.xlsx sheet: value stocks on 3-yr avg FCF (banks: net income),
compare against market cap. Works on your own stock list or the whole Nifty 500.

Run with:
    streamlit run fcfValuationPanel.py
"""

import io
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
import streamlit as st

from fcfValuation import value_stock
from criteriaCheck import check_stock, CRITERIA, DEFAULT_T, PASS, FAIL, NA

NIFTY500_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
DEFAULTS = dict(years=3, rate=0.02, margin=0.5, bank_margin=0.35)

SHOW_COLS = ["symbol", "name", "industry", "basis", "yearly_cr", "avg_cr", "intrinsic_cr", "margin_x",
             "iv_after_margin_cr", "mcap_cr", "mcap_to_iv", "mcap_to_margin_iv", "verdict", "source", "note"]

st.set_page_config(page_title="FCF Valuation", layout="wide")
st.title("💰 FCF / Net-Income Valuation")
st.caption("Intrinsic value = 3-yr average FCF ÷ yield (banks: net income). "
           "Compared with market cap after a margin-of-safety haircut. All figures in ₹ crore.")


# ── Sidebar: settings ────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    custom = st.checkbox("Use my own factors", value=False,
                         help="Off = defaults from the sheet (0.5 / 0.35 / 2%).")
    margin = st.number_input("Margin-of-safety factor (non-banks, FCF)", 0.05, 1.0,
                             DEFAULTS["margin"], 0.05, disabled=not custom)
    bank_margin = st.number_input("Margin-of-safety factor (banks, net income)", 0.05, 1.0,
                                  DEFAULTS["bank_margin"], 0.05, disabled=not custom)
    rate = st.number_input("Capitalisation yield (0.02 = 50× earnings)", 0.005, 0.20,
                           DEFAULTS["rate"], 0.005, format="%.3f", disabled=not custom)
    years = st.number_input("Years averaged", 2, 5, DEFAULTS["years"], disabled=not custom)
    if not custom:
        margin, bank_margin, rate, years = (DEFAULTS[k] for k in ("margin", "bank_margin", "rate", "years"))
    st.caption(f"Active → margin **{margin}** · bank margin **{bank_margin}** · "
               f"yield **{rate}** · **{int(years)}** yrs")


# ── Helpers ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=24 * 3600, show_spinner="Downloading Nifty 500 list from NSE…")
def load_nifty500():
    r = requests.get(NIFTY500_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    return df.rename(columns={"Company Name": "Company", "Symbol": "symbol", "Industry": "industry"})


def run_valuations(symbols, industry_map=None, workers=8):
    """Value many stocks in parallel with a progress bar."""
    results, total = [], len(symbols)
    bar = st.progress(0.0, text=f"0 / {total}")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(value_stock, s, int(years), rate, margin, bank_margin): s for s in symbols}
        for i, f in enumerate(as_completed(futs), 1):
            results.append(f.result())
            bar.progress(i / total, text=f"{i} / {total}  ({futs[f]})")
    bar.empty()
    df = pd.DataFrame(results)
    if industry_map is not None:
        df["industry"] = df["symbol"].map(industry_map)
    return df


def show_results(df, key):
    if df.empty:
        return
    df = df.sort_values("mcap_to_margin_iv", na_position="last")
    verdict = df["verdict"].astype(str)
    errs = verdict.str.startswith("ERROR").sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stocks", len(df))
    c2.metric("Undervalued (with margin)", int(verdict.str.startswith("UNDERVALUED").sum()))
    c3.metric("Neg. earnings (skipped)", int(verdict.str.startswith("NEG").sum()))
    c4.metric("Errors", int(errs))

    verdicts = st.multiselect("Filter verdict", sorted(df["verdict"].dropna().unique()),
                              default=[], key=f"v_{key}")
    view = df[df["verdict"].isin(verdicts)] if verdicts else df
    cols = [c for c in SHOW_COLS if c in view.columns]
    st.dataframe(view[cols], width="stretch", hide_index=True)
    st.download_button("⬇️ Download results (CSV)", view[cols].to_csv(index=False).encode(),
                       file_name=f"fcf_valuation_{key}.csv", mime="text/csv", key=f"dl_{key}")
    st.caption("Market cap ÷ margin value < 1 → trades below intrinsic value even after the haircut. "
               "Ratios < 1 are cheap; ‘NEG’ rows have negative average earnings.")


# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_custom, tab_n500, tab_crit = st.tabs(["🔎 My stocks", "📊 Nifty 500", "✅ Criteria check"])

with tab_custom:
    raw = st.text_input("NSE symbols (comma-separated)", placeholder="e.g. INFY, HCLTECH, ICICIBANK, ITC")
    st.caption("Tip: if a symbol isn't found, give the Tickertape id as SYMBOL:SID (e.g. GREENPANEL:GREP).")
    if st.button("Value these stocks", type="primary", disabled=not raw.strip()):
        syms = [s.strip().upper() for s in raw.replace("\n", ",").split(",") if s.strip()]
        st.session_state["custom_res"] = run_valuations(syms)
    if "custom_res" in st.session_state:
        show_results(st.session_state["custom_res"], "custom")

with tab_n500:
    try:
        n500 = load_nifty500()
    except Exception as e:
        n500 = None
        st.error(f"Could not download the Nifty 500 list from NSE: {e}")

    if n500 is not None:
        c1, c2 = st.columns([1, 3])
        c1.download_button("⬇️ Download Nifty 500 list (CSV)", n500.to_csv(index=False).encode(),
                           file_name="nifty500_list.csv", mime="text/csv")
        c2.caption(f"{len(n500)} constituents · source: NSE Indices")

        if st.checkbox("Show Nifty 500 details", value=False):
            inds = sorted(n500["industry"].unique())
            pick = st.multiselect("Industry", inds, key="n500_detail_ind")
            q = st.text_input("Search company / symbol", key="n500_q")
            view = n500
            if pick:
                view = view[view["industry"].isin(pick)]
            if q:
                m = view["Company"].str.contains(q, case=False) | view["symbol"].str.contains(q, case=False)
                view = view[m]
            st.dataframe(view[["Company", "symbol", "industry", "ISIN Code"]],
                         width="stretch", hide_index=True)
            st.caption(f"{len(view)} shown")

        st.divider()
        st.subheader("Run valuation on Nifty 500")
        sel_inds = st.multiselect("Limit to industries (empty = all)", sorted(n500["industry"].unique()),
                                  key="n500_run_ind")
        pool = n500[n500["industry"].isin(sel_inds)] if sel_inds else n500
        cap = st.number_input("Max stocks to run (0 = all)", 0, len(pool), 0,
                              help="Each stock needs ~3 web calls; the full list takes a few minutes.")
        if cap:
            pool = pool.head(int(cap))
        st.caption(f"{len(pool)} stocks selected")
        if st.button("Run Nifty 500 valuation", type="primary"):
            st.session_state["n500_res"] = run_valuations(pool["symbol"].tolist(),
                                                          dict(zip(n500["symbol"], n500["industry"])))
        if "n500_res" in st.session_state:
            show_results(st.session_state["n500_res"], "nifty500")


# ── Criteria check (CompanyCriteria.xlsx) ────────────────────────────────────
ICON = {PASS: "✅", FAIL: "❌", NA: "➖"}


def run_criteria(symbols, T, workers=4):
    results, total = [], len(symbols)
    bar = st.progress(0.0, text=f"0 / {total}")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(check_stock, s, T): s for s in symbols}
        for i, f in enumerate(as_completed(futs), 1):
            results.append(f.result())
            bar.progress(i / total, text=f"{i} / {total}  ({futs[f]})")
    bar.empty()
    return results


def criteria_table(results):
    rows = []
    for r in results:
        if "error" in r:
            rows.append({"Symbol": r["symbol"], "Name": f"ERROR: {r['error']}", "Moat": "Unsure"})
            continue
        row = {"Symbol": r["symbol"], "Name": r["name"], "Group": r["industry"], "Moat": "Unsure"}
        for c in CRITERIA:
            st_, val, _ = r["results"][c]
            row[c] = f"{ICON[st_]} {val}" if st_ != NA else ICON[NA]
        rows.append(row)
    return pd.DataFrame(rows)


with tab_crit:
    st.markdown("Checks each stock against your **CompanyCriteria** checklist. "
                "✅ pass · ❌ fail · ➖ not applicable (excluded from score). "
                "Moat is a judgement call — set it per stock in the table.")
    with st.expander("Criteria thresholds (defaults from your sheet)"):
        t1, t2, t3 = st.columns(3)
        T = dict(
            pe=t1.number_input("P/E below", 1.0, 100.0, DEFAULT_T["pe"], 1.0),
            peg=t1.number_input("PEG below", 0.1, 5.0, DEFAULT_T["peg"], 0.1),
            peg3=t1.number_input("PEG 3y below (swing checker PEG)", 0.1, 5.0, DEFAULT_T["peg3"], 0.1),
            pb=t1.number_input("P/B below", 0.1, 20.0, DEFAULT_T["pb"], 0.1),
            de=t2.number_input("D/E below", 0.0, 5.0, DEFAULT_T["de"], 0.1),
            opm=t2.number_input("OPM above (%)", 0.0, 100.0, DEFAULT_T["opm"], 1.0),
            icr=t2.number_input("ICR above", 0.0, 100.0, DEFAULT_T["icr"], 1.0),
            roe=t3.number_input("ROE above (%)", 0.0, 100.0, DEFAULT_T["roe"], 1.0),
            fcf_sales=t3.number_input("FCF / sales above (%)", 0.0, 100.0, DEFAULT_T["fcf_sales"], 1.0),
            misses=t3.number_input("Years allowed to miss (D/E, OPM, ICR)", 0, 5, DEFAULT_T["misses"]),
        )

    mode = st.radio("Stocks", ["My symbols", "Nifty 500"], horizontal=True, key="crit_mode")
    syms = []
    if mode == "My symbols":
        raw_c = st.text_input("NSE symbols (comma-separated)", placeholder="e.g. TCS, INFY, ITC",
                              key="crit_syms")
        syms = [x.strip().upper() for x in raw_c.replace("\n", ",").split(",") if x.strip()]
    else:
        try:
            nf = load_nifty500()
            ind = st.multiselect("Industries (empty = all)", sorted(nf["industry"].unique()), key="crit_ind")
            pool = nf[nf["industry"].isin(ind)] if ind else nf
            cap_c = st.number_input("Max stocks (0 = all)", 0, len(pool), 25, key="crit_cap")
            pool = pool.head(int(cap_c)) if cap_c else pool
            st.caption(f"{len(pool)} stocks · ~4 web calls each; large runs take several minutes")
            syms = pool["symbol"].tolist()
        except Exception as e:
            st.error(f"Nifty 500 list unavailable: {e}")

    if st.button("Run criteria check", type="primary", disabled=not syms):
        st.session_state["crit_res"] = run_criteria(syms, T)

    res = st.session_state.get("crit_res")
    if res:
        table = criteria_table(res)
        st.subheader("Results")
        edited = st.data_editor(
            table, hide_index=True, width="stretch", key="crit_editor",
            column_config={"Moat": st.column_config.SelectboxColumn(
                "Moat (manual)", options=["Yes", "No", "Unsure"], required=True)},
            disabled=[c for c in table.columns if c != "Moat"])

        # final ranking: auto score + moat (Yes = +1 pass, No = +0 but counts as applicable)
        rank = []
        by_sym = {r["symbol"]: r for r in res}
        for _, row in edited.iterrows():
            r = by_sym[row["Symbol"]]
            if "error" in r:
                continue
            p, a = r["score"], r["applicable"]
            if row["Moat"] == "Yes":
                p, a = p + 1, a + 1
            elif row["Moat"] == "No":
                a += 1
            rank.append({"Symbol": r["symbol"], "Name": r["name"], "Passed": p, "Applicable": a,
                         "Score": f"{p}/{a}", "Pass %": round(100 * p / a) if a else 0})
        if rank:
            st.subheader("🏆 Ranking — most criteria passed")
            rk = pd.DataFrame(rank).sort_values(["Passed", "Pass %"], ascending=False)
            st.dataframe(rk, width="stretch", hide_index=True)
            st.download_button("⬇️ Download ranking (CSV)", rk.to_csv(index=False).encode(),
                               file_name="criteria_ranking.csv", mime="text/csv")

        ok = [r for r in res if "error" not in r]
        if ok:
            st.subheader("Detail")
            pick = st.selectbox("Stock", [r["symbol"] for r in ok], key="crit_pick")
            r = by_sym[pick]
            st.dataframe(pd.DataFrame(
                [{"Criterion": c, "": ICON[r["results"][c][0]], "Value": r["results"][c][1],
                  "Rule / note": r["results"][c][2]} for c in CRITERIA]),
                width="stretch", hide_index=True)
            h = r["history"].drop(columns=["icr_debtfree"]).round(1)
            st.caption("Yearly history (₹ crore; margins and returns in %)")
            st.dataframe(h, width="stretch", hide_index=True)
