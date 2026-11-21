"""
FCF Valuation — automates the "vS.xlsx" sheet.

Sheet logic (per stock):
    avg FCF      = mean(FCF of last 3 financial years)          [Tickertape, Rs crore]
    intrinsic IV = avg FCF / 0.02        (i.e. 50x FCF, 2% required FCF yield)
    margin IV    = IV * 0.5              (50% margin of safety)
    Market cap   = Tickertape market cap [Rs crore]
    Market cap / IV         (col I)  < 1  -> trading below intrinsic value
    Market cap / margin IV  (col H)  < 1  -> trading below intrinsic value even after 50% haircut
    BANKS (auto-detected): same maths but on NET INCOME (not FCF) with margin 0.35 (--bank-margin).
    Negative avg FCF -> ratios are meaningless (sheet shows negatives) -> flagged NEG FCF.

The sheet converts crore -> million -> trillion; ratios are unit-free so we stay in crore.

Usage:
    python fcfValuation.py GREENPANEL ANUP WPIL
    python fcfValuation.py -f tickers.txt            # one NSE symbol per line
    python fcfValuation.py GREENPANEL --years 3 --rate 0.02 --margin 0.5 --csv out.csv
"""

import argparse
import json
import os
import sys
import threading

import pandas as pd
import requests
import yfinance as yf

HEADERS = {"User-Agent": "Mozilla/5.0"}
SEARCH_URL = "https://api.tickertape.in/search"
INFO_URL = "https://api.tickertape.in/stocks/info/{sid}"
INCOME_URL = "https://api.tickertape.in/stocks/financials/income/{sid}/annual/normal"
CASHFLOW_URL = "https://api.tickertape.in/stocks/financials/cashflow/{sid}/annual/normal"


def _get(url, **params):
    r = requests.get(url, headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(body.get("error") or "tickertape error")
    return body["data"]


SID_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tickertape_sid_cache.json")
_cache_lock = threading.Lock()


def _load_cache():
    try:
        with open(SID_CACHE) as fh:
            return json.load(fh)
    except Exception:
        return {}


def resolve_sid(symbol):
    """NSE symbol -> Tickertape (sid, name), e.g. GREENPANEL -> GREP. Cached on disk so each
    symbol needs the search endpoint at most once."""
    key = symbol.upper()
    hit = _load_cache().get(key)
    if hit:
        return hit["sid"], hit["name"]
    sid, name = _search_sid(symbol)
    with _cache_lock:
        c = _load_cache()
        c[key] = {"sid": sid, "name": name}
        with open(SID_CACHE, "w") as fh:
            json.dump(c, fh, indent=0)
    return sid, name


def _search_sid(symbol):
    data = _get(SEARCH_URL, text=symbol, types="stock")
    stocks = data.get("stocks", [])
    for s in stocks:
        if s.get("ticker", "").upper() == symbol.upper():
            return s["sid"], s["name"]
    # never guess: a wrong company gives a confidently wrong valuation
    cands = ", ".join(f"{s['ticker']}:{s['sid']}" for s in stocks) or "none"
    raise LookupError(f"no exact ticker match (candidates: {cands}); rerun as SYMBOL:SID")


def fetch_series(sid, bank, years):
    """Latest `years` annual values in Rs crore (oldest -> newest): net income for banks, else FCF."""
    if bank:
        rows = _get(INCOME_URL.format(sid=sid), count=10)
        key = "incNinc"
    else:
        rows = _get(CASHFLOW_URL.format(sid=sid), count=10)
        key = "cafFcf"
    # drop trailing-twelve-month rows: they overlap the latest FY and would double-count it
    rows = [r for r in rows if r.get(key) is not None and "TTM" not in r["displayPeriod"].upper()][-years:]
    if len(rows) < 2:
        raise ValueError(f"only {len(rows)} year(s) of data available")
    return [r["displayPeriod"] for r in rows], [r[key] for r in rows]


def tickertape_data(symbol, years):
    if ":" in symbol:                 # explicit override e.g. GREENPANEL:GREP
        symbol, sid = symbol.split(":", 1)
    else:
        sid, _ = resolve_sid(symbol)
    info = _get(INFO_URL.format(sid=sid))
    bank = info.get("gic", {}).get("industrygroup") == "Banks"
    periods, vals = fetch_series(sid, bank, years)
    return info["info"]["name"], periods, vals, info["ratios"]["marketCap"], bank   # mcap in Rs crore


def yf_data(symbol, years):
    """Fallback: Yahoo. Rupees -> crore (1 cr = 1e7)."""
    t = yf.Ticker(f"{symbol.upper()}.NS")
    bank = str((t.info or {}).get("industry", "")).startswith("Banks")
    if bank:
        df, row = t.financials, "Net Income"
    else:
        df, row = t.cashflow, "Free Cash Flow"
    if df is None or df.empty or row not in df.index:
        raise ValueError(f"no {row} on Yahoo")
    ser = df.loc[row].dropna().sort_index().iloc[-years:]
    if len(ser) < 2:
        raise ValueError(f"Yahoo has <2 years of {row}")
    mcap = t.fast_info.get("marketCap")
    if not mcap:
        raise ValueError("no market cap on Yahoo")
    return symbol.upper(), [f"FY{d.year}" for d in ser.index], [v / 1e7 for v in ser.values], mcap / 1e7, bank


def load_data(raw, years):
    """Tickertape first; Yahoo if Tickertape has no match or fewer than `years` of data."""
    symbol = raw.split(":")[0]
    tt_err, tt = None, None
    try:
        tt = tickertape_data(raw, years)
        if len(tt[2]) >= years:
            return (*tt, "tickertape")
    except Exception as e:
        tt_err = e
    try:
        yd = yf_data(symbol, years)
        if tt is None or len(yd[2]) >= len(tt[2]):
            return (tt[0] if tt else yd[0], *yd[1:], "yahoo")
    except Exception as e_yf:
        if tt is None:
            raise RuntimeError(f"tickertape: {tt_err}; yahoo: {e_yf}")
    return (*tt, "tickertape")          # Yahoo no better -> keep short Tickertape history


def value_stock(symbol, years=3, rate=0.02, margin=0.5, bank_margin=0.35):
    out = {"symbol": symbol.split(":")[0].upper()}
    try:
        name, periods, vals, mcap, bank, source = load_data(symbol, years)
    except Exception as e:
        out["verdict"] = f"ERROR: {e}"
        return out

    m = bank_margin if bank else margin          # banks: net income, tighter haircut
    avg = sum(vals) / len(vals)
    iv = avg / rate
    iv_safe = iv * m
    out["source"] = source
    out["basis"] = "NetIncome" if bank else "FCF"
    if len(vals) < years:
        out["note"] = f"only {len(vals)} yrs of data"
    out.update({
        "name": name,
        "years": f"{periods[0]}-{periods[-1]}",
        "yearly_cr": " / ".join(f"{x:.0f}" for x in vals),
        "avg_cr": round(avg, 1),
        "intrinsic_cr": round(iv, 0),
        "margin_x": m,
        "iv_after_margin_cr": round(iv_safe, 0),
        "mcap_cr": round(mcap, 0),
    })
    if avg <= 0:
        out.update({"mcap_to_iv": None, "mcap_to_margin_iv": None,
                    "verdict": "NEG " + ("NET INCOME" if bank else "FCF") + " - skip"})
        return out

    out["mcap_to_iv"] = round(mcap / iv, 2)
    out["mcap_to_margin_iv"] = round(mcap / iv_safe, 2)
    if mcap < iv_safe:
        out["verdict"] = "UNDERVALUED (below margin-of-safety value)"
    elif mcap < iv:
        out["verdict"] = "Below fair value, no margin of safety"
    else:
        out["verdict"] = "OVERVALUED"
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("symbols", nargs="*", help="NSE symbols")
    ap.add_argument("-f", "--file", help="text file, one symbol per line")
    ap.add_argument("--years", type=int, default=3)
    ap.add_argument("--rate", type=float, default=0.02, help="FCF yield used to capitalise (sheet: 0.02)")
    ap.add_argument("--margin", type=float, default=0.5, help="margin-of-safety multiplier (sheet: 0.5)")
    ap.add_argument("--bank-margin", type=float, default=0.35, help="margin multiplier for banks (net income basis)")
    ap.add_argument("--csv", help="also write results to this CSV")
    a = ap.parse_args()

    symbols = list(a.symbols)
    if a.file:
        with open(a.file) as fh:
            symbols += [l.strip() for l in fh if l.strip() and not l.startswith("#")]
    if not symbols:
        ap.error("give at least one symbol")

    rows = []
    for s in symbols:
        print(f"  {s} ...", file=sys.stderr)
        rows.append(value_stock(s, a.years, a.rate, a.margin, a.bank_margin))

    df = pd.DataFrame(rows)
    if "mcap_to_margin_iv" in df:      # cheapest first, errors / negatives last
        df = df.sort_values("mcap_to_margin_iv", na_position="last")
    pd.set_option("display.width", 250, "display.max_columns", None, "display.max_colwidth", 45)
    print(df.to_string(index=False))
    if a.csv:
        df.to_csv(a.csv, index=False)
        print(f"\nSaved {a.csv}")


if __name__ == "__main__":
    main()
