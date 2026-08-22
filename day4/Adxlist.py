"""
ADX + Momentum + Valuation Scanner
Properly layered architecture
Notebook & Streamlit compatible
"""

# ------------------------------------------------------------------
# Imports
# ------------------------------------------------------------------
import warnings
warnings.filterwarnings("ignore")

import time
import pandas as pd
import yfinance as yf
import ta

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------


#STOCKS = ["HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "TIMETECHNO.NS", "BAJFINANCE.NS"]

STOCKS = ["HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "TIMETECHNO.NS", "BAJFINANCE.NS", "DIVISLAB.NS", "HDFCLIFE.NS", "BAJAJFINSV.NS", "ICICIPRULI.NS", "HDFCAMC.NS", "NAM-INDIA.NS", "PGHH.NS", "MARICO.NS", "COLPAL.NS", "HINDUNILVR.NS", "BRITANNIA.NS", "DABUR.NS", "SBIN.NS", "NESTLEIND.NS", "ITC.NS", "ASIANPAINT.NS", "BERGEPAINT.NS", "DRREDDY.NS", "TITAN.NS", "BATAINDIA.NS", "PAGEIND.NS", "KPITTECH.NS", "HAVELLS.NS", "LTIM.NS", "TCS.NS", "INFY.NS", "HCLTECH.NS", "ABBOTINDIA.NS", "GLAXO.NS", "BAJAJ-AUTO.NS", "PFIZER.NS", "PIDILITIND.NS", "GILLETTE.NS", "RELIANCE.NS", "LTTS.NS", "DEEPAKNTR.NS", "FINEORG.NS"]


PERIOD = "1y"
INTERVAL = "1d"

# ------------------------------------------------------------------
# Data Fetching
# ------------------------------------------------------------------
def fetch_stock_data(stock, retries=3):
    for _ in range(retries):
        try:
            df = yf.download(
                stock,
                period=PERIOD,
                interval=INTERVAL,
                progress=False,
                threads=False
            )
            if not df.empty:
                return df
        except Exception:
            time.sleep(2)
    return pd.DataFrame()

def load_all_stocks(stocks):
    return {
        s: df for s in stocks
        if not (df := fetch_stock_data(s)).empty
    }

# ------------------------------------------------------------------
# ADX
# ------------------------------------------------------------------
def compute_adx(df):
    try:
        high = df["High"].squeeze()
        low = df["Low"].squeeze()
        close = df["Close"].squeeze()

        # HARD SAFETY CHECK
        if high.ndim != 1 or low.ndim != 1 or close.ndim != 1:
            return None

        if len(close) < 14:
            return None

        adx_ind = ta.trend.ADXIndicator(
            high=high,
            low=low,
            close=close,
            window=14
        )

        adx = adx_ind.adx()
        plus_di = adx_ind.adx_pos()
        minus_di = adx_ind.adx_neg()

        return pd.DataFrame({
            "ADX": adx,
            "+DI": plus_di,
            "-DI": minus_di
        })

    except Exception as e:
        print("ADX compute error:", e)
        return None


def adx_signal(latest):
    if latest["ADX"] < 20:
        return "AVOID"
    if latest["ADX"] > 25:
        return "BUY" if latest["+DI"] > latest["-DI"] else "SELL"
    return "HOLD"

# ------------------------------------------------------------------
# Fundamentals
# ------------------------------------------------------------------
def get_fundamentals(ticker):
    try:
        info = yf.Ticker(ticker).info
        pe = info.get("trailingPE")
        pb = info.get("priceToBook")
        return (
            pe if isinstance(pe, (int, float)) else None,
            pb if isinstance(pb, (int, float)) else None
        )
    except Exception:
        return None, None

# ------------------------------------------------------------------
# ✅ TECHNICALS (PURE FUNCTION)
# ------------------------------------------------------------------
def compute_technicals(ticker, df):
    """
    Returns:
    - technical indicators
    - momentum score
    - Recommendation_VALUE
    """

    close = df["Close"].squeeze()

    if close.ndim != 1 or len(close) < 200:
        return None

    close = close.astype(float)

    # Indicators
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    macd_ind = ta.trend.MACD(close)
    macd = macd_ind.macd()
    macd_signal = macd_ind.macd_signal()

    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    bb_high = bb.bollinger_hband()
    bb_low = bb.bollinger_lband()

    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()

    # Latest
    latest = {
        "Stock": ticker,
        "Close": round(close.iloc[-1], 2),
        "RSI": round(rsi.iloc[-1], 2),
        "MACD": round(macd.iloc[-1], 2),
        "MACD_Signal": round(macd_signal.iloc[-1], 2),
        "BB_High": round(bb_high.iloc[-1], 2),
        "BB_Low": round(bb_low.iloc[-1], 2),
        "MA50": round(ma50.iloc[-1], 2),
        "MA200": round(ma200.iloc[-1], 2),
    }

    # -------------------------
    # FULL ORIGINAL SCORE LOGIC
    # -------------------------
    score = 0

    score += 1 if latest["RSI"] < 50 else (-1 if latest["RSI"] > 70 else 0)
    score += 1 if latest["MACD"] > latest["MACD_Signal"] else -1
    score += (
        1 if latest["Close"] > latest["MA50"]
        and latest["Close"] > latest["MA200"]
        else -1
    )
    score += (
        1 if latest["Close"] <= latest["BB_Low"] * 1.03
        else -1 if latest["Close"] >= latest["BB_High"] * 0.97
        else 0
    )

    recommendation_value = (
        "STRONG BUY" if score >= 4 else
        "BUY" if score == 3 else
        "HOLD" if score == 2 else
        "SELL"
    )

    latest.update({
        "Score": score,
        "Recommendation_VALUE": recommendation_value
    })

    return latest






# ------------------------------------------------------------------
# ✅ SMA STRUCTURE (PURE FUNCTION)
# ------------------------------------------------------------------
def compute_sma_structure(df):
    close = df["Close"].squeeze()

    if close.ndim != 1 or len(close) < 200:
        return None

    close = close.astype(float)

    sma_periods = [5, 10, 15, 20, 50, 100, 200]
    sma = {p: close.rolling(p).mean().iloc[-1] for p in sma_periods}

    cmp_price = close.iloc[-1]

    max_sma_except_200 = max(sma[p] for p in sma_periods if p != 200)

    structure_ok = (
        cmp_price > max_sma_except_200 and
        cmp_price < sma[200]
    )

    return {
        "CMP": round(cmp_price, 2),
        **{f"SMA_{p}": round(sma[p], 2) for p in sma_periods},
        "SMA_STRUCTURE_OK": structure_ok
    }


SMA_PERIOD = 44
SMA_LOOKBACK = 3

MIN_SLOPE_PCT = 0.4       # minimum SMA rise %
MIN_PRICE_GAP = 0.5      # min % above SMA
MAX_PRICE_GAP = 4.0      # max % above SMA


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

# ------------------------------------------------------------------
# ✅ STOCK ANALYSIS (ORCHESTRATION)
# ------------------------------------------------------------------
def analyze_stock(ticker, stock_data_map):
    if ticker not in stock_data_map:
        return None

    df = stock_data_map[ticker]
    if df is None or df.empty:
        return None

    # --- Technicals ---
    tech = compute_technicals(ticker, df)
    if tech is None:
        return None
    

        # --- SMA Structure ---
    sma_data = compute_sma_structure(df)
    if sma_data is None:
        return None
    tech.update(sma_data)

   

    sma44_data = rising_44_sma_analysis(df)
    if sma44_data is None:
        return None
    tech.update(sma44_data)

    # --- ADX ---
    adx_df = compute_adx(df)
    if adx_df.empty:
        return None

    latest_adx = adx_df.iloc[-1]

    # --- Fundamentals ---
    pe, pb = get_fundamentals(ticker)

    # --- Momentum + Valuation rule ---
    momentum_ok = (
        50 <= tech["RSI"] <= 70 and
        tech["MACD"] > tech["MACD_Signal"] and
        tech["Close"] >= 0.95 * tech["BB_High"]
    )

    valuation_ok = (
        pe is not None and pe < 22.8 and
        pb is not None and pb < 3.36
    )

    tech.update({
        "ADX": round(latest_adx["ADX"], 2),
        "ADX_SIGNAL": adx_signal(latest_adx),
        "P/E": pe,
        "P/B": pb,
        "Recommendation_MOMENTUM": (
            "BUY" if momentum_ok and valuation_ok else "NOCALL"
        )
    })

    return tech

# ------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------
def run_analysis(stocks=STOCKS):
    print(f"📊 Analyzing {len(stocks)} stocks...")
    stock_data_map = load_all_stocks(stocks)
    results = []

    for ticker in stock_data_map:
        row = analyze_stock(ticker, stock_data_map)
        if row:
            results.append(row)
    print(f"📊 Analyzed {len(results)} stocks.")

    return pd.DataFrame(results)

# ------------------------------------------------------------------
# Execute
# ------------------------------------------------------------------
if __name__ == "__main__":
    pd.set_option("display.max_columns", None)
    print(run_analysis())
