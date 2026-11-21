"""Market data loading (Yahoo Finance via yfinance)."""
import pandas as pd
import yfinance as yf


def parse_symbols(raw: str, suffix: str = ".NS") -> list[str]:
    out = []
    for s in raw.replace("\n", ",").split(","):
        s = s.strip().upper()
        if not s:
            continue
        if suffix and "." not in s and not s.startswith("^"):
            s += suffix
        if s not in out:
            out.append(s)
    return out


def load_ohlc(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame | None:
    df = yf.download(symbol, period=period, interval=interval,
                     auto_adjust=False, progress=False)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()
