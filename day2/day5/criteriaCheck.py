"""
Company Criteria Check — automates CompanyCriteria.xlsx.

Each criterion is PASS / FAIL / NA (NA = not applicable, excluded from the score).
Moat is judgement -> entered manually in the panel.

    P/E    < 14                      current
    P/E<Med current P/E < its 5-year median P/E   (as in swingTradeChecker)
    PEG 3y < 1.4                     P/E / 3-yr EPS CAGR (as in swingTradeChecker)
    PEG    < 1.4                     P/E / net-profit CAGR (longest history, max 10 yrs)
    P/B    < 1.5                     current; NA for IT services (sheet: "not needed")
    D/E    < 0.5                     every year      (total debt / equity)
    GPM    rising with sales         needs gross profit (NA when company doesn't report it)
    OPM    > 15 %                    every year      (EBIT / sales)
    ICR    > 7                       every year      (EBIT / interest)
    ROE    > 15 %                    latest FY       (net income / year-end equity)
    FCF    FCF/sales > 10 %          avg of last 3 yrs, Tickertape FCF ("cash machine")

Banks: D/E, GPM, OPM, ICR, FCF are not meaningful -> NA.

CLI:  python criteriaCheck.py TCS INFY
"""

import re
import sys
import time
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup

from fcfValuation import _get, resolve_sid, INFO_URL

BASE = "https://api.tickertape.in/stocks/financials/{k}/{sid}/annual/normal"

DEFAULT_T = dict(pe=14.0, peg=1.4, peg3=1.4, pb=1.5, de=0.5, opm=15.0, icr=7.0, roe=15.0,
                 fcf_sales=10.0, misses=0)

CRITERIA = ["P/E", "P/E<Med", "PEG", "PEG 3y", "P/B", "D/E", "GPM", "OPM", "ICR", "ROE", "FCF"]
PASS, FAIL, NA = "PASS", "FAIL", "NA"
NO_PB_GROUPS = {"Software & Services", "Information Technology"}
BANK = "Banks"


def _fy(rows):
    return {r["displayPeriod"]: r for r in rows if "TTM" not in r["displayPeriod"].upper()}


def fetch_statements(sid):
    inc = _fy(_get(BASE.format(k="income", sid=sid), count=10))
    bal = _fy(_get(BASE.format(k="balancesheet", sid=sid), count=10))
    cf = _fy(_get(BASE.format(k="cashflow", sid=sid), count=10))
    periods = sorted(inc, key=lambda p: inc[p]["endDate"])
    rows = []
    for p in periods:
        i, b, c = inc[p], bal.get(p, {}), cf.get(p, {})
        sales, ebit, intr = i.get("incTrev"), i.get("incPbi"), i.get("incIoi")
        eq, debt, ni = b.get("balTeq"), b.get("balTdeb"), i.get("incNinc")
        rows.append({
            "year": p.replace("FY ", "FY"),
            "sales": sales,
            "gpm": (i["incGpro"] / sales * 100) if i.get("incGpro") is not None and sales else None,
            "opm": (ebit / sales * 100) if ebit is not None and sales else None,
            "icr": (ebit / intr) if ebit is not None and intr else None,   # no interest -> debt free
            "icr_debtfree": bool(ebit is not None and not intr),
            "de": (debt / eq) if debt is not None and eq else None,
            "roe": (ni / eq * 100) if ni is not None and eq else None,
            "ni": ni,
            "fcf": c.get("cafFcf"),
            "fcf_sales": (c["cafFcf"] / sales * 100) if c.get("cafFcf") is not None and sales else None,
        })
    return pd.DataFrame(rows)


def _all_years(series, ok, misses, debtfree=None):
    """PASS if at most `misses` years break the rule. Returns (status, 'n/N yrs', worst)."""
    vals = [(i, v) for i, v in enumerate(series) if v is not None or (debtfree is not None and debtfree[i])]
    if not vals:
        return NA, "no data", None
    good = sum(1 for i, v in vals if (debtfree is not None and debtfree[i]) or ok(v))
    bad = len(vals) - good
    return (PASS if bad <= misses else FAIL), f"{good}/{len(vals)} yrs ok", None



# ── Screener.in source (works straight from the NSE symbol, no id lookup) ────
SCREENER_URL = "https://www.screener.in/company/{sym}/{view}/"
S_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _num(x):
    """'3,51,600' / '35%' / '-1,234' -> float, else None."""
    try:
        return float(re.sub(r"[,%\s]", "", str(x)))
    except ValueError:
        return None


def _get_screener_html(sym):
    for view in ("consolidated", "standalone"):          # prefer consolidated, like the sheet's URLs
        for attempt in range(3):
            r = requests.get(SCREENER_URL.format(sym=sym, view=view), headers=S_HEADERS, timeout=25)
            if r.status_code == 429:                      # polite backoff
                time.sleep(2 * (attempt + 1)); continue
            break
        if r.status_code == 200 and 'id="profit-loss"' in r.text:
            return r.text, view
        if r.status_code not in (200, 404):
            r.raise_for_status()
    raise LookupError(f"{sym}: not found on screener.in")


def _table(soup, section):
    tb = soup.select_one(f"section#{section} table.data-table")
    if tb is None:
        raise ValueError(f"screener: no {section} table")
    df = pd.read_html(StringIO(str(tb)))[0]
    df[df.columns[0]] = df[df.columns[0]].astype(str).str.replace(r"[\xa0+]", "", regex=True).str.strip()
    df = df.set_index(df.columns[0])
    df = df[[c for c in df.columns if re.match(r"Mar \d{4}$", str(c))]]   # annual (March FY) columns only
    return df


def _row(df, *names):
    for n in names:
        for idx in df.index:
            if idx.lower().startswith(n.lower()):
                return df.loc[idx].map(_num)
    return None


def fetch_screener(sym):
    html, view = _get_screener_html(sym)
    soup = BeautifulSoup(html, "lxml")
    name = soup.find("h1").get_text(strip=True)
    links = [a.get_text(strip=True) for a in soup.select('a[href^="/market/"]')]
    pl, bs, cf = _table(soup, "profit-loss"), _table(soup, "balance-sheet"), _table(soup, "cash-flow")
    bank = any(i.lower().startswith("financing profit") for i in pl.index)

    ratios = {}
    for li in soup.select("#top-ratios li"):
        n = li.select_one(".name").get_text(strip=True)
        v = li.select_one(".number")
        ratios[n] = _num(v.get_text()) if v else None
    price, bv = ratios.get("Current Price"), ratios.get("Book Value")
    top = {"pe": ratios.get("Stock P/E"), "pb": (price / bv) if price and bv else None}

    sales = _row(pl, "Sales", "Revenue")
    opr, dep, intr = _row(pl, "Operating Profit"), _row(pl, "Depreciation"), _row(pl, "Interest")
    ni = _row(pl, "Net Profit")
    eq = _row(bs, "Equity Capital").add(_row(bs, "Reserves"), fill_value=None)
    debt = _row(bs, "Borrowing")
    fcf = _row(cf, "Free Cash Flow")

    rows = []
    for col in pl.columns:
        g = lambda ser: (None if ser is None or col not in ser.index or pd.isna(ser[col]) else float(ser[col]))
        S, O, D, I, N = g(sales), g(opr), g(dep), g(intr), g(ni)
        E, B, F = g(eq), g(debt), g(fcf)
        ebit = (O - D) if O is not None and D is not None else None
        rows.append({
            "year": col.replace("Mar ", "FY"), "sales": S, "gpm": None,           # screener has no gross profit
            "opm": (ebit / S * 100) if ebit is not None and S else None,
            "icr": (ebit / I) if ebit is not None and I else None,
            "icr_debtfree": bool(ebit is not None and not I),
            "de": (B / E) if B is not None and E else None,
            "roe": (N / E * 100) if N is not None and E else None,
            "ni": N, "fcf": F,
            "fcf_sales": (F / S * 100) if F is not None and S else None,
        })
    industry = "Banks" if bank else (links[0] if links else "")
    return name, industry, pd.DataFrame(rows).tail(10), top, view


def evaluate(df, ratios, industrygroup, T, pe_med=None, peg3=None):
    """-> {criterion: (status, value_text, detail)}"""
    out = {}
    bank = industrygroup == BANK
    pe, pb = ratios.get("pe"), ratios.get("pb")

    out["P/E"] = (NA, "-", "no P/E") if pe is None else (
        (PASS if 0 < pe < T["pe"] else FAIL), f"{pe:.1f}", f"< {T['pe']}")

    # current P/E below its own 5-year median (same test as swingTradeChecker)
    m = pe_med or {}
    if m.get("median_pe") and m.get("current_pe") is not None:
        pct = m["pct_from_median"]
        out["P/E<Med"] = ((PASS if m["current_pe"] < m["median_pe"] else FAIL),
                          f"{m['current_pe']:.1f} vs {m['median_pe']:.1f}",
                          f"{pct:+.1f}% vs 5y median P/E ({m.get('source', '')})")
    else:
        out["P/E<Med"] = (NA, "-", "median P/E unavailable")

    # PEG: net-profit CAGR over the longest available window, max 10 yrs
    ni = df["ni"].dropna()
    peg_res = (NA, "-", "not enough history")
    if pe is not None and len(ni) >= 3:
        n = min(10, len(ni) - 1)
        start, end = ni.iloc[-1 - n], ni.iloc[-1]
        if pe <= 0 or start <= 0 or end <= 0 or end <= start:
            peg_res = (FAIL, "n/m", f"loss-making or no profit growth over {n} yrs")
        else:
            cagr = ((end / start) ** (1 / n) - 1) * 100
            peg = pe / cagr
            peg_res = ((PASS if peg < T["peg"] else FAIL), f"{peg:.2f}", f"P/E {pe:.1f} / {cagr:.1f}% NI CAGR ({n}y)")
    out["PEG"] = peg_res

    # PEG 3y: swingTradeChecker definition = current P/E / 3-yr EPS CAGR (screener.in EPS series)
    g = peg3 or {}
    if g.get("peg") is not None:
        out["PEG 3y"] = ((PASS if g["peg"] < T["peg3"] else FAIL), f"{g['peg']:.2f}",
                         f"P/E {g['current_pe']} / {g['eps_cagr_pct']}% EPS CAGR (3y), < {T['peg3']}")
    else:
        out["PEG 3y"] = (NA, "-", "3y EPS growth unavailable or not positive")

    if industrygroup in NO_PB_GROUPS:
        out["P/B"] = (NA, f"{pb:.1f}" if pb else "-", "not needed for IT services")
    else:
        out["P/B"] = (NA, "-", "no P/B") if pb is None else (
            (PASS if 0 < pb < T["pb"] else FAIL), f"{pb:.2f}", f"< {T['pb']}")

    if bank:
        for c in ("D/E", "GPM", "OPM", "ICR", "FCF"):
            out[c] = (NA, "-", "not meaningful for banks")
    else:
        s, v, _ = _all_years(df["de"].tolist(), lambda x: x < T["de"], T["misses"])
        out["D/E"] = (s, v, f"< {T['de']}, latest {df['de'].dropna().iloc[-1]:.2f}" if df["de"].notna().any() else "")

        g = df["gpm"].dropna()
        if len(g) >= 3 and df["sales"].notna().sum() >= 2:
            first, last = g.iloc[:3].mean(), g.iloc[-3:].mean()
            sales = df["sales"].dropna()
            ok = last >= first and sales.iloc[-1] > sales.iloc[0]
            out["GPM"] = ((PASS if ok else FAIL), f"{last:.1f}%", f"first-3y avg {first:.1f}% → last-3y {last:.1f}%, sales up")
        else:
            out["GPM"] = (NA, "-", "gross profit not reported")

        s, v, _ = _all_years(df["opm"].tolist(), lambda x: x > T["opm"], T["misses"])
        out["OPM"] = (s, v, f"> {T['opm']}%")

        s, v, _ = _all_years(df["icr"].tolist(), lambda x: x > T["icr"], T["misses"], df["icr_debtfree"].tolist())
        out["ICR"] = (s, v, f"> {T['icr']}")

        f3 = df.tail(3)
        if f3["fcf"].notna().all() and f3["sales"].notna().all() and f3["sales"].sum():
            r = f3["fcf"].sum() / f3["sales"].sum() * 100
            out["FCF"] = ((PASS if r > T["fcf_sales"] else FAIL), f"{r:.1f}%",
                          f"3y avg FCF {f3['fcf'].mean():,.0f} cr; positive {int((df['fcf'] > 0).sum())}/{df['fcf'].notna().sum()} yrs")
        else:
            out["FCF"] = (NA, "-", "no cash-flow data")

    r = df["roe"].dropna()
    out["ROE"] = (NA, "-", "no data") if r.empty else (
        (PASS if r.iloc[-1] > T["roe"] else FAIL), f"{r.iloc[-1]:.1f}%", f"> {T['roe']}%, 10y avg {r.mean():.1f}%")
    return out


def _median_pe(sym, ratios):
    """5-year median P/E via swingTradeChecker (screener.in chart, yfinance fallback)."""
    try:
        from swingTradeChecker import get_pe_valuation
        return get_pe_valuation(sym, current_pe=ratios.get("pe"))
    except Exception:
        return None


def _peg3(sym):
    """PEG exactly as swingTradeChecker computes it (P/E ÷ 3-yr EPS CAGR)."""
    try:
        from swingTradeChecker import get_peg_ratio
        return get_peg_ratio(sym)
    except Exception:
        return None


def _tickertape_stock(symbol):
    sym = symbol.split(":")[0].upper()
    sid = symbol.split(":")[1] if ":" in symbol else resolve_sid(sym)[0]
    info = _get(INFO_URL.format(sid=sid))
    return (info["info"]["name"], info.get("gic", {}).get("industrygroup", ""),
            fetch_statements(sid), info["ratios"], "tickertape")


def check_stock(symbol, T=None):
    """Full check for one symbol. Default source: screener.in; `SYMBOL:SID` forces Tickertape.
    Returns dict: symbol, name, industry, results, history (DataFrame), score, applicable, source."""
    T = {**DEFAULT_T, **(T or {})}
    sym = symbol.split(":")[0].upper()
    errs = []
    loaders = [_tickertape_stock] if ":" in symbol else [
        lambda s: (lambda r: (r[0], r[1], r[2], r[3], "screener"))(fetch_screener(s)), _tickertape_stock]
    for load in loaders:
        try:
            name, ig, df, ratios, source = load(symbol if ":" in symbol else sym)
            res = evaluate(df, ratios, ig, T, _median_pe(sym, ratios), _peg3(sym))
            break
        except Exception as e:
            errs.append(str(e))
    else:
        return {"symbol": sym, "error": " | ".join(errs)}
    passed = sum(1 for s_, _, _ in res.values() if s_ == PASS)
    applicable = sum(1 for s_, _, _ in res.values() if s_ != NA)
    return {"symbol": sym, "name": name, "industry": ig, "results": res, "history": df,
            "score": passed, "applicable": applicable, "source": source}


if __name__ == "__main__":
    for s in sys.argv[1:] or ["TCS"]:
        r = check_stock(s)
        if "error" in r:
            print(s, "ERROR", r["error"]); continue
        print(f"\n{r['symbol']} — {r['name']}  [{r['industry']}] via {r['source']}  score {r['score']}/{r['applicable']}")
        for c in CRITERIA:
            st, val, det = r["results"][c]
            print(f"  {c:4} {st:5} {val:>10}  {det}")
