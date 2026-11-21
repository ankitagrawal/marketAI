from datetime import date

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


def half_month_high(symbol):
    """Highest price in the current half of the month (1-15 first, 16-end second)."""
    try:
        today = date.today()
        start_day = 1 if today.day <= 15 else 16
        start = today.replace(day=start_day)

        df = yf.download(
            symbol,
            start=start.isoformat(),
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        if df.empty:
            print(f"Skipping {symbol}: No data for current half-month")
            return None

        high = df["High"].iloc[:, 0].dropna()
        close = df["Close"].iloc[:, 0].dropna()
        if high.empty or close.empty:
            return None

        peak = float(high.max())
        last = float(close.iloc[-1])
        return round(peak, 2), round(last, 2), round((last / peak - 1) * 100, 2)

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
today = date.today()
half = "1-15" if today.day <= 15 else "16-end"
print(f"\n========== HIGH OF CURRENT HALF-MONTH ({today:%b %Y}, days {half}) ==========")
print(f"{'ETF':<20} {'High':>10} {'Last':>10} {'% from high':>12}")
print("-" * 55)
for ticker, _ in results:
    res = half_month_high(ticker)
    if res:
        peak, last, pct = res
        print(f"{ticker:<20} {peak:>10.2f} {last:>10.2f} {pct:>11.2f}%")
