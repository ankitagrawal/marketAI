"""
Swing Trade Entry System — 4-Gate Framework
Derived from chart analysis of PIDILITIND, SOLARINDS, APOLLOHOSP

Entry sequence every valid swing follows:
  Stage 1: Consolidation/correction  → avoid
  Stage 2: 200 MA reclaim            → prepare/watch
  Stage 3: Pullback to 20 EMA        → ENTRY ZONE
  Stage 4: Trigger candle            → BUY signal

Gates must pass in order. First failure = skip stock.
"""

import yfinance as yf
import pandas as pd


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

    latest = {
        "price":         round(p, 2),
        "ema5":          round(float(e5.iloc[-1]), 2),
        "ema20":         round(float(e20.iloc[-1]), 2),
        "ma200":         round(float(m200.iloc[-1]), 2),
        "rsi":           round(float(r.iloc[-1]), 2),
        "adx":           round(float(adx_v.iloc[-1]), 2),
        "plus_di":       round(float(pdi.iloc[-1]), 2),
        "minus_di":      round(float(ndi.iloc[-1]), 2),
        "atr":           round(float(atr_v.iloc[-1]), 2),
        "volume":        vol,
        "vol_ma20":      int(vol20.iloc[-1]),
        "pct_from_e20":  round(pct_from_e20, 2),
    }

    # ── Gate 1: Trend Gate ────────────────────────────────────────────────────
    # All 3 MAs must be stacked bullishly
    g1 = {
        "price_above_200ma": p > latest["ma200"],
        "ema20_above_200ma": latest["ema20"] > latest["ma200"],
        "ema5_above_ema20":  latest["ema5"]  > latest["ema20"],
    }

    # ── Gate 2: Strength Gate ─────────────────────────────────────────────────
    # Trend must have muscle — ADX and directional movement
    g2 = {
        "adx_above_25":   latest["adx"] > 25,
        "di_plus_leads":  latest["plus_di"] > latest["minus_di"],
    }

    # ── Gate 3: Timing Gate ───────────────────────────────────────────────────
    # Stock must be in pullback, not extended
    g3 = {
        "rsi_entry_zone":    45 <= latest["rsi"] <= 62,
        "price_near_ema20":  -1.0 <= pct_from_e20 <= 3.0,  # at or just above 20 EMA
        "higher_low_intact": higher_low,
    }

    # ── Gate 4: Trigger Gate ──────────────────────────────────────────────────
    # The actual buy candle — green, strong, on volume
    g4 = {
        "green_candle":       p > o,
        "close_above_ema20":  p > latest["ema20"],
        "volume_above_avg":   vol > latest["vol_ma20"],
        "strong_candle_body": strong_candle,
    }

    return latest, g1, g2, g3, g4


def gate_passed(gate_dict):
    return all(gate_dict.values())


def current_stage(g1, g2, g3, g4, latest):
    """Identify which stage of the 4-stage cycle the stock is in."""
    if not gate_passed(g1):
        return "STAGE 1 — Consolidation/Downtrend (Avoid)"
    if gate_passed(g1) and not gate_passed(g2):
        return "STAGE 2 — 200 MA Reclaimed, Trend Weak (Watch)"
    if gate_passed(g1) and gate_passed(g2) and not gate_passed(g3):
        if latest["rsi"] > 62:
            return "STAGE 4 — Momentum Run (Hold if in, else wait)"
        return "STAGE 2/3 — Trend Strong, Waiting for Pullback (Watch)"
    if gate_passed(g1) and gate_passed(g2) and gate_passed(g3) and not gate_passed(g4):
        return "STAGE 3 — In Entry Zone, Waiting for Trigger (Alert)"
    if gate_passed(g1) and gate_passed(g2) and gate_passed(g3) and gate_passed(g4):
        return "STAGE 3→4 — ALL GATES PASSED — BUY SIGNAL NOW 🚨"
    return "UNKNOWN"


def next_trigger(g1, g2, g3, g4, latest):
    """Return a specific, number-driven message about what must happen next."""

    # Gate 1 failing — identify which MA condition is broken
    if not gate_passed(g1):
        msgs = []
        if not g1["price_above_200ma"]:
            gap = round(latest["ma200"] - latest["price"], 2)
            pct = round(gap / latest["ma200"] * 100, 1)
            msgs.append(f"Price ₹{latest['price']} needs to rise ₹{gap} ({pct}%) to reclaim 200 MA (₹{latest['ma200']})")
        if not g1["ema20_above_200ma"]:
            msgs.append(f"20 EMA (₹{latest['ema20']}) still below 200 MA (₹{latest['ma200']}) — needs more time above 200 MA")
        if not g1["ema5_above_ema20"]:
            msgs.append(f"5 EMA (₹{latest['ema5']}) below 20 EMA (₹{latest['ema20']}) — wait for short-term momentum to pick up")
        return " | ".join(msgs)

    # Gate 2 failing — ADX or DI
    if not gate_passed(g2):
        msgs = []
        if not g2["adx_above_25"]:
            gap = round(25 - latest["adx"], 1)
            msgs.append(f"ADX at {latest['adx']} needs {gap} more points to reach 25 — trend building but not confirmed")
        if not g2["di_plus_leads"]:
            msgs.append(f"DI+ ({latest['plus_di']}) < DI- ({latest['minus_di']}) — bears still in control, wait for DI+ crossover")
        return " | ".join(msgs)

    # Gate 3 failing — timing/pullback
    if not gate_passed(g3):
        msgs = []
        if not g3["rsi_entry_zone"]:
            if latest["rsi"] > 62:
                msgs.append(f"RSI {latest['rsi']} is overbought — wait for pullback to 45–62 zone")
            else:
                msgs.append(f"RSI {latest['rsi']} too low — wait for momentum to build above 45")
        if not g3["price_near_ema20"]:
            diff = round(latest["price"] - latest["ema20"], 2)
            pct  = round(latest["pct_from_e20"], 1)
            if pct > 3:
                msgs.append(f"Price ₹{latest['price']} is {pct}% above 20 EMA (₹{latest['ema20']}) — wait for ₹{round(latest['ema20'] * 1.01, 2)}–₹{round(latest['ema20'] * 1.03, 2)} pullback zone")
            else:
                msgs.append(f"Price ₹{latest['price']} is {abs(pct)}% below 20 EMA — needs to bounce back above ₹{latest['ema20']}")
        if not g3["higher_low_intact"]:
            msgs.append("No higher low yet — structure still weak, wait for price to make a higher low")
        return " | ".join(msgs)

    # Gate 4 failing — trigger candle
    if not gate_passed(g4):
        msgs = []
        if not g4["green_candle"]:
            msgs.append("Today's candle is red — need a green close (price > open)")
        if not g4["close_above_ema20"]:
            msgs.append(f"Close ₹{latest['price']} must be above 20 EMA ₹{latest['ema20']}")
        if not g4["volume_above_avg"]:
            shortfall = latest["vol_ma20"] - latest["volume"]
            msgs.append(f"Volume {latest['volume']:,} is below avg {latest['vol_ma20']:,} — need {shortfall:,} more shares traded")
        if not g4["strong_candle_body"]:
            msgs.append("Candle body weak (< 50% of range) — wait for a strong conviction candle")
        return "⚡ Almost there! " + " | ".join(msgs)

    return "✅ All gates passed — BUY NOW"


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
        latest, g1, g2, g3, g4 = evaluate_gates(df)
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

    stage    = current_stage(g1, g2, g3, g4, latest)
    trade    = stop_and_target(df, latest) if gate_passed(g1) else None
    all_pass = gate_passed(g1) and gate_passed(g2) and gate_passed(g3) and gate_passed(g4)

    gates_score = sum([
        gate_passed(g1), gate_passed(g2), gate_passed(g3), gate_passed(g4)
    ])

    value   = get_value_score(symbol, latest["price"])
    trigger = next_trigger(g1, g2, g3, g4, latest)

    return {
        "symbol":      symbol,
        "latest":      latest,
        "gates":       {"G1": g1, "G2": g2, "G3": g3, "G4": g4},
        "stage":       stage,
        "gates_score": f"{gates_score}/4",
        "buy_signal":  all_pass,
        "trade":       trade,
        "value":       value,
        "trigger":     trigger,
    }


# ── Print Report ──────────────────────────────────────────────────────────────

def print_report(result, verbose=True):
    if "error" in result:
        print(f"  {result['symbol']:<20} ERROR: {result['error']}")
        return

    s  = result["symbol"]
    l  = result["latest"]
    gs = result["gates"]
    tr = result["trade"]

    sep = "=" * 60

    if verbose:
        print(f"\n{sep}")
        print(f"  {s}   |   Price: ₹{l['price']}   |   Gates: {result['gates_score']}")
        print(sep)

        print(f"\n  Indicators:")
        print(f"    EMA5:  {l['ema5']}    EMA20: {l['ema20']}    MA200: {l['ma200']}")
        print(f"    RSI:   {l['rsi']}     ADX:   {l['adx']}     ATR:   {l['atr']}")
        print(f"    DI+:   {l['plus_di']}    DI-:   {l['minus_di']}")
        print(f"    Vol:   {l['volume']:,}    AvgVol: {l['vol_ma20']:,}")
        print(f"    % from 20 EMA: {l['pct_from_e20']}%")

        gate_labels = {
            "G1": {
                "price_above_200ma": "Price above 200 MA",
                "ema20_above_200ma": "20 EMA above 200 MA",
                "ema5_above_ema20":  "5 EMA above 20 EMA",
            },
            "G2": {
                "adx_above_25":  "ADX > 25 (strong trend)",
                "di_plus_leads": "DI+ > DI- (bullish)",
            },
            "G3": {
                "rsi_entry_zone":    "RSI 45–62 (entry zone)",
                "price_near_ema20":  "Price within -1% to +3% of 20 EMA",
                "higher_low_intact": "Higher low structure intact",
            },
            "G4": {
                "green_candle":       "Green candle (close > open)",
                "close_above_ema20":  "Close above 20 EMA",
                "volume_above_avg":   "Volume > 20-day average",
                "strong_candle_body": "Candle body > 50% of range",
            },
        }

        gate_names = {
            "G1": "GATE 1 — Trend Gate",
            "G2": "GATE 2 — Strength Gate",
            "G3": "GATE 3 — Timing Gate",
            "G4": "GATE 4 — Trigger Gate",
        }

        print()
        for gk, checks in gs.items():
            passed = gate_passed(checks)
            icon   = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {gate_names[gk]}  [{icon}]")
            for ck, cv in checks.items():
                ci = "  ✅" if cv else "  ❌"
                print(f"    {ci}  {gate_labels[gk][ck]}")
            print()

        print(f"  Stage:  {result['stage']}")
        print(f"\n  Next Trigger:")
        print(f"    → {result['trigger']}")

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
        # One-line summary + next trigger on second line
        signal = "🚨 BUY" if result["buy_signal"] else "   --"
        v = result["value"]
        print(f"  {signal}  {s:<20} Gates:{result['gates_score']}  "
              f"RSI:{l['rsi']:<6} ADX:{l['adx']:<6} "
              f"Value:{v['value_score']}/4  52w%:{v['week52_position']}  "
              f"Stage: {result['stage'].split('—')[0].strip()}")
        print(f"           {'':20} → {result['trigger']}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

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
    "TCS.NS",
    "HDFCLIFE.NS",
    "HINDALCO.NS",
    "NTPC.NS",
    "ONGC.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "JSWSTEEL.NS",
    "IRFC.NS",
    "TVSMOTOR.NS",
    "NAUKRI.NS",
    "JIOFIN.NS",
    "TORNTPHARM.NS",
    "ATGL.NS",
    "IRCTC.NS",
    "PIDILITIND.NS",
    "AMBUJACEM.NS",
    "DLF.NS",
    "LODHA.NS",
    "INDIGO.NS",
    "CANBK.NS",
    "DIVISLAB.NS",
    "ICICIPRULI.NS",
    "TATAPOWER.NS",
    "VEDL.NS",
    "RECLTD.NS",
    "VBL.NS",
    "JINDALSTEL.NS",
    "ABB.NS",
    "PNB.NS",
    "SIEMENS.NS",
    "GAIL.NS",
    "BAJAJHLDNG.NS",
    "ADANIENSOL.NS",
    "NHPC.NS",
    "ADANIGREEN.NS",
    "PFC.NS",
    "UNIONBANK.NS",
    "BANKBARODA.NS",
    "MOTHERSON.NS",
    "BOSCHLTD.NS",
    "IOC.NS",
    "CHOLAFIN.NS",
    "ICICIGI.NS",
    "BHEL.NS",
    "SHREECEM.NS",
    "GODREJCP.NS",
    "ETERNAL.NS",
    "HAL.NS",
    "LICI.NS",
    "UNITDSPR.NS",
    "HAVELLS.NS",
    "DABUR.NS",
    "JSWENERGY.NS",
    "ZYDUSLIFE.NS",
    "LTIM.NS",
    "DMART.NS",
    "ADANIPOWER.NS",
    "BAJAJFINSV.NS",
    "BAJFINANCE.NS",
    "TITAN.NS",
    "BHARTIARTL.NS",
    "BEL.NS",
    "CIPLA.NS",
    "HINDUNILVR.NS",
    "TATASTEEL.NS",
    "TRENT.NS",
    "MARUTI.NS",
    "SHRIRAMFIN.NS",
    "KOTAKBANK.NS",
    "TATACONSUM.NS",
    "TATAMOTORS.NS",
    "ULTRACEMCO.NS",
    "TECHM.NS",
    "POWERGRID.NS",
    "LT.NS",
    "BPCL.NS",
    "SUNPHARMA.NS",
    "RELIANCE.NS",
    "BRITANNIA.NS",
    "BAJAJ-AUTO.NS",
    "M&M.NS",
    "SBIN.NS",
    "GRASIM.NS",
    "SBILIFE.NS",
    "COALINDIA.NS",
    "DRREDDY.NS",
    "ASIANPAINT.NS",
    "ADANIENT.NS",
    "HCLTECH.NS",
    "ICICIBANK.NS",
    "INDUSINDBK.NS",
    "AXISBANK.NS",
    "NESTLEIND.NS",
    "ITC.NS",
    "EICHERMOT.NS",
    "WIPRO.NS",
    "ADANIPORTS.NS",
    "HEROMOTOCO.NS",
    "APOLLOHOSP.NS",
]

    print("\n\n" + "="*60)
    print("  SWING TRADE SCANNER — ALL STOCKS")
    print("="*60)

    buy_signals = []
    watch_list  = []

    for ticker in watchlist:
        r = analyze_stock(ticker)
        if "error" not in r:
            print_report(r, verbose=False)
            if r["buy_signal"]:
                buy_signals.append(r)
            elif r["gates_score"] in ("3/4",):
                watch_list.append(r)

    if buy_signals:
        print("\n\n🚨 ACTIVE BUY SIGNALS (all 4 gates passed):")
        print("─"*60)
        for r in buy_signals:
            l  = r["latest"]
            tr = r["trade"]
            v  = r["value"]
            rr = tr["rr_ratio"] if tr else "N/A"
            print(f"  {r['symbol']:<20}  Price: ₹{l['price']:<10}  "
                  f"RSI: {l['rsi']:<6}  R:R: {rr}x  Value: {v['value_label']}")

    if watch_list:
        print("\n\n👀 WATCHLIST (3/4 gates passed — entry near):")
        print("─"*60)
        for r in watch_list:
            l = r["latest"]
            v = r["value"]
            print(f"  {r['symbol']:<20}  Price: ₹{l['price']:<10}  "
                  f"RSI: {l['rsi']:<6}  Value: {v['value_label']}  "
                  f"{r['stage'].split('—')[1].strip()}")

    # Best combined picks: gates >= 2 AND value_score >= 2
    print("\n\n⭐ VALUE + SWING COMBINED PICKS (Gates≥2 AND Value≥2):")
    print("─"*60)
    combined = [
        r for r in [analyze_stock(t) for t in watchlist]
        if "error" not in r
        and int(r["gates_score"][0]) >= 2
        and r["value"]["value_score"] >= 2
    ]
    if combined:
        combined.sort(key=lambda r: (int(r["gates_score"][0]) + r["value"]["value_score"]), reverse=True)
        for r in combined:
            l = r["latest"]
            v = r["value"]
            print(f"  {r['symbol']:<20}  Gates:{r['gates_score']}  Value:{v['value_score']}/4  "
                  f"P/E:{v['pe']}  52w%:{v['week52_position']}  WeeklyRSI:{v['weekly_rsi']}")
            print(f"  {'':20}  Stage: {r['stage'].split('—')[0].strip()}")
            print(f"  {'':20}  → {r['trigger']}")
            print()
    else:
        print("  No combined picks today — check back tomorrow.")
