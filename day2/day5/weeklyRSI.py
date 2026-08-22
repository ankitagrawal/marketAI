import yfinance as yf


def calculate_rsi(symbol, period=14):
    try:
        df = yf.download(
            symbol,
            period="5y",
            interval="1wk",
            auto_adjust=True,
            progress=False,
        )

        # Skip if no data
        if df.empty:
            print(f"Skipping {symbol}: No data found")
            return None

        # Handle both MultiIndex and single-column DataFrames
        if ("Close", symbol) in df.columns:
            close = df[("Close", symbol)]
        elif "Close" in df.columns:
            close = df["Close"]
        else:
            print(f"Skipping {symbol}: Close price not found")
            return None

        close = close.dropna()

        if len(close) < period:
            print(f"Skipping {symbol}: Insufficient data")
            return None

        delta = close.diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        if rsi.dropna().empty:
            print(f"Skipping {symbol}: RSI could not be calculated")
            return None

        return round(float(rsi.dropna().iloc[-1]), 2)

    except Exception as e:
        print(f"Skipping {symbol}: {e}")
        return None


etfs = [
    "PHARMABEES.NS",
    "MODEFENCE.NS",
    "MOCAPITAL.NS",
    "PVTBANIETF.NS",
    "EVIETF.NS",
    "MOMGF.NS",
    "MOMNIC.NS",
    "BANKBEES.NS",
    "MOTOUR.NS",
    "INFRAIETF.NS",
    "BFSI.NS",
    "MOREALTY.NS",
    "AUTOBEES.NS",
    "METALIETF.NS",
    "PSUBNKBEES.NS",
    "ICICIB22.NS",
    "OILIETF.NS",
    "FMCGIETF.NS",
    "CPSEETF.NS",
    "ITBEES.NS",
    "NIFTYBEES.NS",
]

print(f"{'ETF':<20} {'Weekly RSI'}")
print("-" * 35)

for ticker in etfs:
    rsi = calculate_rsi(ticker)
    if rsi is not None:
        print(f"{ticker:<20} {rsi}")