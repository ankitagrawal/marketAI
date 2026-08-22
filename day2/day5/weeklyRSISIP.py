import yfinance as yf

# weekly RSI above 70 eligible for profit booking
#RSI below 50 eligible for buying
#RSI below 45 eligible for more allocation

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
    "MON100.NS",
    "NIFTYBEES.NS",
    "JUNIORBEES.NS",
    "MIDCAPIETF.NS",
    "GOLDBEES.NS",
    "SILVERBEES.NS",
    "HDFCSML250.NS",
    "MOM100.NS",
    "HNGSNGBEES.NS"


]


etfs += [
    "PHARMABEES.NS",
    "MOREALTY.NS",
    "MODEFENCE.NS",
    "PVTBANIETF.NS",
    "EVIETF.NS",
    "MOCAPITAL.NS",
    "MOMGF.NS",
    "MOMNC.NS",
    "BANKBEES.NS",
    "BFSI.NS",
    "AUTOBEES.NS",
    "MOTOUR.NS",
    "METALIETF.NS",
    "INFRAIETF.NS",
    "PSUBNKBEES.NS",
    "OILIETF.NS",
    "ITBEES.NS",
    "CPSEETF.NS",
    "ICICIB22.NS",
    "FMCGIETF.NS",
]

print(f"{'ETF':<20} {'Weekly RSI'}")
print("-" * 35)

results = []

for ticker in etfs:
    rsi = calculate_rsi(ticker)
    if rsi is not None:
        results.append((ticker, rsi))

# Sort by RSI
results.sort(key=lambda x: x[1], reverse=True)

print("\n========== ALL ETFs ==========")
print(f"{'ETF':<20} {'Weekly RSI'}")
print("-" * 35)
for ticker, rsi in results:
    print(f"{ticker:<20} {rsi:>6.2f}")

print("\n========== RSI > 70 (Profit Booking) ==========")
for ticker, rsi in results:
    if rsi > 70:
        print(f"{ticker:<20} {rsi:>6.2f}")

print("\n========== RSI < 50 (Buy) ==========")
for ticker, rsi in results:
    if 45 <= rsi < 50:
        print(f"{ticker:<20} {rsi:>6.2f}")

print("\n========== RSI < 45 (More Allocation) ==========")
for ticker, rsi in results:
    if rsi < 45:
        print(f"{ticker:<20} {rsi:>6.2f}")