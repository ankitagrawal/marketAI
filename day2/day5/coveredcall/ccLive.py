"""
Live covered-call / collar planner from the NSE option chain.

  python ccLive.py HCLTECH                 # nearest expiry, lot inferred from chain
  python ccLive.py HCLTECH 23-Nov-2026 400 # expiry + explicit lot size (verify on NSE!)

Rules (from the backtest): sell ~0.20-0.25 delta monthly call, buy a put ~8% below spot,
sell at BID / buy at ASK (conservative fills), skip illiquid strikes.
Educational tool, not advice. NSE's endpoint is unofficial and may change or rate-limit.
"""
import sys, math, datetime as dt
from math import log, sqrt, exp, erf, gcd
from functools import reduce
import requests

R = 0.065
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Accept": "application/json", "Referer": "https://www.nseindia.com/option-chain"}
N = lambda x: 0.5 * (1 + erf(x / sqrt(2)))


def fetch(symbol, expiry=None):
    s = requests.Session(); s.headers.update(UA)
    s.get("https://www.nseindia.com/option-chain", timeout=20)
    url = f"https://www.nseindia.com/api/option-chain-v3?type=Equity&symbol={symbol}"
    expiries = s.get(f"https://www.nseindia.com/api/option-chain-contract-info?symbol={symbol}",
                     timeout=20).json().get("expiryDates", [])
    if not expiries:
        raise RuntimeError(f"no expiries returned for {symbol} (not an F&O stock, or NSE is throttling)")
    expiry = expiry or expiries[0]
    d = s.get(f"{url}&expiry={expiry}", timeout=20).json()
    if "records" not in d:
        raise RuntimeError(f"empty chain for {symbol} {expiry} (check expiry/symbol, or retry shortly)")
    d["records"]["expiryDates"] = expiries
    return d["records"], expiry


def call_delta(S, K, T, iv):
    if iv <= 0 or T <= 0: return float("nan")
    return N((log(S / K) + (R + iv**2 / 2) * T) / (iv * sqrt(T)))


def parse(rec, expiry):
    S = rec["underlyingValue"]
    exp_d = dt.datetime.strptime(expiry, "%d-%b-%Y").date()
    asof = dt.datetime.strptime(rec["timestamp"], "%d-%b-%Y %H:%M:%S").date()
    dte = (exp_d - asof).days
    rows, qty = [], []
    for r in rec["data"]:
        k = r["strikePrice"] if "strikePrice" in r else None
        for side in ("CE", "PE"):
            o = r.get(side)
            if o and o.get("strikePrice"):
                qty += [q for q in (o["buyQuantity1"], o["sellQuantity1"]) if q]
        rows.append(r)
    lot = reduce(gcd, qty) if qty else None
    return S, dte, rows, lot


def pnl_scenarios(S0, Kc, call_bid, Kp, put_ask):
    out = []
    for pct in (-20, -15, -10, -8, -5, 0, 3, 5, 8, 12):
        S1 = S0 * (1 + pct / 100)
        stock = S1 - S0
        callp = call_bid - max(S1 - Kc, 0)
        cc = stock + callp
        col = cc + (max(Kp - S1, 0) - put_ask if Kp else 0)
        out.append((pct, S1, cc, col))
    return out


def main():
    symbol = sys.argv[1].upper() if len(sys.argv) > 1 else "HCLTECH"
    expiry = sys.argv[2] if len(sys.argv) > 2 else None
    rec, expiry = fetch(symbol, expiry)
    S, dte, rows, lot_inf = parse(rec, expiry)
    lot = int(sys.argv[3]) if len(sys.argv) > 3 else lot_inf
    T = dte / 365
    print(f"\n{symbol}  spot {S:.2f}  expiry {expiry} ({dte} days)  data {rec['timestamp']}")
    print(f"lot size: {lot}" + ("  (inferred from order-book quantities - VERIFY on NSE)" if len(sys.argv) <= 3 else ""))

    calls = []
    for r in rows:
        c = r.get("CE")
        if not c or not c.get("strikePrice") or not c["buyPrice1"] or not c["sellPrice1"]: continue
        K, iv = c["strikePrice"], c["impliedVolatility"] / 100
        if K <= S: continue
        bid, ask = c["buyPrice1"], c["sellPrice1"]
        mid = (bid + ask) / 2
        calls.append(dict(K=K, iv=iv * 100, delta=call_delta(S, K, T, iv), bid=bid, ask=ask,
                          spread=(ask - bid) / mid * 100, oi=c["openInterest"], vol=c["totalTradedVolume"],
                          otm=(K / S - 1) * 100, yld=bid / S * 100, ann=bid / S * 100 * 365 / dte))
    print("\nCall candidates (OTM, two-sided market):")
    print(" Strike  OTM%  Delta  Bid    Ask   Spr%   OI    Vol   Prem%  Ann%")
    cand = [c for c in calls if 0.10 <= c["delta"] <= 0.40]
    for c in cand:
        print(f" {c['K']:6.0f} {c['otm']:5.1f} {c['delta']:5.2f} {c['bid']:6.2f} {c['ask']:6.2f} "
              f"{c['spread']:5.1f} {c['oi']:6.0f} {c['vol']:5.0f} {c['yld']:5.2f} {c['ann']:5.1f}")

    liquid = [c for c in cand if c["spread"] <= 15 and c["oi"] >= 100]
    pick = min(liquid or cand, key=lambda c: abs(c["delta"] - 0.22))
    print(f"\n=> chosen call: {pick['K']:.0f} CE  (delta {pick['delta']:.2f}, bid {pick['bid']})")

    # protective put ~8% below spot, buy at ask, need real liquidity
    puts = []
    for r in rows:
        p = r.get("PE")
        if p and p.get("strikePrice") and p["sellPrice1"] and p["buyPrice1"] and p["strikePrice"] < S:
            puts.append(p)
    tgt = S * 0.92
    puts = [p for p in puts if (p["sellPrice1"] - p["buyPrice1"]) / ((p["sellPrice1"] + p["buyPrice1"]) / 2) <= 0.25] or puts
    pp = min(puts, key=lambda p: abs(p["strikePrice"] - tgt)) if puts else None
    Kp, put_ask = (pp["strikePrice"], pp["sellPrice1"]) if pp else (None, 0)
    if pp:
        print(f"=> chosen put:  {Kp:.0f} PE  ({(Kp/S-1)*100:.1f}% from spot, ask {put_ask}, OI {pp['openInterest']})")

    Kc, cb = pick["K"], pick["bid"]
    print("\n" + "-" * 60)
    for name, kp, pa in (("PLAIN COVERED CALL", None, 0), ("COLLAR (CC + protective put)", Kp, put_ask)):
        credit = cb - pa
        maxp = (Kc - S) + credit
        be = S - credit
        maxl = (S - kp) - credit if kp else S - credit
        print(f"{name}\n  net premium/share {credit:6.2f} ({credit/S*100:.2f}% of spot, {credit/S*100*365/dte:.1f}% annualised)"
              f"\n  max profit {maxp:7.2f}/sh ({maxp/S*100:.2f}%)  break-even {be:.2f}"
              f"\n  max loss   {maxl:7.2f}/sh ({maxl/S*100:.2f}%)"
              + (f"\n  per lot ({lot}): premium Rs {credit*lot:,.0f}, max profit Rs {maxp*lot:,.0f}, max loss Rs {maxl*lot:,.0f}" if lot else "")
              + "\n")
    print("Expiry P&L per share (move from spot):")
    print("  Move%   Spot    CoveredCall   Collar   | per lot collar (Rs)")
    for pct, S1, cc, col in pnl_scenarios(S, Kc, cb, Kp, put_ask):
        print(f"  {pct:+4d}  {S1:7.1f}  {cc:10.2f}  {col:9.2f}   | {col*lot:>12,.0f}" if lot else f"  {pct:+4d}  {S1:7.1f}  {cc:10.2f}  {col:9.2f}")
    print("\nNot included: brokerage, STT 0.15% on intrinsic if assigned, margin/interest, taxes. Check earnings dates before selling.")


if __name__ == "__main__":
    main()
