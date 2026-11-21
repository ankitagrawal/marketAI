"""
Half-Month High / Low — Streamlit Panel
Pick 1st half (1-15) or 2nd half (16-end) of a month, enter stock codes,
get the highest and lowest price and their dates within that half.

Run with:
    streamlit run halfMonthHighLow.py
"""

from datetime import date

import pandas as pd
import streamlit as st
import yfinance as yf

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def parse_symbols(raw):
    out = []
    for s in raw.replace("\n", ",").split(","):
        s = s.strip().upper()
        if not s:
            continue
        if "." not in s and not s.startswith("^"):
            s += ".NS"
        if s not in out:
            out.append(s)
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def load_daily(symbol, start, end):
    df = yf.download(symbol, start=start, end=end, interval="1d",
                     auto_adjust=True, progress=False)
    if df.empty:
        return df
    df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=["High", "Low"])


def half_range(year, month, half):
    """Return (first_day, last_day) of the half, as dates."""
    if half == "1st half (1-15)":
        return date(year, month, 1), date(year, month, 15)
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    return date(year, month, 16), nxt - pd.Timedelta(days=1)


def high_low(df, first, last):
    d = df.loc[pd.Timestamp(first):pd.Timestamp(last)]
    if d.empty:
        return None
    return {
        "High": round(float(d.High.max()), 2),
        "High Date": d.High.idxmax().date(),
        "Low": round(float(d.Low.min()), 2),
        "Low Date": d.Low.idxmin().date(),
        "Range %": round((d.High.max() / d.Low.min() - 1) * 100, 2),
        "Days": len(d),
    }


st.set_page_config(page_title="Half-Month High/Low", layout="wide")
st.title("📅 Half-Month High / Low")
st.caption("Highest and lowest price of each stock within the 1st or 2nd half of a month")

today = date.today()

c1, c2, c3 = st.columns([2, 1, 1])
half = c1.radio("Half of month", ["1st half (1-15)", "2nd half (16-end)"], horizontal=True)
year = c2.number_input("Year", min_value=2000, max_value=today.year, value=today.year, step=1)
month = c3.selectbox("Month", range(1, 13), index=today.month - 1,
                     format_func=lambda m: MONTHS[m - 1])

raw = st.text_input("Stock codes (comma-separated, NSE assumed)",
                    placeholder="e.g. RELIANCE, TCS, INFY, TATASTEEL")
history = st.checkbox("Also show the same half for each of the previous 12 months", value=False)

if st.button("Get High / Low", type="primary"):
    symbols = parse_symbols(raw)
    if not symbols:
        st.warning("Enter at least one stock code.")
        st.stop()

    first, last = half_range(int(year), int(month), half)
    if first > today:
        st.error("That half hasn't started yet.")
        st.stop()
    if last >= today:
        st.info(f"Half is still in progress — data is up to the latest trading day (today is {today}).")

    rows, hist_rows = [], []
    bar = st.progress(0.0)
    for i, sym in enumerate(symbols):
        try:
            if history:
                # 13 halves: selected one + previous 12 months
                periods = []
                y, m = int(year), int(month)
                for _ in range(13):
                    periods.append(half_range(y, m, half) + (y, m))
                    y, m = (y - 1, 12) if m == 1 else (y, m - 1)
                start = periods[-1][0]
            else:
                periods = [first, last, int(year), int(month)]
                periods = [tuple(periods)]
                start = first
            df = load_daily(sym, start, last + pd.Timedelta(days=1))
            if df.empty:
                rows.append({"Stock": sym, "Note": "No data"})
            else:
                for f, l, y, m in periods:
                    r = high_low(df, f, l)
                    if r is None:
                        continue
                    rec = {"Stock": sym.replace(".NS", ""), "Month": f"{MONTHS[m-1][:3]} {y}", **r}
                    (rows if (f, l) == (first, last) else hist_rows).append(rec)
        except Exception as e:
            rows.append({"Stock": sym, "Note": f"Error: {e}"})
        bar.progress((i + 1) / len(symbols))
    bar.empty()

    st.subheader(f"{half} — {MONTHS[int(month)-1]} {int(year)}  ({first} → {last})")
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    st.subheader("Day-wise prices")
    for sym in symbols:
        df = load_daily(sym, first, last + pd.Timedelta(days=1))
        if df.empty:
            continue
        d = df.loc[pd.Timestamp(first):pd.Timestamp(last), ["Open", "High", "Low", "Close", "Volume"]].copy()
        if d.empty:
            continue
        d["Change %"] = d["Close"].pct_change().mul(100).round(2)
        wk = []
        for ws, g in d.groupby(d.index.to_period("W-SUN")):
            wk.append({
                "Week": f"{ws.start_time:%d %b} – {ws.end_time:%d %b}",
                "High": round(float(g.High.max()), 2),
                "High Date": g.High.idxmax().strftime("%a %d %b"),
                "Low": round(float(g.Low.min()), 2),
                "Low Date": g.Low.idxmin().strftime("%a %d %b"),
                "Days": len(g),
            })
        d.index = d.index.strftime("%a %d %b %Y")
        hi_day, lo_day = d["High"].idxmax(), d["Low"].idxmin()

        def mark(row):
            if row.name == hi_day:
                return ["background-color: rgba(46,160,67,0.3)"] * len(row)
            if row.name == lo_day:
                return ["background-color: rgba(248,81,73,0.3)"] * len(row)
            return [""] * len(row)

        with st.expander(f"{sym.replace('.NS', '')} — daily prices ({len(d)} days)", expanded=len(symbols) == 1):
            st.markdown("**Calendar weeks (Mon–Sun), clipped to this half**")
            st.dataframe(pd.DataFrame(wk), width="stretch", hide_index=True)
            st.markdown("**Daily**")
            st.caption("Green row = highest high, red row = lowest low")
            st.dataframe(d.style.apply(mark, axis=1).format(
                {"Open": "{:.2f}", "High": "{:.2f}", "Low": "{:.2f}", "Close": "{:.2f}",
                 "Volume": "{:,.0f}", "Change %": "{:.2f}"}, na_rep="-"), width="stretch")

    if history and hist_rows:
        st.subheader("Previous 12 months — same half")
        hdf = pd.DataFrame(hist_rows)
        for sym, g in hdf.groupby("Stock", sort=False):
            with st.expander(sym, expanded=len(symbols) == 1):
                st.dataframe(g.drop(columns="Stock"), width="stretch", hide_index=True)
