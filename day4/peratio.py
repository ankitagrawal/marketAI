import yfinance as yf
import pandas as pd
import numpy as np

def pe_analysis_bulk_with_peg(tickers):
    results = []

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            price_df = stock.history(period="5y")

            eps = info.get("trailingEps")
            current_price = info.get("currentPrice")
            growth = info.get("earningsGrowth")  # Forward earnings growth (decimal)

            if eps is None or eps <= 0 or current_price is None or price_df.empty or growth is None:
                continue

            # Current PE
            current_pe = current_price / eps

            # Historical PE (proxy)
            price_df["PE"] = price_df["Close"] / eps
            price_df = price_df[(price_df["PE"] > 0) & (price_df["PE"] < 150)]

            median_pe = np.median(price_df["PE"])
            pe_diff_pct = ((current_pe - median_pe) / median_pe) * 100

            # Classification logic
            if -40 <= pe_diff_pct < -20:
                verdict = "BEST BUY"
            elif -20 <= pe_diff_pct <= 20:
                verdict = "MEDICORE"
            elif pe_diff_pct > 20:
                verdict = "AVOID"
            else:
                verdict = "TOO CHEAP – CHECK QUALITY"

            # PEG calculation (using forward earnings growth)
            peg = current_pe / (growth * 100) if growth > 0 else None

            results.append({
                "Ticker": ticker,
                "Current PE": round(current_pe, 2),
                "Median PE (5Y)": round(median_pe, 2),
                "PE Diff (%)": round(pe_diff_pct, 1),
                "PEG": round(peg, 2) if peg else None,
                "Verdict": verdict
            })

        except Exception as e:
            print(f"Error for {ticker}: {e}")

    return pd.DataFrame(results)

# Example usage
STOCKS = ["TCS.NS", "INFY.NS", "HCLTECH.NS", "BATAINDIA.NS"]
df = pe_analysis_bulk_with_peg(STOCKS)
print(df)
