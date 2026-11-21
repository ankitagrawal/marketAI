"""
Candlestick pattern engine, implementing the rules from the EIFS "Charting"
course notes: reversal patterns (Umbrella/Hammer/Hanging Man, Engulfing,
Piercing, Dark Cloud, Harami, Morning/Evening Star, Shooting Star, Inverted
Hammer) and continuation patterns (Rising/Falling Three Methods).

Conventions (from the report): "white" candle = close > open (bullish),
"black" candle = close < open (bearish). A pattern is stamped on the date of
its LAST candle. Reversal patterns require a preceding trend.
"""

from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd


@dataclass
class Params:
    trend_lookback: int = 5        # bars used to judge the prior trend
    trend_min_move: float = 0.01   # >=1% net move over the lookback = trend
    shadow_ratio: float = 2.0      # umbrella / star shadow >= 2x body
    short_shadow: float = 0.10     # "absent or very short" shadow, as % of range
    long_body_mult: float = 1.0    # long body >= mult * average body
    small_body_mult: float = 0.5   # small body <= mult * average body
    doji_ratio: float = 0.10       # doji: body <= 10% of range
    penetration: float = 0.50      # piercing / dark cloud >= 50% of prior body
    rr_target: float = 2.0         # reward:risk used for the suggested target


BULL, BEAR = "Bullish", "Bearish"


def _prep(df: pd.DataFrame, p: Params) -> pd.DataFrame:
    d = df[["Open", "High", "Low", "Close"]].copy()
    d.columns = ["o", "h", "l", "c"]
    d["body"] = (d.c - d.o).abs()
    d["rng"] = d.h - d.l
    d["upper"] = d.h - d[["o", "c"]].max(axis=1)
    d["lower"] = d[["o", "c"]].min(axis=1) - d.l
    d["avg_body"] = d.body.rolling(10, min_periods=3).mean().shift(1)
    d["white"] = d.c > d.o
    d["black"] = d.c < d.o
    d["doji"] = (d.rng > 0) & (d.body <= p.doji_ratio * d.rng)
    return d


def _trend(d: pd.DataFrame, end: int, p: Params) -> str:
    """Trend ending at bar `end` (inclusive): 'up', 'down' or 'flat'."""
    start = end - p.trend_lookback
    if start < 0:
        return "flat"
    move = d.c.iloc[end] / d.c.iloc[start] - 1
    if move >= p.trend_min_move:
        return "up"
    if move <= -p.trend_min_move:
        return "down"
    return "flat"


def _is_long(d, i, p):
    ab = d.avg_body.iloc[i]
    return pd.notna(ab) and d.body.iloc[i] >= p.long_body_mult * ab


def _is_small(d, i, p):
    ab = d.avg_body.iloc[i]
    return pd.notna(ab) and d.body.iloc[i] <= p.small_body_mult * ab


def _hit(d, i, name, bias, kind, stop, note, bars=1, needs_confirm=False,
         confirm_rule=""):
    return dict(
        idx=i, date=d.index[i], pattern=name, bias=bias, kind=kind,
        stop=float(stop), bars=bars, needs_confirm=needs_confirm,
        confirm_rule=confirm_rule, note=note,
    )


def _umbrella_like(d, i, p):
    """Shape tests shared by Hammer / Hanging Man (long lower shadow)."""
    if d.rng.iloc[i] <= 0:
        return False
    body = max(d.body.iloc[i], 1e-9)
    return d.lower.iloc[i] >= p.shadow_ratio * body and \
        d.upper.iloc[i] <= p.short_shadow * d.rng.iloc[i]


def _star_like(d, i, p):
    """Shape tests shared by Shooting Star / Inverted Hammer (long upper shadow)."""
    if d.rng.iloc[i] <= 0:
        return False
    body = max(d.body.iloc[i], 1e-9)
    return d.upper.iloc[i] >= p.shadow_ratio * body and \
        d.lower.iloc[i] <= p.short_shadow * d.rng.iloc[i]


def detect_patterns(df: pd.DataFrame, params: Params | None = None) -> pd.DataFrame:
    """Scan an OHLC frame; return one row per detected pattern."""
    p = params or Params()
    d = _prep(df, p)
    n = len(d)
    out = []

    for i in range(p.trend_lookback + 1, n):
        # ---------------- single-candle ----------------
        tr = _trend(d, i - 1, p)  # trend going INTO candle i
        if _umbrella_like(d, i, p):
            if tr == "down":
                out.append(_hit(d, i, "Hammer", BULL, "reversal", d.l.iloc[i],
                                "Umbrella after a downtrend. Buy once the hammer completes; "
                                "white body is slightly more bullish."))
            elif tr == "up":
                out.append(_hit(d, i, "Hanging Man", BEAR, "reversal", d.h.iloc[i],
                                "Umbrella after an uptrend: a warning. Act only on confirmation.",
                                needs_confirm=True,
                                confirm_rule="Next close below the hanging man's close"))
        if _star_like(d, i, p):
            if tr == "up":
                out.append(_hit(d, i, "Shooting Star", BEAR, "reversal", d.h.iloc[i],
                                "Warning signal after an uptrend; look for other bearish "
                                "patterns before exiting longs / shorting."))
            elif tr == "down":
                out.append(_hit(d, i, "Inverted Hammer", BULL, "reversal", d.l.iloc[i],
                                "Possible short-covering rally. Needs confirmation.",
                                needs_confirm=True,
                                confirm_rule="Next close above the inverted hammer's close"))

        # ---------------- two-candle ----------------
        a, b = i - 1, i
        tr2 = _trend(d, a - 0, p)   # trend into the first candle's close
        pa_body_hi, pa_body_lo = max(d.o.iloc[a], d.c.iloc[a]), min(d.o.iloc[a], d.c.iloc[a])
        pb_body_hi, pb_body_lo = max(d.o.iloc[b], d.c.iloc[b]), min(d.o.iloc[b], d.c.iloc[b])
        a_mid = (d.o.iloc[a] + d.c.iloc[a]) / 2
        trend_before_a = _trend(d, a - 1, p)

        # Engulfing
        if trend_before_a == "down" and (d.black.iloc[a] or d.doji.iloc[a]) and d.white.iloc[b] \
                and d.o.iloc[b] <= d.c.iloc[a] and d.c.iloc[b] >= d.o.iloc[a] \
                and d.body.iloc[b] > d.body.iloc[a]:
            out.append(_hit(d, b, "Bullish Engulfing", BULL, "reversal", d.l.iloc[b],
                            "White body engulfs prior black body after a downtrend. "
                            "If the white candle is very long, wait for a pullback.", bars=2))
        if trend_before_a == "up" and (d.white.iloc[a] or d.doji.iloc[a]) and d.black.iloc[b] \
                and d.o.iloc[b] >= d.c.iloc[a] and d.c.iloc[b] <= d.o.iloc[a] \
                and d.body.iloc[b] > d.body.iloc[a]:
            out.append(_hit(d, b, "Bearish Engulfing", BEAR, "reversal", d.h.iloc[b],
                            "Black body engulfs prior white body after an uptrend.", bars=2))

        # Piercing / Dark Cloud
        if trend_before_a == "down" and d.black.iloc[a] and d.white.iloc[b] and _is_long(d, a, p):
            thresh = d.c.iloc[a] + p.penetration * (d.o.iloc[a] - d.c.iloc[a])
            if d.o.iloc[b] < d.c.iloc[a] and thresh <= d.c.iloc[b] < d.o.iloc[a]:
                out.append(_hit(d, b, "Piercing Pattern", BULL, "reversal", d.l.iloc[b],
                                "White candle closes >=50% into prior black body.", bars=2))
        if trend_before_a == "up" and d.white.iloc[a] and d.black.iloc[b] and _is_long(d, a, p):
            thresh = d.c.iloc[a] - p.penetration * (d.c.iloc[a] - d.o.iloc[a])
            if d.o.iloc[b] > d.c.iloc[a] and d.o.iloc[a] < d.c.iloc[b] <= thresh:
                out.append(_hit(d, b, "Dark Cloud Cover", BEAR, "reversal", d.h.iloc[b],
                                "Black candle closes >=50% into prior white body.", bars=2))

        # Harami (+ cross)
        inside = pb_body_hi <= pa_body_hi and pb_body_lo >= pa_body_lo and d.body.iloc[b] < d.body.iloc[a]
        if inside and _is_long(d, a, p):
            if trend_before_a == "down" and d.black.iloc[a]:
                nm = "Bullish Harami Cross" if d.doji.iloc[b] else "Bullish Harami"
                out.append(_hit(d, b, nm, BULL, "reversal", d.l.iloc[a],
                                "Small body inside a long black body after a downtrend; "
                                "stop at the first candle's low.", bars=2))
            elif trend_before_a == "up" and d.white.iloc[a]:
                nm = "Bearish Harami Cross" if d.doji.iloc[b] else "Bearish Harami"
                out.append(_hit(d, b, nm, BEAR, "reversal", d.h.iloc[a],
                                "Small body inside a long white body after an uptrend.", bars=2))

        # ---------------- three-candle stars ----------------
        if i >= 2:
            s, m, e = i - 2, i - 1, i
            tr_s = _trend(d, s - 1, p)
            m_hi, m_lo = max(d.o.iloc[m], d.c.iloc[m]), min(d.o.iloc[m], d.c.iloc[m])
            s_mid = (d.o.iloc[s] + d.c.iloc[s]) / 2
            if tr_s == "down" and d.black.iloc[s] and _is_long(d, s, p) and _is_small(d, m, p) \
                    and m_hi < d.c.iloc[s] and d.white.iloc[e] and d.c.iloc[e] > s_mid:
                nm = "Morning Doji Star" if d.doji.iloc[m] else "Morning Star"
                out.append(_hit(d, e, nm, BULL, "reversal", d.l.iloc[s:e + 1].min(),
                                "Long black, small star not overlapping, white closing into "
                                "first body. Stop at the low of all three candles.", bars=3))
            if tr_s == "up" and d.white.iloc[s] and _is_long(d, s, p) and _is_small(d, m, p) \
                    and m_lo > d.c.iloc[s] and d.black.iloc[e] and d.c.iloc[e] < s_mid:
                nm = "Evening Doji Star" if d.doji.iloc[m] else "Evening Star"
                out.append(_hit(d, e, nm, BEAR, "reversal", d.h.iloc[s:e + 1].max(),
                                "Long white, small star not overlapping, black closing into "
                                "first body. Stop at the high of all three candles.", bars=3))

        # ---------------- continuation: three methods ----------------
        for k in (3, 2, 4):  # ideal = 3 small bodies; 2-4 acceptable
            f = i - k - 1
            if f < 0:
                continue
            mid = slice(f + 1, i)
            inside_rng = (d.h.iloc[mid] <= d.h.iloc[f]).all() and (d.l.iloc[mid] >= d.l.iloc[f]).all()
            smalls = all(d.body.iloc[j] < d.body.iloc[f] * 0.6 for j in range(f + 1, i))
            if not (inside_rng and smalls and _is_long(d, f, p)):
                continue
            if d.white.iloc[f] and d.white.iloc[i] and _is_long(d, i, p) and d.c.iloc[i] > d.c.iloc[f] \
                    and _trend(d, f - 1, p) == "up":
                out.append(_hit(d, i, "Rising Three Methods", BULL, "continuation", d.l.iloc[f],
                                f"Long white, {k} small candles inside its range, long white "
                                "closing above the first close. Uptrend continues.", bars=k + 2))
                break
            if d.black.iloc[f] and d.black.iloc[i] and _is_long(d, i, p) and d.c.iloc[i] < d.c.iloc[f] \
                    and _trend(d, f - 1, p) == "down":
                out.append(_hit(d, i, "Falling Three Methods", BEAR, "continuation", d.h.iloc[f],
                                f"Long black, {k} small candles inside its range, long black "
                                "closing below the first close. Downtrend continues.", bars=k + 2))
                break

    res = pd.DataFrame(out)
    if res.empty:
        return pd.DataFrame(columns=[
            "date", "pattern", "bias", "kind", "status", "entry", "stop", "risk_pct",
            "target", "bars", "note", "idx", "confirm_rule", "needs_confirm"])

    # --- confirmation status + trade plan ---
    status, entry = [], []
    for _, r in res.iterrows():
        i = int(r.idx)
        e = d.c.iloc[i]
        st = "Complete"
        if r.needs_confirm:
            if i + 1 >= n:
                st = "Awaiting confirmation"
            else:
                nxt = d.c.iloc[i + 1]
                ok = nxt < d.c.iloc[i] if r.bias == BEAR else nxt > d.c.iloc[i]
                st = "Confirmed" if ok else "Not confirmed"
                if ok:
                    e = nxt
        status.append(st)
        entry.append(float(e))
    res["status"], res["entry"] = status, entry
    risk = (res.entry - res.stop).abs()
    sign = np.where(res.bias == BULL, 1, -1)
    res["risk_pct"] = (risk / res.entry * 100).round(2)
    res["target"] = (res.entry + sign * p.rr_target * risk).round(2)
    res["stop"] = res.stop.round(2)
    res["entry"] = res.entry.round(2)
    return res.sort_values("date").reset_index(drop=True)[
        ["date", "pattern", "bias", "kind", "status", "entry", "stop", "risk_pct",
         "target", "bars", "note", "idx", "confirm_rule", "needs_confirm"]]


def market_trend(df: pd.DataFrame, p: Params | None = None) -> str:
    p = p or Params()
    d = _prep(df, p)
    return _trend(d, len(d) - 1, p)


# Strength of each pattern, following the report's emphasis: engulfing, stars and
# three-methods are major; Shooting Star / Inverted Hammer are "warnings only".
WEIGHTS = {
    "Bullish Engulfing": 3, "Bearish Engulfing": 3,
    "Morning Star": 3, "Evening Star": 3, "Morning Doji Star": 3, "Evening Doji Star": 3,
    "Rising Three Methods": 2, "Falling Three Methods": 2,
    "Piercing Pattern": 2, "Dark Cloud Cover": 2, "Hammer": 2, "Hanging Man": 2,
    "Bullish Harami": 1, "Bearish Harami": 1, "Bullish Harami Cross": 1.5, "Bearish Harami Cross": 1.5,
    "Shooting Star": 1, "Inverted Hammer": 1,
}


def rating_from_score(s: float) -> str:
    if s >= 4: return "Strong Buy"
    if s >= 2: return "Buy"
    if s <= -4: return "Strong Sell"
    if s <= -2: return "Sell"
    return "Neutral"


def score_signals(hits: pd.DataFrame, n_bars: int, recent: int = 5) -> dict:
    """Weighted score from patterns in the last `recent` bars.

    weight x recency (newest bar 1.0, fading to 0.5) x confirmation
    (Awaiting = 0.5, Not confirmed = 0). Score maps to Strong Buy / Buy /
    Neutral / Sell / Strong Sell at +-2 and +-4.
    """
    if hits.empty:
        return dict(score=0.0, label="Neutral", rating="Neutral", patterns=[])
    r = hits[hits.idx >= n_bars - recent]
    total, names = 0.0, []
    for _, h in r.iterrows():
        conf = {"Not confirmed": 0.0, "Awaiting confirmation": 0.5}.get(h.status, 1.0)
        if conf == 0:
            continue
        age = n_bars - 1 - int(h.idx)
        rec = 1.0 - 0.5 * age / max(recent - 1, 1)
        total += (1 if h.bias == BULL else -1) * WEIGHTS.get(h.pattern, 1) * rec * conf
        names.append(h.pattern)
    total = round(total, 1)
    return dict(score=total, label="Bullish" if total > 0 else "Bearish" if total < 0 else "Neutral",
                rating=rating_from_score(total), patterns=names)


REFERENCE = [
    ("Hammer", BULL, "1 candle", "Downtrend; lower shadow >= 2x body; no/short upper shadow", "Buy after it completes; stop = hammer low"),
    ("Hanging Man", BEAR, "1 candle", "Uptrend; same shape as hammer", "Needs lower next close; stop = high"),
    ("Shooting Star", BEAR, "1 candle", "Uptrend; upper shadow >= 2x body; ideally gap-up open", "Warning only; wait for other bearish signs"),
    ("Inverted Hammer", BULL, "1 candle", "Downtrend; shooting-star shape", "Needs higher next close"),
    ("Bullish Engulfing", BULL, "2 candles", "Downtrend; white body engulfs prior black/doji body", "Long; stop = engulfing low"),
    ("Bearish Engulfing", BEAR, "2 candles", "Uptrend; black body engulfs prior white/doji body", "Short; stop = engulfing high"),
    ("Piercing Pattern", BULL, "2 candles", "Downtrend; white closes >=50% into prior black body", "Long; stop = piercing candle low"),
    ("Dark Cloud Cover", BEAR, "2 candles", "Uptrend; black closes >=50% into prior white body", "Short; stop = candle high"),
    ("Bullish Harami", BULL, "2 candles", "Downtrend; small body inside long black body (cross variant)", "Long; stop = first candle low"),
    ("Bearish Harami", BEAR, "2 candles", "Uptrend; small body inside long white body (cross variant)", "Short; stop = first candle high"),
    ("Morning Star", BULL, "3 candles", "Downtrend; black, small non-overlapping star, white into first body", "Buy; stop = low of the 3 candles"),
    ("Evening Star", BEAR, "3 candles", "Uptrend; white, small non-overlapping star, black into first body", "Sell; stop = high of the 3 candles"),
    ("Rising Three Methods", BULL, "5 candles", "Long white, 2-4 small candles inside its range, long white closing higher", "Uptrend continuation"),
    ("Falling Three Methods", BEAR, "5 candles", "Long black, 2-4 small candles inside its range, long black closing lower", "Downtrend continuation"),
]
