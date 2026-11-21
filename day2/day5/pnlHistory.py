"""
Personal P&L history — parses the broker-exported P&L Excel
(day2/day5/Profitloss/pnl-YA0663.xlsx) into a per-symbol trade summary:
quantity traded, average buy/sell price, realized P&L, and last sell date.

The file only carries aggregate Buy Value / Sell Value / Quantity per symbol
(no per-lot price or buy date), so "buy/sell price" here means the average
over all fills for that symbol in the statement period. Last sell date is
recovered from the DP-charge narrations on the "Other Debits and Credits"
sheet ("DP Charges for Sale of <SYMBOL> on <DATE>").
"""

import os
import re
from collections import defaultdict

import openpyxl

PNL_FILE = os.path.join(os.path.dirname(__file__), "Profitloss", "pnl-YA0663.xlsx")


def _bare_symbol(symbol):
    return symbol.split(".")[0].upper()


def _last_sell_dates(wb):
    dates = defaultdict(list)
    if "Other Debits and Credits" not in wb.sheetnames:
        return dates
    ws = wb["Other Debits and Credits"]
    for row in ws.iter_rows(min_row=16, values_only=True):
        particulars = row[1] if len(row) > 1 else None
        date = row[2] if len(row) > 2 else None
        if not particulars or "Sale of" not in particulars:
            continue
        m = re.search(r"Sale of (\S+) on", particulars)
        if m and date:
            dates[m.group(1).upper()].append(str(date))
    return {sym: max(ds) for sym, ds in dates.items()}


def load_trade_history(path=PNL_FILE):
    """
    Returns {bare_symbol: {...}} with:
      quantity, buy_value, sell_value, avg_buy_price, avg_sell_price,
      realized_pl, realized_pl_pct, last_sell_date (str or None)
    Returns {} if the file is missing or malformed.
    """
    if not os.path.exists(path):
        return {}

    try:
        wb = openpyxl.load_workbook(path, data_only=True)
    except Exception:
        return {}

    if "Equity" not in wb.sheetnames:
        return {}

    ws = wb["Equity"]
    last_sell = _last_sell_dates(wb)

    header_row = None
    for row in ws.iter_rows(min_row=1, values_only=False):
        vals = [c.value for c in row]
        if "Symbol" in vals and "Buy Value" in vals and "Sell Value" in vals:
            header_row = row[0].row
            break
    if header_row is None:
        return {}

    history = {}
    for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
        symbol = row[1]
        if not symbol or not isinstance(symbol, str):
            continue
        try:
            qty        = float(row[3] or 0)
            buy_value  = float(row[4] or 0)
            sell_value = float(row[5] or 0)
            realized   = float(row[6] or 0)
            realized_pct = float(row[7] or 0)
        except (TypeError, ValueError):
            continue

        bare = _bare_symbol(symbol)
        avg_buy  = round(buy_value / qty, 2) if qty else None
        avg_sell = round(sell_value / qty, 2) if qty and sell_value else None

        history[bare] = {
            "symbol":          bare,
            "quantity":        qty,
            "buy_value":       round(buy_value, 2),
            "sell_value":      round(sell_value, 2),
            "avg_buy_price":   avg_buy,
            "avg_sell_price":  avg_sell,
            "realized_pl":     round(realized, 2),
            "realized_pl_pct": round(realized_pct, 2),
            "last_sell_date":  last_sell.get(bare),
        }

    return history


def get_trade_info(symbol, history=None):
    """Look up trade history for a symbol (accepts 'TCS' or 'TCS.NS')."""
    if history is None:
        history = load_trade_history()
    return history.get(_bare_symbol(symbol))


def in_trading_zone(current_price, avg_sell_price, tolerance_pct=3.0):
    """
    True if current_price is at/below avg_sell_price, or within
    `tolerance_pct` above it (i.e. back in the zone you last sold at
    or better — worth another look for re-entry).
    """
    if current_price is None or not avg_sell_price:
        return False
    threshold = avg_sell_price * (1 + tolerance_pct / 100)
    return current_price <= threshold
