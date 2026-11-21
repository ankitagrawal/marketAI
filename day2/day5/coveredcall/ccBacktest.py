"""
Covered-call strategy lab (NSE large caps) - synthetic Black-Scholes backtest.

Option prices are MODELLED (yfinance has no NSE option history):
  sigma = 30d realised vol * IV_MULT, r = 6.5%, q = 0.  Treat results as relative
  comparisons between rule-sets, not forecasts.

Cycle = 21 trading days (~monthly expiry). Costs: 0.10% on every stock buy/sell,
0.10% on option premium, 0.15% STT on intrinsic value if the short call is assigned.
"""
import sys
import numpy as np
import pandas as pd
import yfinance as yf
from math import log, sqrt, exp, erf


class norm:
    @staticmethod
    def cdf(x):
        return 0.5 * (1 + erf(x / sqrt(2)))

TICKERS = ["RELIANCE", "HDFCBANK", "INFY", "TCS", "ITC", "ICICIBANK",
           "LT", "HINDUNILVR", "SBIN", "AXISBANK"]
START, CYCLE, R = "2013-01-01", 21, 0.065
IV_MULT = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
COST_STK, COST_OPT, STT_EX = 0.001, 0.001, 0.0015


def bs(S, K, T, sig, call=True):
    d1 = (log(S / K) + (R + sig**2 / 2) * T) / (sig * sqrt(T))
    d2 = d1 - sig * sqrt(T)
    if call:
        return S * norm.cdf(d1) - K * exp(-R * T) * norm.cdf(d2)
    return K * exp(-R * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def strike_for_delta(S, T, sig, delta, step=0.0025):
    """Walk strike up from spot until call delta <= target (rounded to ~0.25% grid)."""
    K = S
    for _ in range(200):
        d1 = (log(S / K) + (R + sig**2 / 2) * T) / (sig * sqrt(T))
        if norm.cdf(d1) <= delta:
            break
        K *= 1 + step
    return K


def load(t):
    df = yf.download(t + ".NS", start=START, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    c = df["Close"].dropna()
    return pd.DataFrame({"c": c,
                         "vol": np.log(c).diff().rolling(30).std() * sqrt(252),
                         "ma50": c.rolling(50).mean(),
                         "ma200": c.rolling(200).mean()}).dropna()


def run(df, delta=None, trend=False, put_pct=None, tp=None):
    """Returns per-cycle net return series (fraction of start-of-cycle stock value).
    delta: call delta (None = buy&hold); trend: stay in cash if close<200DMA;
    put_pct: buy put at that moneyness (collar); tp: buy back call at tp% of premium captured
    (checked at cycle mid-point, i.e. one look)."""
    idx, rets, prem = list(df.index), [], []
    for i in range(0, len(idx) - CYCLE, CYCLE):
        S0, S1 = df.c.iloc[i], df.c.iloc[i + CYCLE]
        sig, T = df.vol.iloc[i] * IV_MULT, CYCLE / 252
        if trend and S0 < df.ma200.iloc[i]:
            rets.append(R * CYCLE / 252); prem.append(0); continue     # parked in cash
        if delta is None:
            rets.append(S1 / S0 - 1); prem.append(0); continue
        K = strike_for_delta(S0, T, sig, delta)
        p = bs(S0, K, T, sig)
        pnl = (S1 - S0) - max(S1 - K, 0) + p
        # one mid-cycle look: if premium decayed to (1-tp) of original, close early & keep stock
        if tp:
            Sm = df.c.iloc[i + CYCLE // 2]
            pm = bs(Sm, K, T / 2, sig)
            if p - pm >= tp * p:
                pnl = (S1 - S0) + (p - pm)
        cost = p * COST_OPT
        if S1 > K:                                   # assigned -> sell at K, buy back at S1
            cost += K * COST_STK + S1 * COST_STK + max(S1 - K, 0) * STT_EX
        if put_pct:
            Kp = S0 * put_pct
            pp = bs(S0, Kp, T, sig, call=False)
            pnl += max(Kp - S1, 0) - pp
            cost += pp * COST_OPT
        rets.append((pnl - cost) / S0); prem.append(p / S0)
    return pd.Series(rets), pd.Series(prem)


def stats(r, prem):
    eq = (1 + r).cumprod()
    yrs = len(r) * CYCLE / 252
    dd = (eq / eq.cummax() - 1).min()
    return {"CAGR%": (eq.iloc[-1] ** (1 / yrs) - 1) * 100,
            "Vol%": r.std() * sqrt(252 / CYCLE) * 100,
            "MaxDD%": dd * 100,
            "Worst cyc%": r.min() * 100,
            "Win cyc%": (r > 0).mean() * 100,
            "Avg prem%/cyc": prem.mean() * 100,
            "Ret/DD": ((eq.iloc[-1] ** (1 / yrs) - 1) / abs(dd))}


STRATS = {
    "Buy&Hold":              dict(),
    "CC 0.30d":              dict(delta=.30),
    "CC 0.20d":              dict(delta=.20),
    "CC 0.20d +200DMA":      dict(delta=.20, trend=True),
    "CC 0.20d +TP50":        dict(delta=.20, tp=.5),
    "Collar .20c/92%put":    dict(delta=.20, put_pct=.92),
    "CC .25d +200DMA +TP50": dict(delta=.25, trend=True, tp=.5),
}

if __name__ == "__main__":
    data = {t: load(t) for t in TICKERS}
    out = {}
    for name, kw in STRATS.items():
        rs, ps = [], []
        for t, df in data.items():
            r, p = run(df, **kw); rs.append(r.reset_index(drop=True)); ps.append(p.reset_index(drop=True))
        n = min(map(len, rs))
        rp = pd.concat([x.iloc[-n:].reset_index(drop=True) for x in rs], axis=1).mean(axis=1)
        pp = pd.concat([x.iloc[-n:].reset_index(drop=True) for x in ps], axis=1).mean(axis=1)
        out[name] = stats(rp, pp)
    print(f"IV multiplier = {IV_MULT}, cycles ~{n}, years ~{n*CYCLE/252:.1f}")
    print(pd.DataFrame(out).T.round(2).to_string())
