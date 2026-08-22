"""
Rising 44 SMA Scanner (Enhanced)
--------------------------------
Conditions:
1. Close > 44 SMA
2. 44 SMA rising with minimum slope %
3. Price not overextended from SMA

Author: You
"""

import yfinance as yf
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

# --------------------------------------------------
# Configuration
# --------------------------------------------------
# STOCKS = [
#     "TCS.NS", "INFY.NS", "RELIANCE.NS",
#     "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS",
#     "ITC.NS", "LT.NS", "VBL.NS"
# ]


STOCKS = ["HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "TIMETECHNO.NS", "BAJFINANCE.NS", "DIVISLAB.NS", "HDFCLIFE.NS", "BAJAJFINSV.NS", "ICICIPRULI.NS", "HDFCAMC.NS", "NAM-INDIA.NS", "PGHH.NS", "MARICO.NS", "COLPAL.NS", "HINDUNILVR.NS", "BRITANNIA.NS", "DABUR.NS", "SBIN.NS", "NESTLEIND.NS", "ITC.NS", "ASIANPAINT.NS", "BERGEPAINT.NS", "DRREDDY.NS", "TITAN.NS", "BATAINDIA.NS", "PAGEIND.NS", "KPITTECH.NS", "HAVELLS.NS", "LTIM.NS", "TCS.NS", "INFY.NS", "HCLTECH.NS", "ABBOTINDIA.NS", "GLAXO.NS", "BAJAJ-AUTO.NS", "PFIZER.NS", "PIDILITIND.NS", "GILLETTE.NS", "RELIANCE.NS", "LTTS.NS", "DEEPAKNTR.NS", "FINEORG.NS"]


PERIOD = "6mo"
INTERVAL = "1d"

SMA_PERIOD = 44
SMA_LOOKBACK = 3

MIN_SLOPE_PCT = 0.4       # minimum SMA rise %
MIN_PRICE_GAP = 0.5      # min % above SMA
MAX_PRICE_GAP = 4.0      # max % above SMA


# --------------------------------------------------
# Fetch stock data
# --------------------------------------------------
def fetch_stock_data(ticker, period=PERIOD, interval=INTERVAL):
    try:
        df = yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            threads=False
        )
        return df if df is not None and not df.empty else None
    except Exception:
        return None


# --------------------------------------------------
# Rising 44 SMA Analysis (STRICT 고려)
# --------------------------------------------------
def rising_44_sma_analysis(df):
    close = df["Close"].squeeze()

    if close.ndim != 1 or len(close) < SMA_PERIOD + SMA_LOOKBACK:
        return None

    sma_44 = close.rolling(SMA_PERIOD).mean()

    latest_close = close.iloc[-1]
    latest_sma = sma_44.iloc[-1]
    past_sma = sma_44.iloc[-(SMA_LOOKBACK + 1)]

    # -------------------------
    # New Strong Conditions
    # -------------------------
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
        "Rising_44SMA_Signal": signal
    }


# --------------------------------------------------
# Runner
# --------------------------------------------------
def run_rising_44_sma_scan(stocks=STOCKS):
    results = []

    for ticker in stocks:
        df = fetch_stock_data(ticker)
        if df is None:
            continue

        data = rising_44_sma_analysis(df)
        if not data:
            continue

        if data["Rising_44SMA_Signal"]:
            results.append({
                "Stock": ticker,
                **data
            })

    return pd.DataFrame(results)


# --------------------------------------------------
# CLI Execution
# --------------------------------------------------
if __name__ == "__main__":
    df = run_rising_44_sma_scan()
    pd.set_option("display.max_columns", None)

    if df.empty:
        print("No stocks matched the Rising 44 SMA strict criteria.")
    else:
        print("\nStocks with STRONG Rising 44 SMA:\n")
        print(df)
