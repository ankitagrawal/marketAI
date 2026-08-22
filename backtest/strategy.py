"""Core swing-trading strategy engine: buy fixed amount, sell at profit target."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import pandas as pd

from config import StrategyConfig
from utils import first_buy_date_for_month, next_trading_day_on_or_after

logger = logging.getLogger("backtest")


@dataclass
class Trade:
    """Record of a single buy-to-sell (or still-open) cycle."""

    buy_date: pd.Timestamp
    buy_price: float
    shares: int
    investment: float
    target_price: float
    sell_date: pd.Timestamp | None = None
    sell_price: float | None = None
    status: str = "OPEN"  # "COMPLETED" or "OPEN"
    entry_cost: float = 0.0
    exit_cost: float = 0.0
    tax: float = 0.0
    exit_reason: str = "TARGET"  # "TARGET", "STOP_LOSS", "TRAILING_STOP", "OPEN"

    @property
    def holding_days(self) -> int | None:
        if self.sell_date is None:
            return None
        return (self.sell_date - self.buy_date).days

    @property
    def gross_profit(self) -> float | None:
        if self.sell_price is None:
            return None
        return (self.sell_price - self.buy_price) * self.shares

    @property
    def net_profit(self) -> float | None:
        gp = self.gross_profit
        if gp is None:
            return None
        return gp - self.entry_cost - self.exit_cost - self.tax

    @property
    def profit_pct(self) -> float | None:
        if self.sell_price is None:
            return None
        return (self.sell_price - self.buy_price) / self.buy_price

    def unrealized_pnl(self, last_close: float) -> float:
        return (last_close - self.buy_price) * self.shares

    def to_dict(self, last_close: float | None = None) -> dict:
        realized = self.status == "COMPLETED"
        return {
            "buy_date": self.buy_date.date().isoformat(),
            "sell_date": self.sell_date.date().isoformat() if self.sell_date else None,
            "buy_price": round(self.buy_price, 2),
            "sell_price": round(self.sell_price, 2) if self.sell_price else None,
            "shares": self.shares,
            "investment": round(self.investment, 2),
            "target_price": round(self.target_price, 2),
            "profit": round(self.net_profit, 2) if realized and self.net_profit is not None else (
                round(self.unrealized_pnl(last_close), 2) if last_close is not None else None
            ),
            "profit_pct": round(self.profit_pct * 100, 2) if realized and self.profit_pct is not None else None,
            "holding_days": self.holding_days,
            "status": self.status,
            "exit_reason": self.exit_reason,
        }


class SwingStrategy:
    """Runs the fixed-amount, sell-at-target swing strategy over historical OHLCV data."""

    def __init__(self, config: StrategyConfig, data: pd.DataFrame):
        self.config = config
        self.data = data
        self.trades: list[Trade] = []

    def run(self) -> list[Trade]:
        """Execute the full backtest and return the list of trades (completed + open)."""
        cfg = self.config
        idx = self.data.index
        end_ts = pd.Timestamp(cfg.end_date)

        buy_date = first_buy_date_for_month(idx, cfg.start_date.year, cfg.start_date.month, cfg.buy_day_of_month)
        if buy_date is None or buy_date > end_ts:
            logger.warning("No valid first buy date found in range for %s", cfg.ticker)
            return self.trades

        current_investment = cfg.investment_amount

        while buy_date is not None and buy_date <= end_ts:
            trade = self._open_trade(buy_date, current_investment)
            if trade is None:
                break
            self._simulate_exit(trade, end_ts)
            self.trades.append(trade)

            if trade.status == "OPEN":
                break

            if cfg.reinvest_profits:
                current_investment = cfg.investment_amount + (trade.net_profit or 0.0)
                current_investment = max(current_investment, cfg.investment_amount * 0.1)
            else:
                current_investment = cfg.investment_amount

            next_buy = next_trading_day_on_or_after(
                idx, trade.sell_date + pd.Timedelta(days=1)
            )
            buy_date = next_buy

        return self.trades

    def _open_trade(self, buy_date: pd.Timestamp, investment_amount: float) -> Trade | None:
        cfg = self.config
        buy_price = float(self.data.loc[buy_date, "Close"])
        shares = math.floor(investment_amount / buy_price)
        if shares <= 0:
            logger.warning(
                "Investment amount %.2f too small to buy even 1 share of %s at %.2f on %s",
                investment_amount, cfg.ticker, buy_price, buy_date.date(),
            )
            return None

        actual_investment = shares * buy_price
        target_price = buy_price * (1 + cfg.target_pct)
        entry_cost = cfg.costs.entry_cost(actual_investment)

        return Trade(
            buy_date=buy_date,
            buy_price=buy_price,
            shares=shares,
            investment=actual_investment,
            target_price=target_price,
            entry_cost=entry_cost,
        )

    def _simulate_exit(self, trade: Trade, end_ts: pd.Timestamp) -> None:
        cfg = self.config
        idx = self.data.index
        future = idx[(idx > trade.buy_date) & (idx <= end_ts)]

        highest_seen = trade.buy_price
        stop_price = None
        if cfg.stop_loss.enabled and not cfg.stop_loss.trailing:
            stop_price = trade.buy_price * (1 - cfg.stop_loss.stop_loss_pct)

        for day in future:
            row = self.data.loc[day]
            high, low = float(row["High"]), float(row["Low"])
            highest_seen = max(highest_seen, high)

            if cfg.stop_loss.enabled and cfg.stop_loss.trailing:
                stop_price = highest_seen * (1 - cfg.stop_loss.trailing_pct)

            if high >= trade.target_price:
                self._close_trade(trade, day, trade.target_price, "TARGET")
                return

            if stop_price is not None and low <= stop_price:
                self._close_trade(trade, day, stop_price, "STOP_LOSS" if not cfg.stop_loss.trailing else "TRAILING_STOP")
                return

        trade.status = "OPEN"

    def _close_trade(self, trade: Trade, sell_date: pd.Timestamp, sell_price: float, reason: str) -> None:
        cfg = self.config
        trade.sell_date = sell_date
        trade.sell_price = sell_price
        trade.status = "COMPLETED"
        trade.exit_reason = reason
        trade.exit_cost = cfg.costs.exit_cost(sell_price * trade.shares)
        gross = (sell_price - trade.buy_price) * trade.shares
        trade.tax = cfg.costs.tax_on_profit(gross - trade.entry_cost - trade.exit_cost)
