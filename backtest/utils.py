"""Data loading and small shared helpers for the backtester."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

logger = logging.getLogger("backtest")


def setup_logging(level: int = logging.INFO) -> None:
    """Configure a simple console logger for the whole package."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def normalize_ticker(ticker: str) -> str:
    """Ensure an NSE ticker has the .NS suffix expected by yfinance."""
    ticker = ticker.strip().upper()
    if not ticker.endswith((".NS", ".BO")) and "." not in ticker:
        return f"{ticker}.NS"
    return ticker


def download_ohlcv(
    ticker: str,
    start_date: date,
    end_date: date,
    csv_fallback_path: Path | None = None,
) -> pd.DataFrame:
    """Download daily OHLCV data via yfinance, falling back to a local CSV on failure.

    Returns a DataFrame indexed by Date with columns Open, High, Low, Close, Volume.
    """
    ticker = normalize_ticker(ticker)
    df: pd.DataFrame | None = None

    try:
        import yfinance as yf

        logger.info("Downloading %s from %s to %s via yfinance", ticker, start_date, end_date)
        raw = yf.download(
            ticker,
            start=start_date.isoformat(),
            end=(end_date + timedelta(days=1)).isoformat(),
            progress=False,
            auto_adjust=False,
        )
        if raw is not None and not raw.empty:
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
        else:
            logger.warning("yfinance returned no data for %s", ticker)
    except Exception as exc:  # noqa: BLE001 - any network/library failure should fall back
        logger.warning("yfinance download failed for %s: %s", ticker, exc)

    if df is None or df.empty:
        if csv_fallback_path is None:
            raise RuntimeError(
                f"Could not download data for {ticker} and no csv_fallback_path was provided."
            )
        df = load_csv(csv_fallback_path)

    df = df.sort_index()
    df.index = pd.to_datetime(df.index).normalize()
    mask = (df.index.date >= start_date) & (df.index.date <= end_date)
    df = df.loc[mask]

    if df.empty:
        raise RuntimeError(f"No OHLCV rows found for {ticker} in range {start_date} to {end_date}")

    return df


def load_csv(path: Path) -> pd.DataFrame:
    """Load OHLCV data from a CSV with a Date column plus Open/High/Low/Close/Volume."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV fallback file not found: {path}")

    logger.info("Loading OHLCV data from CSV: %s", path)
    df = pd.read_csv(path, parse_dates=["Date"])
    df = df.set_index("Date")
    required = {"Open", "High", "Low", "Close", "Volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV {path} is missing required columns: {missing}")
    return df[["Open", "High", "Low", "Close", "Volume"]]


def next_trading_day_on_or_after(index: pd.DatetimeIndex, target: pd.Timestamp) -> pd.Timestamp | None:
    """Find the first date in index that is >= target."""
    candidates = index[index >= target]
    if len(candidates) == 0:
        return None
    return candidates[0]


def first_buy_date_for_month(
    index: pd.DatetimeIndex, year: int, month: int, day_of_month: int
) -> pd.Timestamp | None:
    """Resolve the first trading day on/after day_of_month in the given year/month."""
    target = pd.Timestamp(year=year, month=month, day=day_of_month)
    return next_trading_day_on_or_after(index, target)
