"""
Stock Analyzer
==============
Python port of a Google Sheets LAMBDA formula that recommends Buy/Average Out,
Avoid/Hold, or Short History for a list of tickers.

Logic:
  1. Find the date of the 52-week (364-day) high.
  2. Pull daily closes from that high date to today.
  3. Build a cumulative (expanding) average of those closes.
  4. Look at the last 10 cumulative averages.
  5. If the most recent cumulative average is strictly greater than each of
     the previous 9, signal "Buy/Average Out"; otherwise "Avoid/Hold".
  6. If fewer than 10 trading days of data exist, signal "Short History".

Requirements:
    pip install yfinance pandas

Usage:
    python stock_analyzer.py AAPL MSFT GOOG
    python stock_analyzer.py --file tickers.txt
    python stock_analyzer.py --csv results.csv AAPL MSFT GOOG
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from typing import List, Tuple

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    sys.stderr.write(
        "Missing dependency 'yfinance'. Install with: pip install yfinance pandas\n"
    )
    raise


def analyze_stock(ticker: str) -> Tuple[str, dict]:
    """
    Analyze a single ticker. Returns (signal, details_dict).

    Signals:
        "Buy/Average Out"  - uptrend confirmed by cumulative-average check
        "Avoid/Hold"       - trend check failed
        "Short History"    - fewer than 10 data points from the 52-week high
        "TICKER NOT FOUND" - yfinance returned no data
    """
    details = {"ticker": ticker}
    today = date.today()
    year_ago = today - timedelta(days=364)

    # ---- 1. Pull the last ~year of data and find the high ---------------
    try:
        hist = yf.download(
            ticker,
            start=year_ago.isoformat(),
            end=(today + timedelta(days=1)).isoformat(),
            progress=False,
            auto_adjust=False,
        )
    except Exception as exc:  # network / yfinance errors
        details["error"] = str(exc)
        return "TICKER NOT FOUND", details

    if hist is None or hist.empty:
        return "TICKER NOT FOUND", details

    # yfinance may return a MultiIndex on columns when a single ticker is
    # requested; flatten it so we can do hist["High"] reliably.
    if isinstance(hist.columns, pd.MultiIndex):
        hist.columns = hist.columns.get_level_values(0)

    if "High" not in hist.columns or "Close" not in hist.columns:
        return "TICKER NOT FOUND", details

    # ---- 2. Date of the 52-week high ------------------------------------
    high_series = hist["High"]
    # Some yfinance versions hand back a 1-col DataFrame here; squeeze to Series
    if isinstance(high_series, pd.DataFrame):
        high_series = high_series.squeeze("columns")
    high_series = high_series.dropna()

    if high_series.empty:
        high_date = pd.Timestamp(today - timedelta(days=30))
        high_price = float("nan")
    else:
        high_date = high_series.idxmax()
        # idxmax can still return a Series in odd shapes; coerce to scalar
        if isinstance(high_date, pd.Series):
            high_date = high_date.iloc[0]
        high_price = float(high_series.loc[high_date])
        if isinstance(high_price, pd.Series):
            high_price = float(high_price.iloc[0])

    details["high_date"] = pd.Timestamp(high_date).date().isoformat()
    details["high_price"] = round(high_price, 4) if pd.notna(high_price) else ""

    # ---- 3. Closes from the high date to today --------------------------
    close_series = hist["Close"]
    if isinstance(close_series, pd.DataFrame):
        close_series = close_series.squeeze("columns")

    closes = close_series.loc[close_series.index >= high_date].dropna()

    # Sheet fallback: if the slice is empty, use the last ~10 days of closes
    if closes.empty:
        closes = close_series.dropna().tail(10)

    count_rows = len(closes)
    details["data_points"] = count_rows

    if count_rows < 10:
        return "Short History", details

    # ---- 4. Cumulative (expanding) average ------------------------------
    cum_avg = closes.expanding().mean()

    # ---- 5. Last 10 cumulative averages, newest first -------------------
    last_10 = cum_avg.tail(10).iloc[::-1].tolist()
    most_recent = last_10[0]
    previous_9 = last_10[1:]

    details["latest_cum_avg"] = round(most_recent, 4)
    details["prev_9_cum_avgs"] = [round(v, 4) for v in previous_9]

    # ---- 6. Is the newest cumulative average above all 9 prior ones? ----
    all_higher = all(most_recent > v for v in previous_9)
    return ("Buy/Average Out" if all_higher else "Avoid/Hold"), details


def analyze_many(tickers: List[str]) -> pd.DataFrame:
    rows = []
    for t in tickers:
        t = t.strip().upper()
        if not t:
            continue
        signal, details = analyze_stock(t)
        rows.append(
            {
                "Ticker": t,
                "Signal": signal,
                "High Date": details.get("high_date", ""),
                "High Price": details.get("high_price", ""),
                "Data Points": details.get("data_points", ""),
                "Latest Cum Avg": details.get("latest_cum_avg", ""),
            }
        )
    return pd.DataFrame(rows)


def load_tickers_from_file(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze stocks with a cumulative-average trend check."
    )
    parser.add_argument(
        "tickers",
        nargs="*",
        help="Ticker symbols, e.g. AAPL MSFT GOOG",
    )
    parser.add_argument(
        "--file",
        help="Path to a text file with one ticker per line.",
    )
    parser.add_argument(
        "--csv",
        help="Optional path to write results as CSV.",
    )
    args = parser.parse_args()

    tickers: List[str] = []
    for raw in args.tickers:
        # Support "AAPL,MSFT,GOOG" as well as space-separated
        tickers.extend(part for part in raw.replace(",", " ").split() if part)
    if args.file:
        tickers.extend(load_tickers_from_file(args.file))

    if not tickers:
        parser.print_help()
        sys.exit(1)

    df = analyze_many(tickers)

    # Pretty console output
    with pd.option_context(
        "display.max_rows", None,
        "display.max_columns", None,
        "display.width", 120,
    ):
        print(df.to_string(index=False))

    if args.csv:
        df.to_csv(args.csv, index=False)
        print(f"\nSaved results to {args.csv}")


if __name__ == "__main__":
    main()