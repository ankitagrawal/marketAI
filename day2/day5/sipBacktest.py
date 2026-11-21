"""
Adaptive-SIP backtest engine (pure logic, no UI).

Strategy (mirrors Sequence.xlsx):
  * Day 0 of a cycle: invest `base` (₹1 lakh).
  * Every month after, SIP amount = base * (1 - mult * gain%/100), where gain% is the
    current gain/loss of the open position vs its average price.
        loss of 4%  -> base * (1 + 4*0.04) = 1.16 lakh      (mult = 4)
        gain of 3%  -> base * (1 - 4*0.03) = 0.88 lakh
  * The moment gain% >= target (6.28 in the sheet) the whole position is sold at that
    day's close and a fresh cycle starts with `base` on the NEXT trading day.
"""

from __future__ import annotations

from dataclasses import dataclass

import threading

import numpy as np
import pandas as pd
import yfinance as yf


@dataclass
class Params:
    base: float = 100_000.0
    mult: float = 4.0            # sensitivity to gain/loss
    target: float = 6.28         # % gain at which the cycle is closed
    min_sip: float = 0.0         # floor for a SIP (gains can shrink it, never negative)
    max_sip_x: float = 0.0       # cap as multiple of base (0 = no cap)


_DL_LOCK = threading.Lock()   # yf.download shares global state; parallel calls mix up tickers


# ── Data ─────────────────────────────────────────────────────────────────────
def to_yf_symbol(sym: str) -> str:
    s = sym.strip().upper()
    if not s:
        return s
    if s.startswith("^") or "." in s or "=" in s:
        return s
    return s + ".NS"


def fetch_prices(symbol: str, years: int) -> pd.Series:
    """Daily close series (price return, split-adjusted) for the last `years` years."""
    start = pd.Timestamp.today().normalize() - pd.DateOffset(years=years)
    with _DL_LOCK:
        df = yf.download(symbol, start=start, interval="1d", auto_adjust=False, progress=False, threads=False)
    if df is None or df.empty:
        return pd.Series(dtype=float)
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = close.dropna()
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close[~close.index.duplicated()]


# ── Core cycle ───────────────────────────────────────────────────────────────
def sip_amount(gain_pct: float, p: Params) -> float:
    amt = p.base * (1 - p.mult * gain_pct / 100.0)
    amt = max(amt, p.min_sip)
    if p.max_sip_x > 0:
        amt = min(amt, p.base * p.max_sip_x)
    return amt


def run_cycle(dates, prices, start_idx: int, p: Params) -> dict:
    """Run one cycle from start_idx until target hit or data ends."""
    start_date = dates[start_idx]
    qty = p.base / prices[start_idx]
    invested = p.base
    buys = [(dates[start_idx], prices[start_idx], p.base)]
    k = 1
    next_sip = start_date + pd.DateOffset(months=k)
    worst_gain = 0.0
    worst_pnl = 0.0
    peak_invested = invested
    n = len(prices)

    for i in range(start_idx + 1, n):
        px = prices[i]
        value = qty * px
        gain = (value / invested - 1) * 100
        worst_gain = min(worst_gain, gain)
        worst_pnl = min(worst_pnl, value - invested)

        if gain >= p.target:
            return dict(start=start_date, end=dates[i], days=(dates[i] - start_date).days,
                        invested=invested, proceeds=value, profit=value - invested,
                        ret_pct=gain, sips=len(buys), peak_invested=peak_invested,
                        worst_gain_pct=worst_gain, worst_pnl=worst_pnl,
                        status="Target hit", buys=buys, sell=(dates[i], px, value), end_idx=i)

        if dates[i] >= next_sip:
            amt = sip_amount(gain, p)
            if amt > 0:
                qty += amt / px
                invested += amt
                buys.append((dates[i], px, amt))
                peak_invested = invested
            k += 1
            next_sip = start_date + pd.DateOffset(months=k)
            # data gap safety: skip over any months already passed
            while next_sip <= dates[i]:
                k += 1
                next_sip = start_date + pd.DateOffset(months=k)

    px = prices[-1]
    value = qty * px
    gain = (value / invested - 1) * 100
    worst_gain = min(worst_gain, gain)
    worst_pnl = min(worst_pnl, value - invested)
    return dict(start=start_date, end=dates[-1], days=(dates[-1] - start_date).days,
                invested=invested, proceeds=value, profit=value - invested, ret_pct=gain,
                sips=len(buys), peak_invested=peak_invested, worst_gain_pct=worst_gain,
                worst_pnl=worst_pnl, status="Open", buys=buys, sell=None, end_idx=n - 1)


# ── Sequential backtest: cycle after cycle ───────────────────────────────────
def xirr(flows: list[tuple[pd.Timestamp, float]]) -> float | None:
    if len(flows) < 2:
        return None
    t0 = flows[0][0]
    ts = np.array([(d - t0).days / 365.0 for d, _ in flows])
    cf = np.array([a for _, a in flows])
    if not (cf < 0).any() or not (cf > 0).any():
        return None

    def npv(r):
        return np.sum(cf / (1 + r) ** ts)

    lo, hi = -0.99, 100.0
    try:
        if npv(lo) * npv(hi) > 0:
            return None
        for _ in range(200):
            mid = (lo + hi) / 2
            if npv(lo) * npv(mid) <= 0:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2
    except Exception:
        return None


def backtest(prices: pd.Series, p: Params) -> dict:
    dates = list(prices.index)
    px = prices.to_numpy(dtype=float)
    cycles, flows = [], []
    idx = 0
    while idx < len(px) - 1:
        c = run_cycle(dates, px, idx, p)
        cycles.append(c)
        for d, _, amt in c["buys"]:
            flows.append((d, -amt))
        flows.append((c["end"], c["proceeds"]))   # open cycle is marked-to-market
        if c["status"] == "Open":
            break
        idx = c["end_idx"] + 1                    # restart next trading day

    df = pd.DataFrame([{k: v for k, v in c.items() if k not in ("buys", "sell", "end_idx")}
                       for c in cycles])
    closed = df[df["status"] == "Target hit"] if not df.empty else df
    open_c = df[df["status"] == "Open"] if not df.empty else df

    total_invested = sum(-a for _, a in flows if a < 0)
    total_profit = df["profit"].sum() if not df.empty else 0.0
    summary = dict(
        cycles=len(df),
        closed=len(closed),
        open=len(open_c),
        win_rate=(len(closed) / len(df) * 100) if len(df) else 0.0,
        realised_profit=closed["profit"].sum() if len(closed) else 0.0,
        open_pnl=open_c["profit"].sum() if len(open_c) else 0.0,
        total_profit=total_profit,
        total_invested=total_invested,
        avg_days=closed["days"].mean() if len(closed) else np.nan,
        median_days=closed["days"].median() if len(closed) else np.nan,
        max_days=closed["days"].max() if len(closed) else np.nan,
        max_peak_capital=df["peak_invested"].max() if not df.empty else 0.0,
        worst_drawdown_pct=df["worst_gain_pct"].min() if not df.empty else 0.0,
        worst_pnl=df["worst_pnl"].min() if not df.empty else 0.0,
        xirr_pct=(lambda r: r * 100 if r is not None else np.nan)(xirr(sorted(flows, key=lambda x: x[0]))),
    )
    return dict(cycles=df, summary=summary, raw=cycles)


# ── Rolling-start scan: "if I had begun in month X, would it have worked?" ───
def rolling_scan(prices: pd.Series, p: Params) -> pd.DataFrame:
    dates = list(prices.index)
    px = prices.to_numpy(dtype=float)
    s = pd.Series(range(len(dates)), index=prices.index)
    first_of_month = s.groupby([s.index.year, s.index.month]).first().to_numpy()
    rows = []
    for idx in first_of_month:
        if idx >= len(px) - 1:
            continue
        c = run_cycle(dates, px, int(idx), p)
        rows.append({k: v for k, v in c.items() if k not in ("buys", "sell", "end_idx")})
    return pd.DataFrame(rows)


def scan_summary(scan: pd.DataFrame) -> dict:
    if scan.empty:
        return dict(starts=0, hit_rate=0.0, median_days=np.nan, p90_days=np.nan,
                    avg_peak=0.0, worst_gain_pct=0.0)
    hit = scan[scan["status"] == "Target hit"]
    return dict(
        starts=len(scan),
        hit_rate=len(hit) / len(scan) * 100,
        median_days=hit["days"].median() if len(hit) else np.nan,
        p90_days=hit["days"].quantile(0.9) if len(hit) else np.nan,
        avg_peak=scan["peak_invested"].mean(),
        worst_gain_pct=scan["worst_gain_pct"].min(),
    )
