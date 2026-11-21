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

import re

import requests
import yfinance as yf
import pandas as pd

from pnlHistory import get_trade_info, in_trading_zone

SCREENER_HEADERS = {"User-Agent": "Mozilla/5.0"}
SCREENER_SEARCH_URL = "https://www.screener.in/api/company/search/"
SCREENER_CHART_URL  = "https://www.screener.in/api/company/{id}/chart/"


# ── Data ─────────────────────────────────────────────────────────────────────

def _yf_download(symbol, period="1y", interval="1d", auto_adjust=True, progress=False):
    """Thread-safe stand-in for yf.download (which shares global state across
    concurrent calls). Returns the same OHLCV frame for a single symbol."""
    return yf.Ticker(symbol).history(period=period, interval=interval,
                                     auto_adjust=auto_adjust)

def get_ohlcv(symbol, period="1y", interval="1d"):
    df = _yf_download(symbol, period=period, interval=interval,
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

def coppock(close, roc1=11, roc2=14, wma_period=10):
    """
    Coppock Curve — long-term momentum indicator on monthly closes:
        WMA(wma_period) of [ROC(roc1) + ROC(roc2)]
    A rising curve from below zero is the classic "major bottom" buy signal.
    """
    roc_sum = close.pct_change(roc1) * 100 + close.pct_change(roc2) * 100
    weights = pd.Series(range(1, wma_period + 1), dtype=float)
    return roc_sum.rolling(wma_period).apply(
        lambda x: (x * weights.values).sum() / weights.sum(), raw=True
    )


# ── 5-Year Median PE Valuation ─────────────────────────────────────────────────

def _pe_verdict(pct):
    if pct <= -20:
        return "UNDERVALUED ✅"
    if pct <= 20:
        return "REASONABLE 🟡"
    return "OVERVALUED ❌"


def _bare_symbol(symbol):
    """Strip exchange suffix (e.g. 'TCS.NS' → 'TCS') for screener.in lookups."""
    return symbol.split(".")[0]


def screener_company_lookup(symbol):
    """Resolve a bare NSE/BSE symbol to screener.in's (company_id, page_url)."""
    bare = _bare_symbol(symbol)
    resp = requests.get(SCREENER_SEARCH_URL, params={"q": bare},
                        headers=SCREENER_HEADERS, timeout=10)
    resp.raise_for_status()
    for hit in resp.json():
        m = re.match(r"^/company/([^/]+)/", hit.get("url", ""))
        if m and m.group(1).upper() == bare.upper():
            return hit["id"], hit["url"]
    return None, None


def screener_company_id(symbol):
    """Resolve a bare NSE/BSE symbol to screener.in's numeric company id."""
    company_id, _ = screener_company_lookup(symbol)
    return company_id


def get_pe_valuation_screener(symbol):
    """
    Fetches screener.in's own 5-year (1825-day) PE chart for the stock:
    weekly historical PE, TTM EPS, and their pre-computed Median PE line.
    Classifies current PE vs that median:
      <= -20%           → UNDERVALUED
      -20% .. +20%       → REASONABLE
      > +20%             → OVERVALUED
    """
    result = {
        "median_pe":        None,
        "current_pe":       None,
        "pct_from_median":  None,
        "verdict":          "N/A",
        "source":           "screener.in",
    }

    company_id = screener_company_id(symbol)
    if company_id is None:
        return result

    resp = requests.get(
        SCREENER_CHART_URL.format(id=company_id),
        params={"q": "Price to Earning-Median PE-EPS", "days": 1825, "consolidated": "true"},
        headers=SCREENER_HEADERS, timeout=10,
    )
    resp.raise_for_status()
    datasets = resp.json().get("datasets", [])

    median_pe = None
    current_pe = None
    for ds in datasets:
        if ds.get("metric") == "Median PE" and ds.get("values"):
            median_pe = float(ds["values"][-1][1])
        elif ds.get("metric") == "Price to Earning" and ds.get("values"):
            current_pe = float(ds["values"][-1][1])

    if median_pe and current_pe and median_pe > 0:
        result["median_pe"]  = round(median_pe, 1)
        result["current_pe"] = round(current_pe, 1)
        pct = (current_pe - median_pe) / median_pe * 100
        result["pct_from_median"] = round(pct, 1)
        result["verdict"] = _pe_verdict(pct)

    return result


# ── PEG Ratio ────────────────────────────────────────────────────────────────

def get_peg_ratio(symbol):
    """
    PEG = current P/E ÷ 3-year EPS growth rate (%), using screener.in's own
    quarterly TTM-EPS series and latest PE from the same 5y chart endpoint.
    Returns dict with current_pe, eps_now, eps_3y_ago, eps_cagr_pct, peg.
    Returns an all-None dict (no exception) if screener.in is unreachable
    or the symbol can't be resolved.
    """
    empty = {
        "current_pe":    None,
        "eps_now":       None,
        "eps_3y_ago":    None,
        "eps_cagr_pct":  None,
        "peg":           None,
        "source":        "screener.in",
    }
    try:
        return _get_peg_ratio(symbol)
    except Exception:
        return empty


def _get_peg_ratio(symbol):
    result = {
        "current_pe":    None,
        "eps_now":       None,
        "eps_3y_ago":    None,
        "eps_cagr_pct":  None,
        "peg":           None,
        "source":        "screener.in",
    }

    company_id = screener_company_id(symbol)
    if company_id is None:
        return result

    resp = requests.get(
        SCREENER_CHART_URL.format(id=company_id),
        params={"q": "Price to Earning-EPS", "days": 1825, "consolidated": "true"},
        headers=SCREENER_HEADERS, timeout=10,
    )
    resp.raise_for_status()
    datasets = resp.json().get("datasets", [])

    current_pe = None
    eps_points = []
    for ds in datasets:
        if ds.get("metric") == "Price to Earning" and ds.get("values"):
            current_pe = float(ds["values"][-1][1])
        elif ds.get("metric") == "EPS" and ds.get("values"):
            eps_points = [(d, float(v)) for d, v in ds["values"]]

    if current_pe is None or len(eps_points) < 2:
        return result

    result["current_pe"] = round(current_pe, 1)

    latest_date, eps_now = eps_points[-1]
    target = pd.to_datetime(latest_date) - pd.Timedelta(days=1095)

    eps_3y_ago = None
    for d, v in eps_points:
        if pd.to_datetime(d) <= target:
            eps_3y_ago = v
        else:
            break

    if eps_3y_ago is None or eps_3y_ago <= 0 or eps_now <= 0:
        return result

    years = (pd.to_datetime(latest_date) - pd.to_datetime(
        next(d for d, v in eps_points if v == eps_3y_ago))).days / 365.25
    if years <= 0:
        return result

    cagr = (eps_now / eps_3y_ago) ** (1 / years) - 1

    result["eps_now"]      = round(eps_now, 2)
    result["eps_3y_ago"]   = round(eps_3y_ago, 2)
    result["eps_cagr_pct"] = round(cagr * 100, 2)

    if cagr > 0:
        result["peg"] = round(current_pe / (cagr * 100), 2)

    return result


def get_pe_valuation_yfinance(symbol, current_price=None, current_pe=None):
    """
    Fallback: builds a historical daily P/E series over the last 5 years
    (price / trailing annual EPS as of each date) and compares current P/E
    against its median. Used when screener.in lookup fails.
    """
    result = {
        "median_pe":        None,
        "current_pe":       current_pe,
        "pct_from_median":  None,
        "verdict":          "N/A",
        "source":           "yfinance",
    }

    try:
        ticker = yf.Ticker(symbol)

        eps_hist = ticker.income_stmt.loc["Diluted EPS"].dropna().sort_index()
        if eps_hist.empty:
            return result

        price_hist = _yf_download(symbol, period="5y", interval="1d",
                                  auto_adjust=True, progress=False)
        if price_hist is None or price_hist.empty:
            return result
        if isinstance(price_hist.columns, pd.MultiIndex):
            price_hist.columns = [col[0] for col in price_hist.columns]
        closes = price_hist["Close"].dropna()

        # For each trading day, use the EPS from the most recently completed
        # fiscal year as of that date (as-of join).
        eps_for_day = eps_hist.reindex(closes.index, method="ffill")

        # Before the first known fiscal year, fall back to the earliest EPS
        # available so the early portion of the window isn't dropped entirely.
        eps_for_day = eps_for_day.fillna(eps_hist.iloc[0])

        daily_pe = (closes / eps_for_day).replace([float("inf"), float("-inf")], pd.NA).dropna()
        daily_pe = daily_pe[daily_pe > 0]

        if daily_pe.empty:
            return result

        median_pe = float(daily_pe.median())
        result["median_pe"] = round(median_pe, 1)

        cur_pe = current_pe
        if cur_pe is None:
            latest_eps = float(eps_hist.iloc[-1])
            if current_price and latest_eps > 0:
                cur_pe = current_price / latest_eps

        if cur_pe and cur_pe > 0 and median_pe > 0:
            result["current_pe"] = round(cur_pe, 1)
            pct = (cur_pe - median_pe) / median_pe * 100
            result["pct_from_median"] = round(pct, 1)
            result["verdict"] = _pe_verdict(pct)

    except Exception:
        pass

    return result


def get_pe_valuation(symbol, current_price=None, current_pe=None):
    """
    5-year median PE valuation. Tries screener.in's own precomputed median
    PE first (more accurate, real TTM EPS); falls back to a yfinance-derived
    approximation if screener.in is unreachable or the symbol isn't found.
    """
    try:
        result = get_pe_valuation_screener(symbol)
        if result["median_pe"] is not None:
            return result
    except Exception:
        pass

    return get_pe_valuation_yfinance(symbol, current_price=current_price, current_pe=current_pe)


# ── Fundamental Quality Flags ───────────────────────────────────────────────────
#
# Scrapes screener.in's Balance Sheet, Cash Flow, Profit & Loss, and
# Shareholding Pattern tables (rendered as plain HTML tables on the company
# page — no separate JSON API covers these) to surface quality signals and
# red flags with a plain-English reason for each.

SCREENER_PAGE_URL = "https://www.screener.in{path}"


def _fetch_screener_page(symbol):
    _, url_path = screener_company_lookup(symbol)
    if url_path is None:
        return None
    resp = requests.get(SCREENER_PAGE_URL.format(path=url_path),
                        headers=SCREENER_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.text


def _section_html(page_html, section_id):
    start = page_html.find(f'id="{section_id}"')
    if start == -1:
        return None
    start = page_html.rfind("<section", 0, start)
    next_start = page_html.find("<section", start + 1)
    end = next_start if next_start != -1 else len(page_html)
    return page_html[start:end]


def _section_tables(page_html, section_id):
    frag = _section_html(page_html, section_id)
    if frag is None:
        return []
    try:
        from io import StringIO
        return pd.read_html(StringIO(frag))
    except ValueError:
        return []


def _row(df, label):
    """Fetch a table row by its leading label, ignoring the '+' expand marker."""
    for idx in df.index:
        cell = str(df.iloc[idx, 0]).replace("\xa0+", "").strip()
        if cell == label:
            return df.iloc[idx, 1:]
    return None


def _to_numeric(series):
    return pd.to_numeric(
        series.astype(str).str.replace("%", "", regex=False)
                          .str.replace(",", "", regex=False),
        errors="coerce",
    )


def _flag(name, severity, description):
    return {"flag": name, "severity": severity, "description": description}


def get_quality_flags(symbol):
    """
    Fundamental quality/red-flag scan using screener.in's Balance Sheet,
    Cash Flow, Profit & Loss, and Shareholding tables.

    severity: "red" (red flag), "yellow" (caution), "green" (positive signal)
    Returns {"flags": [...], "error": str|None}
    """
    out = {"flags": [], "error": None}

    try:
        page = _fetch_screener_page(symbol)
        if page is None:
            out["error"] = "Could not resolve symbol on screener.in"
            return out

        # ── Cash flow quality: CFO vs Operating Profit ──────────────────────
        cf_tables = _section_tables(page, "cash-flow")
        if cf_tables:
            cfop = _to_numeric(_row(cf_tables[0], "CFO/OP"))
            if cfop is not None and len(cfop.dropna()) >= 3:
                recent = cfop.dropna().iloc[-3:]
                avg_recent = recent.mean()
                if avg_recent < 70:
                    out["flags"].append(_flag(
                        "Weak cash conversion", "red",
                        f"Cash from Operations has averaged only {avg_recent:.0f}% of "
                        f"Operating Profit over the last 3 years — a large chunk of "
                        f"reported profit isn't turning into actual cash, which can mean "
                        f"aggressive revenue recognition or rising receivables."
                    ))
                elif avg_recent >= 90:
                    out["flags"].append(_flag(
                        "Strong cash conversion", "green",
                        f"Cash from Operations has averaged {avg_recent:.0f}% of Operating "
                        f"Profit over the last 3 years — reported profit is backed by real cash, "
                        f"a hallmark of high earnings quality."
                    ))

        # ── Balance sheet: leverage trend ───────────────────────────────────
        bs_tables = _section_tables(page, "balance-sheet")
        if bs_tables:
            borrowings = _to_numeric(_row(bs_tables[0], "Borrowings"))
            reserves   = _to_numeric(_row(bs_tables[0], "Reserves"))
            if borrowings is not None and reserves is not None:
                b, r = borrowings.dropna(), reserves.dropna()
                if len(b) >= 2 and len(r) >= 2 and r.iloc[0] > 0 and b.iloc[0] >= 0:
                    debt_growth = (b.iloc[-1] - b.iloc[0])
                    reserve_growth_pct = (r.iloc[-1] / r.iloc[0] - 1) * 100 if r.iloc[0] else 0
                    debt_to_reserves_now = (b.iloc[-1] / r.iloc[-1] * 100) if r.iloc[-1] else 0
                    if debt_to_reserves_now > 50 and debt_growth > 0 and b.iloc[-1] > b.iloc[0] * 1.5:
                        out["flags"].append(_flag(
                            "Rising leverage", "red",
                            f"Borrowings grew from ₹{b.iloc[0]:,.0f} Cr to ₹{b.iloc[-1]:,.0f} Cr "
                            f"while Reserves grew {reserve_growth_pct:.0f}% over the same period — "
                            f"debt is now {debt_to_reserves_now:.0f}% of Reserves and climbing, "
                            f"a sign the business may be leaning more on borrowed capital."
                        ))
                    elif debt_to_reserves_now < 15:
                        out["flags"].append(_flag(
                            "Low leverage", "green",
                            f"Borrowings are just {debt_to_reserves_now:.0f}% of Reserves "
                            f"(₹{b.iloc[-1]:,.0f} Cr vs ₹{r.iloc[-1]:,.0f} Cr) — the balance "
                            f"sheet carries very little debt risk."
                        ))

        # ── P&L: margin stability + growth deceleration ─────────────────────
        pl_tables = _section_tables(page, "profit-loss")
        if pl_tables:
            opm = _to_numeric(_row(pl_tables[0], "OPM %"))
            if opm is not None:
                opm_hist = opm.dropna().iloc[:-1] if len(opm.dropna()) > 1 else opm.dropna()
                if len(opm_hist) >= 3:
                    recent3 = opm_hist.iloc[-3:]
                    if recent3.iloc[-1] < recent3.iloc[0] - 3 and recent3.is_monotonic_decreasing:
                        out["flags"].append(_flag(
                            "Margin erosion", "red",
                            f"Operating margin has declined for 3 straight years "
                            f"({recent3.iloc[0]:.0f}% → {recent3.iloc[-1]:.0f}%) — signals "
                            f"weakening pricing power or rising costs relative to sales."
                        ))
                    elif opm_hist.std() < 2:
                        out["flags"].append(_flag(
                            "Stable margins", "green",
                            f"Operating margin has stayed within a tight "
                            f"{opm_hist.min():.0f}%–{opm_hist.max():.0f}% band over the "
                            f"available history — consistent pricing power and cost control."
                        ))

            for tbl in pl_tables[1:]:
                cols = [str(c) for c in tbl.columns]
                if "Compounded Profit Growth" in cols[0]:
                    growth = {str(row[0]).rstrip(":"): row[1] for row in tbl.itertuples(index=False)}
                    g3 = growth.get("3 Years")
                    g5 = growth.get("5 Years")
                    if g3 is not None and g5 is not None:
                        g3n = pd.to_numeric(str(g3).replace("%", ""), errors="coerce")
                        g5n = pd.to_numeric(str(g5).replace("%", ""), errors="coerce")
                        if pd.notna(g3n) and pd.notna(g5n) and g3n < g5n - 5:
                            out["flags"].append(_flag(
                                "Growth decelerating", "yellow",
                                f"3-year profit growth ({g3n:.0f}%) is notably lower than "
                                f"5-year profit growth ({g5n:.0f}%) — the business is compounding "
                                f"profit more slowly than its own recent history."
                            ))

        # ── Shareholding: FII and Promoter trend ────────────────────────────
        sh_tables = _section_tables(page, "shareholding")
        if sh_tables:
            fii  = _to_numeric(_row(sh_tables[0], "FIIs"))
            promoters = _to_numeric(_row(sh_tables[0], "Promoters"))
            if fii is not None:
                fii_hist = fii.dropna()
                if len(fii_hist) >= 4:
                    window = fii_hist  # use the full available history (up to ~12 quarters)
                    diffs = window.diff().dropna()
                    declining_share = (diffs < 0).mean() if len(diffs) else 0
                    total_drop = window.iloc[0] - window.iloc[-1]
                    if declining_share >= 0.55 and total_drop > 1:
                        out["flags"].append(_flag(
                            "FII holding declining", "yellow",
                            f"Foreign institutional holding has trended down over the last "
                            f"{len(window)} quarters ({window.iloc[0]:.1f}% → "
                            f"{window.iloc[-1]:.1f}%) — large global investors have been "
                            f"steadily reducing exposure, which can precede or reflect "
                            f"slower growth expectations."
                        ))
            if promoters is not None:
                p_hist = promoters.dropna()
                if len(p_hist) >= 4:
                    full_drop = p_hist.iloc[0] - p_hist.iloc[-1]
                    if full_drop > 1:
                        out["flags"].append(_flag(
                            "Promoter holding declining", "red",
                            f"Promoter holding fell from {p_hist.iloc[0]:.1f}% to "
                            f"{p_hist.iloc[-1]:.1f}% over the last {len(p_hist)} quarters "
                            f"— check company announcements for the reason (block deal, "
                            f"pledge, open offer, etc.); unexplained promoter selling is a "
                            f"classic red flag."
                        ))
                    elif full_drop <= 0.05:
                        out["flags"].append(_flag(
                            "Promoter holding stable", "green",
                            f"Promoter holding has stayed flat at ~{p_hist.iloc[-1]:.1f}% "
                            f"over the last {len(p_hist)} quarters — no dilution or "
                            f"insider-selling concern."
                        ))

    except Exception as e:
        out["error"] = str(e)

    return out


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
        "coppock_daily":            None,
        "coppock_daily_prev":       None,
        "coppock_daily_verdict":    "N/A",
        "coppock_monthly":          None,
        "coppock_monthly_prev":     None,
        "coppock_monthly_verdict":  "N/A",
        "coppock_weekly":           None,
        "coppock_weekly_prev":      None,
        "coppock_weekly_verdict":   "N/A",
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

    def _coppock_verdict(cur_cop, prev_cop):
        rising = cur_cop > prev_cop
        if cur_cop < 0 and rising:
            return "TURNING UP FROM NEGATIVE (bullish) 🟢"
        elif cur_cop < 0:
            return "NEGATIVE, still falling"
        elif rising:
            return "POSITIVE, rising"
        else:
            return "POSITIVE, falling"

    # Weekly RSI + weekly Coppock from 2 years of weekly data
    try:
        df_w = _yf_download(symbol, period="2y", interval="1wk",
                           auto_adjust=True, progress=False)
        if not df_w.empty:
            if isinstance(df_w.columns, pd.MultiIndex):
                df_w.columns = [col[0] for col in df_w.columns]
            closes_w = df_w["Close"].dropna()

            w_rsi = rsi(closes_w)
            val = float(w_rsi.dropna().iloc[-1])
            result["weekly_rsi"] = round(val, 1)
            if val < 45:
                result["weekly_rsi_verdict"] = "OVERSOLD (value zone)"
            elif val <= 60:
                result["weekly_rsi_verdict"] = "NEUTRAL (healthy)"
            else:
                result["weekly_rsi_verdict"] = "OVERBOUGHT (expensive)"

            cop_w = coppock(closes_w).dropna()
            if len(cop_w) >= 2:
                cur_cop, prev_cop = float(cop_w.iloc[-1]), float(cop_w.iloc[-2])
                result["coppock_weekly"]      = round(cur_cop, 2)
                result["coppock_weekly_prev"] = round(prev_cop, 2)
                result["coppock_weekly_verdict"] = _coppock_verdict(cur_cop, prev_cop)
    except Exception:
        pass

    # Daily Coppock from 2 years of daily closes
    try:
        df_d = _yf_download(symbol, period="2y", interval="1d",
                           auto_adjust=True, progress=False)
        if not df_d.empty:
            if isinstance(df_d.columns, pd.MultiIndex):
                df_d.columns = [col[0] for col in df_d.columns]
            cop_d = coppock(df_d["Close"].dropna()).dropna()
            if len(cop_d) >= 2:
                cur_cop, prev_cop = float(cop_d.iloc[-1]), float(cop_d.iloc[-2])
                result["coppock_daily"]      = round(cur_cop, 2)
                result["coppock_daily_prev"] = round(prev_cop, 2)
                result["coppock_daily_verdict"] = _coppock_verdict(cur_cop, prev_cop)
    except Exception:
        pass

    # Coppock Curve from monthly closes (needs ~3y+ of history for ROC(14) + WMA(10))
    try:
        df_m = _yf_download(symbol, period="15y", interval="1mo",
                           auto_adjust=True, progress=False)
        if not df_m.empty:
            if isinstance(df_m.columns, pd.MultiIndex):
                df_m.columns = [col[0] for col in df_m.columns]
            cop_m = coppock(df_m["Close"].dropna()).dropna()
            if len(cop_m) >= 2:
                cur_cop, prev_cop = float(cop_m.iloc[-1]), float(cop_m.iloc[-2])
                result["coppock_monthly"]      = round(cur_cop, 2)
                result["coppock_monthly_prev"] = round(prev_cop, 2)
                result["coppock_monthly_verdict"] = _coppock_verdict(cur_cop, prev_cop)
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
    pe_val  = get_pe_valuation(symbol, current_price=latest["price"], current_pe=value["pe"])
    peg     = get_peg_ratio(symbol)
    quality = get_quality_flags(symbol)
    trigger = next_trigger(g1, g2, g3, g4, latest)

    my_trade = get_trade_info(symbol)
    below_last_sell = None
    if my_trade and my_trade.get("avg_sell_price"):
        below_last_sell = latest["price"] <= my_trade["avg_sell_price"]
    zone_hit = in_trading_zone(latest["price"], my_trade["avg_sell_price"]) if my_trade else False

    return {
        "symbol":      symbol,
        "latest":      latest,
        "gates":       {"G1": g1, "G2": g2, "G3": g3, "G4": g4},
        "stage":       stage,
        "gates_score": f"{gates_score}/4",
        "buy_signal":  all_pass,
        "trade":       trade,
        "value":       value,
        "pe_valuation": pe_val,
        "peg":         peg,
        "quality":     quality,
        "trigger":     trigger,
        "my_trade":    my_trade,
        "below_last_sell": below_last_sell,
        "in_trading_zone": zone_hit,
    }


def analyze_stocks_parallel(symbols, chunk_size=50, max_workers=8, progress_cb=None):
    """Analyze symbols in chunks, each chunk processed by a thread pool.
    Returns results in the same order as `symbols`. A failure in one stock
    becomes an error result instead of aborting the batch.
    progress_cb(done, total) is called from the calling thread."""
    from concurrent.futures import ThreadPoolExecutor

    def _safe(sym):
        try:
            return analyze_stock(sym)
        except Exception as e:
            return {"symbol": sym, "error": f"{type(e).__name__}: {e}"}

    results, total = [], len(symbols)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for i in range(0, total, chunk_size):
            chunk = symbols[i:i + chunk_size]
            results.extend(pool.map(_safe, chunk))
            if progress_cb:
                progress_cb(len(results), total)
    return results


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
        cop_d_str = f"Coppock (daily): {v['coppock_daily']} (prev {v['coppock_daily_prev']}) — {v['coppock_daily_verdict']}" \
                    if v['coppock_daily'] is not None else "Coppock (daily): N/A"
        cop_w_str = f"Coppock (weekly): {v['coppock_weekly']} (prev {v['coppock_weekly_prev']}) — {v['coppock_weekly_verdict']}" \
                    if v['coppock_weekly'] is not None else "Coppock (weekly): N/A"
        cop_m_str = f"Coppock (monthly): {v['coppock_monthly']} (prev {v['coppock_monthly_prev']}) — {v['coppock_monthly_verdict']}" \
                    if v['coppock_monthly'] is not None else "Coppock (monthly): N/A"
        print(f"    {pe_str}")
        print(f"    {pos_str}")
        print(f"    {wrsi_str}")
        print(f"    {cop_d_str}")
        print(f"    {cop_w_str}")
        print(f"    {cop_m_str}")

        # 5-year median PE valuation
        pv = result.get("pe_valuation")
        if pv and pv["median_pe"] is not None:
            pct_str = f"{pv['pct_from_median']:+.1f}%" if pv["pct_from_median"] is not None else "N/A"
            print(f"\n  5Y Median PE Valuation:  {pv['verdict']}")
            print(f"    Current P/E: {pv['current_pe']}   5Y Median P/E: {pv['median_pe']}   "
                  f"Diff: {pct_str}   (source: {pv.get('source', 'N/A')})")

        # PEG ratio
        peg = result.get("peg")
        if peg and peg["peg"] is not None:
            print(f"\n  PEG Ratio: {peg['peg']}")
            print(f"    P/E: {peg['current_pe']}   3Y EPS CAGR: {peg['eps_cagr_pct']}%   "
                  f"(EPS {peg['eps_3y_ago']} → {peg['eps_now']})")

        # Fundamental quality flags
        quality = result.get("quality")
        if quality and quality.get("flags"):
            icon_by_severity = {"red": "🔴", "yellow": "🟡", "green": "🟢"}
            print(f"\n  Fundamental Quality Flags:")
            for f in quality["flags"]:
                icon = icon_by_severity.get(f["severity"], "•")
                print(f"    {icon} {f['flag']}")
                print(f"        {f['description']}")
        elif quality and quality.get("error"):
            print(f"\n  Fundamental Quality Flags: unavailable ({quality['error']})")

        my_trade = result.get("my_trade")
        if my_trade:
            print(f"\n  My Trade History:")
            print(f"    Bought {my_trade['quantity']:g} @ avg ₹{my_trade['avg_buy_price']}   "
                  f"Sold @ avg ₹{my_trade['avg_sell_price']}  (last sell: {my_trade['last_sell_date']})")
            print(f"    Realized P&L: ₹{my_trade['realized_pl']:,.2f} ({my_trade['realized_pl_pct']:+.1f}%)")
            if result.get("in_trading_zone"):
                tag = "at/below last sell price" if result.get("below_last_sell") else "back near last sell price"
                print(f"    🔁 Currently {tag} — potential re-entry zone")

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
        v   = result["value"]
        pv  = result.get("pe_valuation") or {}
        peg = result.get("peg") or {}
        pe_verdict = pv.get("verdict", "N/A")
        peg_str    = peg.get("peg", "N/A")
        quality  = result.get("quality") or {}
        n_red    = sum(1 for f in quality.get("flags", []) if f["severity"] == "red")
        n_yellow = sum(1 for f in quality.get("flags", []) if f["severity"] == "yellow")
        flags_str = f"🔴{n_red} 🟡{n_yellow}" if (n_red or n_yellow) else "clean"
        print(f"  {signal}  {s:<20} Gates:{result['gates_score']}  "
              f"RSI:{l['rsi']:<6} ADX:{l['adx']:<6} "
              f"Value:{v['value_score']}/4  52w%:{v['week52_position']}  "
              f"5yPE:{pe_verdict}  PEG:{peg_str}  Flags:{flags_str}  "
              f"Stage: {result['stage'].split('—')[0].strip()}")
        print(f"           {'':20} → {result['trigger']}")


# ── Symbol normalization ──────────────────────────────────────────────────────

def normalize_symbol(sym):
    """Uppercase, strip whitespace, and append .NS if no exchange suffix given."""
    sym = sym.strip().upper()
    if not sym:
        return None
    if "." not in sym:
        sym += ".NS"
    return sym


def parse_symbols(raw):
    """Parse a comma-separated string of tickers into a clean symbol list."""
    return [s for s in (normalize_symbol(x) for x in raw.split(",")) if s]


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    raw_input = input(
        "Enter comma-separated company codes (e.g. TCS,INFY,RELIANCE) "
        "or press Enter to run the default watchlist scan: "
    ).strip()

    if raw_input:
        symbols = parse_symbols(raw_input)
        print("\n" + "─"*60)
        print(f"  ANALYZING {len(symbols)} STOCK(S)")
        print("─"*60)
        for stock in symbols:
            result = analyze_stock(stock)
            print_report(result, verbose=True)
        raise SystemExit(0)

    # ── Single deep-dive ──────────────────────────────────────────────────────
    print("\n" + "─"*60)
    print("  SINGLE STOCK DEEP ANALYSIS")
    print("─"*60)

    for stock in ["ABBOTINDIA.NS", "SOLARINDS.NS", "APOLLOHOSP.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "CMSINFO.NS","PFIZER.NS"]:
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
