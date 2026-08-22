"""
Swing Trade Scorer — Weighted 100-Point System
Derived from chart analysis of PIDILITIND, SOLARINDS, APOLLOHOSP

Instead of all-or-nothing gates (which reject great setups the moment ADX dips
during a pullback or RSI cools off), every factor contributes points. Stocks are
ranked by quality, not killed by a single failed condition.

  Trend             40   (MA stack + slope)
  Momentum          20   (ADX tiers + DI)
  Entry Timing      17   (RSI band + EMA proximity + higher low)
  Trigger           13   (green + close + volume tiers + body; red = penalty)
  Relative Strength 10   (out/under-performance vs Nifty over 3M / 6M)
  ────────────────────
  Base max         100
  Breakout bonus   +10   (near 52w high, above all MAs, big volume) — capped at 100

Rating bands:
  85–100  ⭐⭐⭐⭐⭐  Strong Buy
  75–84   ⭐⭐⭐⭐☆  Buy
  65–74   ⭐⭐⭐☆☆  Watchlist
  50–64   ⭐⭐☆☆☆  Wait
  <50     ⭐☆☆☆☆  Avoid
"""

import os
import sys
from datetime import datetime

import yfinance as yf
import pandas as pd


class Tee:
    """Duplicate stdout to a file so the full scan is saved as it prints."""
    def __init__(self, *streams):
        self.streams = streams
    def write(self, data):
        for s in self.streams:
            s.write(data)
    def flush(self):
        for s in self.streams:
            s.flush()


# Nifty benchmark series for relative-strength scoring (fetched once, lazily)
_NIFTY_CLOSE = None

def _get_nifty_close():
    global _NIFTY_CLOSE
    if _NIFTY_CLOSE is None:
        try:
            b = yf.download("^NSEI", period="1y", interval="1d",
                            auto_adjust=True, progress=False)
            if not b.empty:
                if isinstance(b.columns, pd.MultiIndex):
                    b.columns = [c[0] for c in b.columns]
                _NIFTY_CLOSE = b["Close"].dropna()
            else:
                _NIFTY_CLOSE = pd.Series(dtype=float)
        except Exception:
            _NIFTY_CLOSE = pd.Series(dtype=float)
    return _NIFTY_CLOSE


# ── Data ─────────────────────────────────────────────────────────────────────

def get_ohlcv(symbol, period="1y", interval="1d"):
    df = yf.download(symbol, period=period, interval=interval,
                     auto_adjust=True, progress=False)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


# ── Indicators ────────────────────────────────────────────────────────────────

def ema(close, span):
    return close.ewm(span=span, adjust=False).mean()

def sma(close, window):
    return close.rolling(window=window).mean()

def rsi(close, period=14):
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    ag    = gain.ewm(alpha=1/period, adjust=False).mean()
    al    = loss.ewm(alpha=1/period, adjust=False).mean()
    return 100 - (100 / (1 + ag / al))

def adx(df, period=14):
    hi, lo, cl = df["High"], df["Low"], df["Close"]
    pdm = hi.diff().clip(lower=0)
    ndm = (-lo.diff()).clip(lower=0)
    pdm = pdm.where(pdm > ndm, 0.0)
    ndm = ndm.where(ndm > pdm, 0.0)
    tr  = pd.concat([hi - lo, (hi - cl.shift()).abs(),
                     (lo - cl.shift()).abs()], axis=1).max(axis=1)
    atr_  = tr.ewm(alpha=1/period, adjust=False).mean()
    pdi   = 100 * pdm.ewm(alpha=1/period, adjust=False).mean() / atr_
    ndi   = 100 * ndm.ewm(alpha=1/period, adjust=False).mean() / atr_
    dx    = (abs(pdi - ndi) / (pdi + ndi)) * 100
    return dx.ewm(alpha=1/period, adjust=False).mean(), pdi, ndi

def atr(df, period=14):
    hi, lo, cl = df["High"], df["Low"], df["Close"]
    tr = pd.concat([hi - lo, (hi - cl.shift()).abs(),
                    (lo - cl.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()


# ── Value Scoring ─────────────────────────────────────────────────────────────

def get_value_score(symbol, current_price):
    """
    Returns a value dict with P/E, 52w position, weekly RSI, and a 0-4 score.
    Higher score = more attractive value.
    """
    result = {
        "pe":               None,
        "pe_verdict":       "N/A",
        "week52_low":       None,
        "week52_high":      None,
        "pct_from_52w_low": None,
        "week52_position":  None,   # 0–100%, where in the 52w range
        "weekly_rsi":       None,
        "weekly_rsi_verdict": "N/A",
        "dist_from_200ma_pct": None,
        "value_score":      0,
        "value_label":      "N/A",
    }

    try:
        info = yf.Ticker(symbol).info

        # P/E ratio
        pe = info.get("trailingPE") or info.get("forwardPE")
        if pe and pe > 0:
            result["pe"] = round(pe, 1)
            # Sector-agnostic: under 25 = value, 25-40 = fair, above 40 = expensive
            if pe < 25:
                result["pe_verdict"] = "CHEAP"
            elif pe <= 40:
                result["pe_verdict"] = "FAIR"
            else:
                result["pe_verdict"] = "EXPENSIVE"

        # 52-week range position
        low52  = info.get("fiftyTwoWeekLow")
        high52 = info.get("fiftyTwoWeekHigh")
        if low52 and high52 and high52 > low52:
            result["week52_low"]  = round(low52, 2)
            result["week52_high"] = round(high52, 2)
            pos = (current_price - low52) / (high52 - low52) * 100
            result["week52_position"]  = round(pos, 1)
            result["pct_from_52w_low"] = round((current_price - low52) / low52 * 100, 1)

    except Exception:
        pass

    # Weekly RSI from 2 years of weekly data
    try:
        df_w = yf.download(symbol, period="2y", interval="1wk",
                           auto_adjust=True, progress=False)
        if not df_w.empty:
            if isinstance(df_w.columns, pd.MultiIndex):
                df_w.columns = [col[0] for col in df_w.columns]
            w_rsi = rsi(df_w["Close"].dropna())
            val = float(w_rsi.dropna().iloc[-1])
            result["weekly_rsi"] = round(val, 1)
            if val < 45:
                result["weekly_rsi_verdict"] = "OVERSOLD (value zone)"
            elif val <= 60:
                result["weekly_rsi_verdict"] = "NEUTRAL (healthy)"
            else:
                result["weekly_rsi_verdict"] = "OVERBOUGHT (expensive)"
    except Exception:
        pass

    # Compute value score 0–4
    score = 0
    if result["pe"] and result["pe"] < 35:
        score += 1
    if result["week52_position"] is not None and result["week52_position"] < 60:
        score += 1
    if result["weekly_rsi"] and result["weekly_rsi"] < 55:
        score += 1
    if result["pct_from_52w_low"] is not None and result["pct_from_52w_low"] < 30:
        score += 1

    result["value_score"] = score
    if score >= 3:
        result["value_label"] = "GOOD VALUE ✅"
    elif score == 2:
        result["value_label"] = "FAIR VALUE 🟡"
    else:
        result["value_label"] = "OVERVALUED ❌"

    return result


# ── 4-Gate Evaluation ─────────────────────────────────────────────────────────

def evaluate_gates(df):
    close  = df["Close"]
    volume = df["Volume"]

    e5     = ema(close, 5)
    e20    = ema(close, 20)
    m44    = sma(close, 44)
    m200   = sma(close, 200)
    r      = rsi(close)
    adx_v, pdi, ndi = adx(df)
    atr_v  = atr(df)
    vol20  = volume.rolling(20).mean()

    p      = float(close.iloc[-1])
    o      = float(df["Open"].iloc[-1])
    hi_c   = float(df["High"].iloc[-1])
    lo_c   = float(df["Low"].iloc[-1])
    vol    = int(volume.iloc[-1])

    # Higher low check: last low > low 5 bars ago
    recent_lows    = df["Low"].iloc[-6:-1]
    higher_low     = float(df["Low"].iloc[-1]) > float(recent_lows.min())

    # Candle body strength: body > 50% of total range
    candle_range   = hi_c - lo_c
    candle_body    = abs(p - o)
    strong_candle  = (candle_body / candle_range > 0.5) if candle_range > 0 else False

    # Distance from 20 EMA
    pct_from_e20   = (p - float(e20.iloc[-1])) / float(e20.iloc[-1]) * 100

    ma44_rising = float(m44.iloc[-1]) > float(m44.iloc[-5])  # rising if today > 5 bars ago

    latest = {
        "price":         round(p, 2),
        "ema5":          round(float(e5.iloc[-1]), 2),
        "ema20":         round(float(e20.iloc[-1]), 2),
        "ma44":          round(float(m44.iloc[-1]), 2),
        "ma200":         round(float(m200.iloc[-1]), 2),
        "ma44_rising":   ma44_rising,
        "rsi":           round(float(r.iloc[-1]), 2),
        "adx":           round(float(adx_v.iloc[-1]), 2),
        "plus_di":       round(float(pdi.iloc[-1]), 2),
        "minus_di":      round(float(ndi.iloc[-1]), 2),
        "atr":           round(float(atr_v.iloc[-1]), 2),
        "volume":        vol,
        "vol_ma20":      int(vol20.iloc[-1]),
        "pct_from_e20":  round(pct_from_e20, 2),
    }

    latest["higher_low"]    = higher_low
    latest["strong_candle"] = strong_candle
    latest["green_candle"]  = p > o

    return latest


# ── Weighted Scoring ──────────────────────────────────────────────────────────
# Each category returns (points_earned, max_points, list_of_(label, earned, note)).

def score_trend(l):
    """Trend — 40 pts. MA stack + 44 DMA slope."""
    items = []
    pts = 0
    if l["price"] > l["ma200"]:
        pts += 10; items.append(("Price > 200 DMA", 10, ""))
    else:
        items.append(("Price > 200 DMA", 0, f"below 200 DMA ₹{l['ma200']}"))
    if l["ema20"] > l["ma200"]:
        pts += 10; items.append(("20 EMA > 200 DMA", 10, ""))
    else:
        items.append(("20 EMA > 200 DMA", 0, "20 EMA still under 200 DMA"))
    if l["ema5"] > l["ema20"]:
        pts += 8; items.append(("5 EMA > 20 EMA", 8, ""))
    else:
        items.append(("5 EMA > 20 EMA", 0, "short-term momentum soft"))
    if l["price"] > l["ma44"]:
        pts += 6; items.append(("Price > 44 DMA", 6, ""))
    else:
        items.append(("Price > 44 DMA", 0, f"below 44 DMA ₹{l['ma44']}"))
    if l["ma44_rising"]:
        pts += 6; items.append(("44 DMA rising", 6, ""))
    else:
        items.append(("44 DMA rising", 0, "44 DMA flat/falling"))
    return pts, 40, items


def score_momentum(l):
    """Momentum — 20 pts. ADX tiers + DI direction."""
    items = []
    pts = 0
    adx = l["adx"]
    if adx > 30:
        pts += 10; items.append((f"ADX {adx} (>30 excellent)", 10, ""))
    elif adx >= 22:
        pts += 7;  items.append((f"ADX {adx} (22–30 good)", 7, ""))
    elif adx >= 18:
        pts += 4;  items.append((f"ADX {adx} (18–22 acceptable)", 4, ""))
    else:
        items.append((f"ADX {adx} (<18 weak)", 0, "trend not established"))
    if l["plus_di"] > l["minus_di"]:
        pts += 10; items.append(("DI+ > DI-", 10, ""))
    else:
        items.append(("DI+ > DI-", 0, f"DI- leads ({l['minus_di']} > {l['plus_di']})"))
    return pts, 20, items


def score_timing(l):
    """Entry timing — 17 pts. RSI band + EMA proximity + higher low."""
    items = []
    pts = 0
    rsi_v = l["rsi"]
    if 48 <= rsi_v <= 68:
        pts += 8; items.append((f"RSI {rsi_v} (48–68 zone)", 8, ""))
    else:
        note = "overbought" if rsi_v > 68 else "momentum too weak"
        items.append((f"RSI {rsi_v}", 0, note))
    pe = l["pct_from_e20"]
    if -2.0 <= pe <= 5.0:
        pts += 5; items.append((f"Within -2% to +5% of 20 EMA ({pe}%)", 5, ""))
    else:
        note = "extended above 20 EMA" if pe > 5 else "below pullback zone"
        items.append((f"Near 20 EMA ({pe}%)", 0, note))
    if l["higher_low"]:
        pts += 4; items.append(("Higher low intact", 4, ""))
    else:
        items.append(("Higher low intact", 0, "structure still weak"))
    return pts, 17, items


def score_trigger(l):
    """Trigger — 13 pts. Green(or red penalty) + close + volume tiers + body."""
    items = []
    pts = 0
    if l["green_candle"]:
        pts += 3; items.append(("Green candle", 3, ""))
    else:
        pts -= 2; items.append(("Green candle", -2, "red day (penalty, trend may resume)"))
    if l["price"] > l["ema20"]:
        pts += 3; items.append(("Close > 20 EMA", 3, ""))
    else:
        items.append(("Close > 20 EMA", 0, f"below 20 EMA ₹{l['ema20']}"))
    vr = l["volume"] / l["vol_ma20"] if l["vol_ma20"] else 0
    if vr >= 2.0:
        pts += 5; items.append((f"Volume {vr:.1f}× avg (≥2×)", 5, ""))
    elif vr >= 1.5:
        pts += 4; items.append((f"Volume {vr:.1f}× avg (≥1.5×)", 4, ""))
    elif vr >= 1.0:
        pts += 2; items.append((f"Volume {vr:.1f}× avg (≥1×)", 2, ""))
    else:
        items.append((f"Volume {vr:.1f}× avg", 0, "below average volume"))
    if l["strong_candle"]:
        pts += 2; items.append(("Strong candle body (>50%)", 2, ""))
    else:
        items.append(("Strong candle body (>50%)", 0, "weak/indecisive body"))
    return pts, 13, items


def score_relative_strength(symbol, df):
    """Relative strength — 10 pts. Out/under-performance vs Nifty (3M + 6M)."""
    items = []
    pts = 0
    nifty = _get_nifty_close()
    close = df["Close"]
    if nifty.empty or len(close) < 130:
        items.append(("Relative strength", 0, "benchmark data unavailable"))
        return pts, 10, items

    def ret(series, bars):
        if len(series) <= bars:
            return None
        a, b = float(series.iloc[-bars-1]), float(series.iloc[-1])
        return (b - a) / a * 100 if a else None

    # ~63 trading days ≈ 3M, ~126 ≈ 6M
    s3, n3 = ret(close, 63),  ret(nifty, 63)
    s6, n6 = ret(close, 126), ret(nifty, 126)

    if s3 is not None and n3 is not None:
        if s3 > n3:
            pts += 6; items.append((f"3M vs Nifty: {s3:.1f}% vs {n3:.1f}% (outperform)", 6, ""))
        else:
            items.append((f"3M vs Nifty: {s3:.1f}% vs {n3:.1f}% (lag)", 0, ""))
    if s6 is not None and n6 is not None:
        if s6 > n6:
            pts += 4; items.append((f"6M vs Nifty: {s6:.1f}% vs {n6:.1f}% (outperform)", 4, ""))
        else:
            items.append((f"6M vs Nifty: {s6:.1f}% vs {n6:.1f}% (lag)", 0, ""))
    return pts, 10, items


def score_breakout_bonus(symbol, l, value):
    """Breakout bonus — up to +10. Near 52w high + above all MAs + big volume."""
    items = []
    pts = 0
    pos = value.get("week52_position")
    above_all = (l["price"] > l["ma200"] and l["price"] > l["ma44"] and
                 l["price"] > l["ema20"] and l["ema5"] > l["ema20"])
    vr = l["volume"] / l["vol_ma20"] if l["vol_ma20"] else 0
    near_high = pos is not None and pos >= 98  # within 2% of 52w high
    if near_high and above_all and vr >= 1.5:
        pts += 10
        items.append((f"Breakout: {pos}% of 52w range, above all MAs, {vr:.1f}× vol", 10, ""))
    return pts, 10, items


def rating_for(score):
    if score >= 85: return "⭐⭐⭐⭐⭐ Strong Buy"
    if score >= 75: return "⭐⭐⭐⭐☆ Buy"
    if score >= 65: return "⭐⭐⭐☆☆ Watchlist"
    if score >= 50: return "⭐⭐☆☆☆ Wait"
    return "⭐☆☆☆☆ Avoid"


def next_action(l, breakdown):
    """Single most-impactful next step, based on the biggest points left on the table."""
    # Find category with largest earned/max gap and surface its first missed item.
    worst = None
    for cat, (pts, mx, items) in breakdown.items():
        gap = mx - pts
        misses = [it for it in items if it[1] <= 0]
        if misses and (worst is None or gap > worst[0]):
            worst = (gap, cat, misses[0])
    if worst is None:
        return "✅ Firing on all cylinders — everything scoring."
    _, cat, (label, _, note) = worst
    tail = f" — {note}" if note else ""
    return f"Biggest gap: {cat} → {label}{tail}"


def stop_and_target(df, latest):
    lo_c = float(df["Low"].iloc[-1])
    stop = round(lo_c - 0.5 * latest["atr"], 2)
    risk = latest["price"] - stop

    # Target 1 = previous swing high (last 20 bars)
    swing_high = round(float(df["High"].iloc[-21:-1].max()), 2)
    t1 = swing_high if swing_high > latest["price"] else round(latest["price"] + 2 * risk, 2)
    t2 = round(latest["price"] + 3 * risk, 2)
    rr = round((t1 - latest["price"]) / risk, 2) if risk > 0 else 0

    return {
        "stop_loss":  stop,
        "target_1":   t1,
        "target_2":   t2,
        "risk_points": round(risk, 2),
        "rr_ratio":   rr,
    }


# ── Full Analysis ─────────────────────────────────────────────────────────────

def analyze_stock(symbol):
    df = get_ohlcv(symbol)
    if df is None or len(df) < 210:
        return {"symbol": symbol, "error": "Insufficient data (need 210+ days)"}

    try:
        latest = evaluate_gates(df)
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

    value = get_value_score(symbol, latest["price"])

    breakdown = {
        "Trend":     score_trend(latest),
        "Momentum":  score_momentum(latest),
        "Timing":    score_timing(latest),
        "Trigger":   score_trigger(latest),
        "RelStr":    score_relative_strength(symbol, df),
    }
    bonus_pts, bonus_max, bonus_items = score_breakout_bonus(symbol, latest, value)

    base   = sum(pts for pts, _, _ in breakdown.values())
    total  = max(0, min(100, base + bonus_pts))  # bonus can lift, floor at 0, cap at 100
    rating = rating_for(total)

    # Trade plan only meaningful when trend is broadly in place (>=70% of trend pts)
    trend_pts = breakdown["Trend"][0]
    trade = stop_and_target(df, latest) if trend_pts >= 28 else None

    return {
        "symbol":     symbol,
        "latest":     latest,
        "breakdown":  breakdown,
        "bonus":      (bonus_pts, bonus_max, bonus_items),
        "score":      total,
        "base_score": base,
        "rating":     rating,
        "buy_signal": total >= 75,
        "trade":      trade,
        "value":      value,
        "next":       next_action(latest, breakdown),
    }


# ── Print Report ──────────────────────────────────────────────────────────────

def print_report(result, verbose=True):
    if "error" in result:
        print(f"  {result['symbol']:<20} ERROR: {result['error']}")
        return

    s  = result["symbol"]
    l  = result["latest"]
    tr = result["trade"]

    sep = "=" * 64

    if verbose:
        print(f"\n{sep}")
        print(f"  {s}   |   Price: ₹{l['price']}   |   Score: {result['score']}/100   {result['rating']}")
        print(sep)

        print(f"\n  Indicators:")
        print(f"    EMA5:  {l['ema5']}    EMA20: {l['ema20']}    MA44: {l['ma44']} ({'rising' if l['ma44_rising'] else 'flat/falling'})    MA200: {l['ma200']}")
        print(f"    RSI:   {l['rsi']}     ADX:   {l['adx']}     ATR:   {l['atr']}")
        print(f"    DI+:   {l['plus_di']}    DI-:   {l['minus_di']}")
        print(f"    Vol:   {l['volume']:,}    AvgVol: {l['vol_ma20']:,}")
        print(f"    % from 20 EMA: {l['pct_from_e20']}%")

        print(f"\n  Score Breakdown:")
        for cat, (pts, mx, items) in result["breakdown"].items():
            print(f"    {cat:<9} {pts:>3}/{mx:<3}")
            for label, earned, note in items:
                mark = "✅" if earned > 0 else ("➖" if earned == 0 else "⚠️ ")
                extra = f"  ({note})" if note else ""
                print(f"        {mark} [{earned:+d}] {label}{extra}")
        bpts, bmx, bitems = result["bonus"]
        if bpts:
            for label, earned, note in bitems:
                print(f"    Bonus     {bpts:>3}/{bmx:<3}")
                print(f"        🚀 [{earned:+d}] {label}")
        print(f"\n    ── Base {result['base_score']}/100" +
              (f"  + Bonus {bpts}  → Total {result['score']}/100" if bpts else f"  → Total {result['score']}/100"))

        print(f"\n  Next Action:")
        print(f"    → {result['next']}")

        # Value section
        v = result["value"]
        print(f"\n  Value Analysis:  {v['value_label']}  (score {v['value_score']}/4)")
        pe_str   = f"P/E: {v['pe']} ({v['pe_verdict']})" if v['pe'] else "P/E: N/A"
        pos_str  = f"52w position: {v['week52_position']}%  (low ₹{v['week52_low']} / high ₹{v['week52_high']})" \
                   if v['week52_position'] is not None else "52w range: N/A"
        wrsi_str = f"Weekly RSI: {v['weekly_rsi']} — {v['weekly_rsi_verdict']}" \
                   if v['weekly_rsi'] else "Weekly RSI: N/A"
        print(f"    {pe_str}")
        print(f"    {pos_str}")
        print(f"    {wrsi_str}")

        if tr:
            print(f"\n  Trade Plan:")
            print(f"    Entry:    ₹{l['price']}")
            print(f"    Stop:     ₹{tr['stop_loss']}  (risk ₹{tr['risk_points']})")
            print(f"    Target 1: ₹{tr['target_1']}  (book 50%)")
            print(f"    Target 2: ₹{tr['target_2']}  (trail 20 EMA)")
            print(f"    R:R Ratio: {tr['rr_ratio']}x")

        print(sep)

    else:
        # One-line summary + next action on second line
        signal = "🚨 BUY " if result["buy_signal"] else "   --  "
        v = result["value"]
        print(f"  {signal} {s:<18} {result['score']:>3}/100 {result['rating']:<18} "
              f"RSI:{l['rsi']:<6} ADX:{l['adx']:<6} Value:{v['value_score']}/4  52w%:{v['week52_position']}")
        print(f"          {'':18} → {result['next']}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # Save the entire run to a timestamped report alongside this script.
    _stamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
    _out_dir  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    os.makedirs(_out_dir, exist_ok=True)
    _out_path = os.path.join(_out_dir, f"swing_scan_{_stamp}.txt")
    _report   = open(_out_path, "w", encoding="utf-8")
    sys.stdout = Tee(sys.__stdout__, _report)

    print(f"  Swing Trade Scan — generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ── Single deep-dive ──────────────────────────────────────────────────────
    print("\n" + "─"*60)
    print("  SINGLE STOCK DEEP ANALYSIS")
    print("─"*60)

    for stock in ["MARUTI.NS", "SOLARINDS.NS", "APOLLOHOSP.NS"]:
        result = analyze_stock(stock)
        print_report(result, verbose=True)

    # ── Full watchlist scan ───────────────────────────────────────────────────
    # watchlist = [
    #     "PIDILITIND.NS", "SOLARINDS.NS", "APOLLOHOSP.NS",
    #     "ASIANPAINT.NS", "HDFCBANK.NS",  "TCS.NS",
    #     "IRCTC.NS",      "DIXON.NS",     "CDSL.NS",
    #     "KOTAKBANK.NS",  "MARUTI.NS",    "SBIN.NS",
    #     "BEL.NS",        "HAL.NS",       "LTFOODS.NS",
    #     "SIEMENS.NS",    "HCLTECH.NS",   "VBL.NS",
    # ]


    watchlist = [
        "BIOCON.NS",
        "HDFCBANK.NS",
        "HCLTECH.NS",
        "TCS.NS",
        "INFY.NS",
        "ICICIBANK.NS",
        "KALYANKJIL.NS",
        "DIVISLAB.NS",
        "SBIN.NS",
        "RELIANCE.NS",
        "BHARTIARTL.NS",
        "ADANIPOWER.NS",
        "AXISBANK.NS",
        "HINDALCO.NS",
        "POLYCAB.NS",
        "BAJAJ-AUTO.NS",
        "ADANIGREEN.NS",
        "SBICARD.NS",
        "BAJFINANCE.NS",
        "MCX.NS",
        "LT.NS",
        "BSE.NS",
        "SHRIRAMFIN.NS",
        "ETERNAL.NS",
        "ADANIENT.NS",
        "UNIONBANK.NS",
        "PAYTM.NS",
        "INDIGO.NS",
        "TECHM.NS",
        "ADANIENSOL.NS",
        "CONCOR.NS",
        "GRASIM.NS",
        "TATASTEEL.NS",
        "KOTAKBANK.NS",
        "M&M.NS",
        "BHEL.NS",
        "LTF.NS",
        "MARUTI.NS",
        "WIPRO.NS",
        "COFORGE.NS",
        "DIXON.NS",
        "HDFCLIFE.NS",
        "PERSISTENT.NS",
        "LAURUSLABS.NS",
        "NATIONALUM.NS",
        "ASHOKLEY.NS",
        "ADANIPORTS.NS",
        "ITC.NS",
        "ABCAPITAL.NS",
        "VBL.NS",
        "HINDUNILVR.NS",
        "TATAELXSI.NS",
        "CHOLAFIN.NS",
        "SWIGGY.NS",
        "JIOFIN.NS",
        "OFSS.NS",
        "TITAN.NS",
        "CANBK.NS",
        "IDFCFIRSTB.NS",
        "TMPV.NS",
        "DRREDDY.NS",
        "LTM.NS",
        "RBLBANK.NS",
        "TORNTPHARM.NS",
        "BANKBARODA.NS",
        "POWERGRID.NS",
        "ONGC.NS",
        "BEL.NS",
        "AMBER.NS",
        "LODHA.NS",
        "NTPC.NS",
        "APOLLOHOSP.NS",
        "HAL.NS",
        "TRENT.NS",
        "HINDPETRO.NS",
        "WAAREEENER.NS",
        "BAJAJFINSV.NS",
        "INDUSTOWER.NS",
        "HEROMOTOCO.NS",
        "KEI.NS",
        "DMART.NS",
        "HDFCAMC.NS",
        "DELHIVERY.NS",
        "IDEA.NS",
        "SUNPHARMA.NS",
        "CDSL.NS",
        "JSWSTEEL.NS",
        "OBEROIRLTY.NS",
        "INDIANB.NS",
        "ULTRACEMCO.NS",
        "POWERINDIA.NS",
        "DLF.NS",
        "FEDERALBNK.NS",
        "MANAPPURAM.NS",
        "ABB.NS",
        "CGPOWER.NS",
        "MUTHOOTFIN.NS",
        "EICHERMOT.NS",
        "TVSMOTOR.NS",
        "AMBUJACEM.NS",
        "COALINDIA.NS",
        "PNB.NS",
        "ANGELONE.NS",
        "AUBANK.NS",
        "RECLTD.NS",
        "PFC.NS",
        "ICICIGI.NS",
        "ASIANPAINT.NS",
        "GLENMARK.NS",
        "GVT&D.NS",
        "GODREJPROP.NS",
        "ASTRAL.NS",
        "PGEL.NS",
        "MOTHERSON.NS",
        "HAVELLS.NS",
        "CIPLA.NS",
        "IOC.NS",
        "ALKEM.NS",
        "BANDHANBNK.NS",
        "VOLTAS.NS",
        "BHARATFORG.NS",
        "ICICIPRULI.NS",
        "OIL.NS",
        "JSWENERGY.NS",
        "PAGEIND.NS",
        "EXIDEIND.NS",
        "LICI.NS",
        "BPCL.NS",
        "AUROPHARMA.NS",
        "BDL.NS",
        "SONACOMS.NS",
        "MPHASIS.NS",
        "LICHSGFIN.NS",
        "NESTLEIND.NS",
        "HYUNDAI.NS",
        "INDUSINDBK.NS",
        "NAUKRI.NS",
        "VEDL.NS",
        "YESBANK.NS",
        "MARICO.NS",
        "PIDILITIND.NS",
        "SUPREMEIND.NS",
        "SBILIFE.NS",
        "CUMMINSIND.NS",
        "MAXHEALTH.NS",
        "PREMIERENE.NS",
        "NMDC.NS",
        "JINDALSTEL.NS",
        "BLUESTARCO.NS",
        "SOLARINDS.NS",
        "MAZDOCK.NS",
        "INDHOTEL.NS",
        "SUZLON.NS",
        "LUPIN.NS",
        "PNBHOUSING.NS",
        "SAIL.NS",
        "KPITTECH.NS",
        "HINDZINC.NS",
        "PATANJALI.NS",
        "BRITANNIA.NS",
        "NYKAA.NS",
        "360ONE.NS",
        "JUBLFOOD.NS",
        "GMRAIRPORT.NS",
        "TATAPOWER.NS",
        "PRESTIGE.NS",
        "PHOENIXLTD.NS",
        "BANKINDIA.NS",
        "SIEMENS.NS",
        "TATACONSUM.NS",
        "SRF.NS",
        "IREDA.NS",
        "UPL.NS",
        "UNITDSPR.NS",
        "NBCC.NS",
        "KFINTECH.NS",
        "MOTILALOFS.NS",
        "DABUR.NS",
        "GAIL.NS",
        "NUVAMA.NS",
        "ZYDUSLIFE.NS",
        "POLICYBZR.NS",
        "DALBHARAT.NS",
        "COCHINSHIP.NS",
        "UNOMINDA.NS",
        "GODREJCP.NS",
        "CROMPTON.NS",
        "RVNL.NS",
        "INOXWIND.NS",
        "RADICO.NS",
        "BOSCHLTD.NS",
        "NHPC.NS",
        "VMM.NS",
        "CAMS.NS",
        "FORTIS.NS",
        "PIIND.NS",
        "APLAPOLLO.NS",
        "TIINDIA.NS",
        "IRFC.NS",
        "SHREECEM.NS",
    ]


    print("\n\n" + "="*64)
    print("  SWING TRADE SCANNER — ALL STOCKS (ranked by score)")
    print("="*64)

    results = []
    for ticker in watchlist:
        r = analyze_stock(ticker)
        if "error" not in r:
            results.append(r)

    # Rank every scanned stock high-to-low so the leaders float to the top.
    results.sort(key=lambda r: r["score"], reverse=True)
    for r in results:
        print_report(r, verbose=False)

    strong = [r for r in results if r["score"] >= 85]
    buy    = [r for r in results if 75 <= r["score"] < 85]
    watch  = [r for r in results if 65 <= r["score"] < 75]

    def _line(r):
        l, v, tr = r["latest"], r["value"], r["trade"]
        rr = tr["rr_ratio"] if tr else "N/A"
        print(f"  {r['symbol']:<18}  {r['score']:>3}/100  Price:₹{l['price']:<9} "
              f"RSI:{l['rsi']:<6} R:R:{rr}x  Value:{v['value_label']}")
        print(f"  {'':18}  → {r['next']}")

    if strong:
        print("\n\n🚨 STRONG BUY (score ≥ 85):")
        print("─"*64)
        for r in strong: _line(r)

    if buy:
        print("\n\n✅ BUY (score 75–84):")
        print("─"*64)
        for r in buy: _line(r)

    if watch:
        print("\n\n👀 WATCHLIST (score 65–74 — entry near):")
        print("─"*64)
        for r in watch: _line(r)

    # Best combined picks: score >= 65 AND value_score >= 2
    print("\n\n⭐ VALUE + SWING COMBINED PICKS (Score≥65 AND Value≥2):")
    print("─"*64)
    combined = [r for r in results if r["score"] >= 65 and r["value"]["value_score"] >= 2]
    if combined:
        combined.sort(key=lambda r: (r["score"] + r["value"]["value_score"] * 5), reverse=True)
        for r in combined:
            l, v = r["latest"], r["value"]
            print(f"  {r['symbol']:<18}  Score:{r['score']}/100 {r['rating']}  Value:{v['value_score']}/4  "
                  f"P/E:{v['pe']}  52w%:{v['week52_position']}  WeeklyRSI:{v['weekly_rsi']}")
            print(f"  {'':18}  → {r['next']}")
            print()
    else:
        print("  No combined picks today — check back tomorrow.")

    if not (strong or buy or watch):
        print("\n  No stocks scored ≥ 65 today. Top 5 by score:")
        for r in results[:5]:
            print(f"    {r['symbol']:<18} {r['score']}/100  {r['rating']}")

    # Restore stdout and close the report file.
    sys.stdout = sys.__stdout__
    _report.close()
    print(f"\n✅ Report saved to: {_out_path}")
