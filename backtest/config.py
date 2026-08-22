"""Configuration objects for the swing-trading backtester."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class BrokerageConfig:
    """Cost model applied on entry and exit of every trade."""

    brokerage_pct: float = 0.0
    """Brokerage as a fraction of trade value (e.g. 0.0003 = 0.03%), charged on buy and sell."""

    stt_pct: float = 0.0
    """Securities Transaction Tax as a fraction of trade value, charged on sell only."""

    other_charges_pct: float = 0.0
    """Catch-all for stamp duty / exchange charges / GST, as a fraction of trade value."""

    capital_gains_tax_pct: float = 0.0
    """Tax on realized profit only (applied to positive P&L), as a fraction of profit."""

    def entry_cost(self, trade_value: float) -> float:
        return trade_value * (self.brokerage_pct + self.other_charges_pct)

    def exit_cost(self, trade_value: float) -> float:
        return trade_value * (self.brokerage_pct + self.stt_pct + self.other_charges_pct)

    def tax_on_profit(self, profit: float) -> float:
        return max(profit, 0.0) * self.capital_gains_tax_pct


@dataclass
class StopLossConfig:
    """Optional stop-loss / trailing-stop rules layered on top of the profit target."""

    enabled: bool = False
    stop_loss_pct: float = 0.0
    """Hard stop as a fraction below buy price (e.g. 0.03 = 3%). Ignored if trailing is enabled."""

    trailing: bool = False
    trailing_pct: float = 0.0
    """Trailing stop as a fraction below the highest close/high seen since entry."""


@dataclass
class StrategyConfig:
    """All parameters needed to run a single backtest."""

    ticker: str = "ABBOTINDIA.NS"
    start_date: date = date(2025, 8, 1)
    end_date: date = date(2026, 7, 31)
    investment_amount: float = 100_000.0
    target_pct: float = 0.05
    buy_day_of_month: int = 7

    sip_mode: bool = False
    """If True, a fresh investment_amount is deployed every month on buy_day_of_month
    regardless of whether prior positions are still open (portfolio/SIP mode)."""

    reinvest_profits: bool = False
    """If True, realized profit is added to the next cycle's investment amount instead
    of always redeploying a flat investment_amount."""

    costs: BrokerageConfig = field(default_factory=BrokerageConfig)
    stop_loss: StopLossConfig = field(default_factory=StopLossConfig)

    csv_fallback_path: Path | None = None
    """Optional path to a local OHLCV CSV to use if yfinance download fails."""

    output_dir: Path = field(default_factory=lambda: Path("backtest/output"))

    def __post_init__(self) -> None:
        if not (0 < self.target_pct < 5):
            raise ValueError(f"target_pct must be a small fraction like 0.05, got {self.target_pct}")
        if not (1 <= self.buy_day_of_month <= 28):
            raise ValueError(f"buy_day_of_month must be between 1 and 28, got {self.buy_day_of_month}")
        if self.investment_amount <= 0:
            raise ValueError("investment_amount must be positive")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        self.output_dir = Path(self.output_dir)


SENSITIVITY_TARGETS = [0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10]
