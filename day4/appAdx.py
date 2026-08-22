import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import time

st.set_page_config(page_title="ADX Scanner", layout="wide")
st.title("📈 ADX Stock Scanner (NSE)")

# ---------------------------------
# SAFE YFINANCE DOWNLOAD
# ---------------------------------
@st.cache_data(ttl=3600)
def safe_download(symbol, period, interval, retries=3):
    for _ in range(retries):
        try:
            df = yf.download(
                symbol,
                period=period,
                interval=interval,
                progress=False,
                threads=False
            )
            if not df.empty:
                return df
        except Exception:
            time.sleep(2)
    return pd.DataFrame()

# ---------------------------------
# ADX CALCULATION
# ---------------------------------
def calculate_adx(df, period=14):
    df = df.copy()

    df['TR'] = np.maximum(
        df['High'] - df['Low'],
        np.maximum(
            abs(df['High'] - df['Close'].shift(1)),
            abs(df['Low'] - df['Close'].shift(1))
        )
    )

    df['+DM'] = np.where(
        (df['High'] - df['High'].shift(1)) > (df['Low'].shift(1) - df['Low']),
        np.maximum(df['High'] - df['High'].shift(1), 0),
        0
    )

    df['-DM'] = np.where(
        (df['Low'].shift(1) - df['Low']) > (df['High'] - df['High'].shift(1)),
        np.maximum(df['Low'].shift(1) - df['Low'], 0),
        0
    )

    df['TR_smooth'] = df['TR'].rolling(period).mean()
    df['+DM_smooth'] = df['+DM'].rolling(period).mean()
    df['-DM_smooth'] = df['-DM'].rolling(period).mean()

    df['+DI'] = 100 * df['+DM_smooth'] / df['TR_smooth']
    df['-DI'] = 100 * df['-DM_smooth'] / df['TR_smooth']

    df['DX'] = 100 * abs(df['+DI'] - df['-DI']) / (df['+DI'] + df['-DI'])
    df['ADX'] = df['DX'].rolling(period).mean()

    return df.dropna()

# ---------------------------------
# SIGNAL LOGIC
# ---------------------------------
def get_signal(df):
    last = df.iloc[-1]
    adx = float(last['ADX'])
    plus_di = float(last['+DI'])
    minus_di = float(last['-DI'])

    if adx < 20:
        return "AVOID", adx
    if adx > 25:
        return ("BUY", adx) if plus_di > minus_di else ("SELL", adx)
    return "HOLD", adx

# ---------------------------------
# SIDEBAR INPUTS
# ---------------------------------
st.sidebar.header("⚙️ Settings")

stock_input = st.sidebar.text_area(
    "Enter NSE Symbols (comma separated)",
    value="RELIANCE.NS, TCS.NS, INFY.NS, HDFCBANK.NS"
)

period = st.sidebar.selectbox("Period", ["3mo", "6mo", "1y"], index=1)
interval = st.sidebar.selectbox("Interval", ["1d", "1wk"], index=0)

run = st.sidebar.button("🔍 Run Scan")

# ---------------------------------
# MAIN LOGIC
# ---------------------------------
if run:
    stocks = [s.strip().upper() for s in stock_input.split(",") if s.strip()]
    results = []

    with st.spinner("Scanning stocks..."):
        for stock in stocks:
            df = safe_download(stock, period, interval)

            if df.empty or len(df) < 50:
                st.warning(f"⚠️ No data for {stock}")
                continue

            try:
                df = calculate_adx(df)
                signal, adx = get_signal(df)

                results.append({
                    "Stock": stock,
                    "ADX": round(adx, 2),
                    "Signal": signal
                })

            except Exception as e:
                st.error(f"Error processing {stock}")

    if results:
        result_df = pd.DataFrame(results).sort_values("ADX", ascending=False)
        st.subheader("📊 ADX Scan Results")
        st.dataframe(result_df, use_container_width=True)
    else:
        st.info("No valid results.")
