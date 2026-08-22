"""
Combined Stock Scanner
----------------------
Filters:
1. Rising 44 SMA (daily)
   - Close > 44 SMA
   - SMA slope >= 0.4%
   - Price 0.5%–4% above SMA
2. Weekly filters:
   - Weekly Open >= 200
   - Weekly Volume > 200,000
   - RSI(14) crossed above 55 last week
"""

import yfinance as yf
import pandas as pd
import ta
import warnings
warnings.filterwarnings("ignore")

# -----------------------------
# Configuration
# -----------------------------
#STOCKS = ["TCS.NS", "INFY.NS", "RELIANCE.NS", "HDFCBANK.NS", "SBIN.NS", "LT.NS", "VBL.NS"]
STOCKS = ["HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "TIMETECHNO.NS", "BAJFINANCE.NS", "DIVISLAB.NS", "HDFCLIFE.NS", "BAJAJFINSV.NS", "ICICIPRULI.NS", "HDFCAMC.NS", "NAM-INDIA.NS", "PGHH.NS", "MARICO.NS", "COLPAL.NS", "HINDUNILVR.NS", "BRITANNIA.NS", "DABUR.NS", "SBIN.NS", "NESTLEIND.NS", "ITC.NS", "ASIANPAINT.NS", "BERGEPAINT.NS", "DRREDDY.NS", "TITAN.NS", "BATAINDIA.NS", "PAGEIND.NS", "KPITTECH.NS", "HAVELLS.NS", "LTIM.NS", "TCS.NS", "INFY.NS", "HCLTECH.NS", "ABBOTINDIA.NS", "GLAXO.NS", "BAJAJ-AUTO.NS", "PFIZER.NS", "PIDILITIND.NS", "GILLETTE.NS", "RELIANCE.NS", "LTTS.NS", "DEEPAKNTR.NS", "FINEORG.NS"]

PERIOD_DAILY = "6mo"
PERIOD_WEEKLY = "6mo"
INTERVAL_DAILY = "1d"
INTERVAL_WEEKLY = "1wk"

SMA_PERIOD = 44
SMA_LOOKBACK = 3
MIN_SLOPE_PCT = 0.4
MIN_PRICE_GAP = 0.5
MAX_PRICE_GAP = 4.0

RSI_PERIOD = 14
RSI_THRESHOLD = 55
MIN_OPEN = 200
MIN_VOLUME = 200000

# -----------------------------
# Fetch data
# -----------------------------
def fetch_data(ticker, period, interval):
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False, threads=False)
        return df if df is not None and not df.empty else None
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

# -----------------------------
# Rising 44 SMA check
# -----------------------------
def check_rising_sma(df):
    close = df["Close"].squeeze()
    if close.ndim != 1 or len(close) < SMA_PERIOD + SMA_LOOKBACK:
        return None

    sma_44 = close.rolling(SMA_PERIOD).mean()
    latest_close = close.iloc[-1]
    latest_sma = sma_44.iloc[-1]
    past_sma = sma_44.iloc[-(SMA_LOOKBACK + 1)]

    slope_pct = ((latest_sma - past_sma) / past_sma) * 100
    price_gap_pct = ((latest_close - latest_sma) / latest_sma) * 100

    signal = (
        latest_close > latest_sma and
        slope_pct >= MIN_SLOPE_PCT and
        MIN_PRICE_GAP <= price_gap_pct <= MAX_PRICE_GAP
    )

    return {
        "Close": round(latest_close, 2),
        "SMA_44": round(latest_sma, 2),
        "SMA_44_Past": round(past_sma, 2),
        "SMA_Slope_%": round(slope_pct, 2),
        "Price_Gap_%": round(price_gap_pct, 2),
        "Rising_44SMA": signal
    }

# -----------------------------
# Weekly filter check
# -----------------------------
def check_weekly_filter(df):
    df = df.copy()
    
    # Ensure 'Close' is 1D
    close = df['Close']
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    
    # Compute RSI
    rsi_series = ta.momentum.RSIIndicator(close, window=RSI_PERIOD).rsi()
    df['RSI'] = rsi_series.values  # ensure numeric array, not Series of Series

    if len(df) < 2:
        return False

    # Extract last two rows as scalars
    last_open = float(df['Open'].iloc[-1])
    last_volume = float(df['Volume'].iloc[-1])
    prev_rsi = float(df['RSI'].iloc[-2])
    last_rsi = float(df['RSI'].iloc[-1])

    # Conditions
    cond_open = last_open >= MIN_OPEN
    cond_volume = last_volume > MIN_VOLUME
    cond_rsi_cross = prev_rsi <= RSI_THRESHOLD < last_rsi

    return cond_open and cond_volume and cond_rsi_cross



# -----------------------------
# Combined scanner
# -----------------------------
def run_combined_scan(stocks=STOCKS):
    results = []

    for ticker in stocks:
        daily_df = fetch_data(ticker, PERIOD_DAILY, INTERVAL_DAILY)
        weekly_df = fetch_data(ticker, PERIOD_WEEKLY, INTERVAL_WEEKLY)

        if daily_df is None or weekly_df is None:
            continue

        sma_data = check_rising_sma(daily_df)
        weekly_ok = check_weekly_filter(weekly_df)

        if sma_data and sma_data["Rising_44SMA"] and weekly_ok:
            results.append({
                "Stock": ticker,
                **sma_data
            })

    return pd.DataFrame(results)

# -----------------------------
# CLI Execution
# -----------------------------
if __name__ == "__main__":
    df = run_combined_scan()
    pd.set_option("display.max_columns", None)

    if df.empty:
        print("No stocks passed all combined filters.")
    else:
        print("\nStocks passing Rising 44 SMA + Weekly Filters:\n")
        print(df)
