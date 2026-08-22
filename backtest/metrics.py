"""Performance metrics, sensitivity analysis, and monthly statistics."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from config import StrategyConfig
from strategy import SwingStrategy, Trade

logger = logging.getLogger("backtest")


@dataclass
class PerformanceMetrics:
    """Aggregate performance metrics computed from a list of trades."""

    num_completed_trades: int
    num_open_trades: int
    avg_holding_days: float
    median_holding_days: float
    max_holding_days: int
    min_holding_days: int
    total_realized_profit: float
    unrealized_profit: float
    annualized_return_pct: float
    capital_deployed: float
    pct_time_invested: float
    avg_gain_per_trade: float
    win_rate_pct: float
    max_wait_for_target_days: int
    effective_cagr_pct: float

    def to_dict(self) -> dict:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in self.__dict__.items()}


def compute_metrics(
    trades: list[Trade],
    config: StrategyConfig,
    last_close: float,
) -> PerformanceMetrics:
    """Compute the full performance metrics suite for a completed backtest run."""
    completed = [t for t in trades if t.status == "COMPLETED"]
    open_trades = [t for t in trades if t.status == "OPEN"]

    holding_days = [t.holding_days for t in completed if t.holding_days is not None]
    profits = [t.net_profit for t in completed if t.net_profit is not None]

    total_realized_profit = sum(profits) if profits else 0.0
    unrealized_profit = sum(t.unrealized_pnl(last_close) for t in open_trades)

    capital_deployed = sum(t.investment for t in trades)
    wins = [p for p in profits if p > 0]
    win_rate = (len(wins) / len(profits) * 100) if profits else 0.0

    total_span_days = (config.end_date - config.start_date).days or 1
    invested_days = sum(holding_days) if holding_days else 0
    pct_time_invested = min(invested_days / total_span_days * 100, 100.0)

    years = total_span_days / 365.25
    total_invested_capital = config.investment_amount
    net_return_pct = (
        (total_realized_profit + unrealized_profit) / total_invested_capital * 100
        if total_invested_capital
        else 0.0
    )
    annualized_return_pct = (net_return_pct / years) if years > 0 else 0.0

    ending_value = total_invested_capital + total_realized_profit + unrealized_profit
    if total_invested_capital > 0 and years > 0 and ending_value > 0:
        effective_cagr_pct = ((ending_value / total_invested_capital) ** (1 / years) - 1) * 100
    else:
        effective_cagr_pct = 0.0

    return PerformanceMetrics(
        num_completed_trades=len(completed),
        num_open_trades=len(open_trades),
        avg_holding_days=float(np.mean(holding_days)) if holding_days else 0.0,
        median_holding_days=float(np.median(holding_days)) if holding_days else 0.0,
        max_holding_days=int(np.max(holding_days)) if holding_days else 0,
        min_holding_days=int(np.min(holding_days)) if holding_days else 0,
        total_realized_profit=total_realized_profit,
        unrealized_profit=unrealized_profit,
        annualized_return_pct=annualized_return_pct,
        capital_deployed=capital_deployed,
        pct_time_invested=pct_time_invested,
        avg_gain_per_trade=float(np.mean(profits)) if profits else 0.0,
        win_rate_pct=win_rate,
        max_wait_for_target_days=int(np.max(holding_days)) if holding_days else 0,
        effective_cagr_pct=effective_cagr_pct,
    )


def run_sensitivity_analysis(
    base_config: StrategyConfig,
    data: pd.DataFrame,
    targets: list[float],
) -> pd.DataFrame:
    """Re-run the strategy across a list of profit targets and compare results."""
    rows = []
    last_close = float(data["Close"].iloc[-1])

    for target in targets:
        cfg = StrategyConfig(
            ticker=base_config.ticker,
            start_date=base_config.start_date,
            end_date=base_config.end_date,
            investment_amount=base_config.investment_amount,
            target_pct=target,
            buy_day_of_month=base_config.buy_day_of_month,
            sip_mode=base_config.sip_mode,
            reinvest_profits=base_config.reinvest_profits,
            costs=base_config.costs,
            stop_loss=base_config.stop_loss,
            csv_fallback_path=base_config.csv_fallback_path,
            output_dir=base_config.output_dir,
        )
        strategy = SwingStrategy(cfg, data)
        trades = strategy.run()
        metrics = compute_metrics(trades, cfg, last_close)

        years = (cfg.end_date - cfg.start_date).days / 365.25
        annual_profit = (
            (metrics.total_realized_profit + metrics.unrealized_profit) / years if years > 0 else 0.0
        )

        rows.append(
            {
                "target_pct": round(target * 100, 2),
                "completed_trades": metrics.num_completed_trades,
                "avg_holding_days": round(metrics.avg_holding_days, 2),
                "annual_profit": round(annual_profit, 2),
                "annualized_return_pct": round(metrics.annualized_return_pct, 2),
                "capital_utilization_pct": round(metrics.pct_time_invested, 2),
            }
        )

    df = pd.DataFrame(rows)
    logger.info("Sensitivity analysis complete for %d targets", len(targets))
    return df


def identify_optimal_target(sensitivity_df: pd.DataFrame) -> float:
    """Pick the target with the highest annualized return as the 'optimal' target."""
    if sensitivity_df.empty:
        return 0.0
    best_row = sensitivity_df.loc[sensitivity_df["annualized_return_pct"].idxmax()]
    return float(best_row["target_pct"])


def compute_monthly_stats(trades: list[Trade]) -> pd.DataFrame:
    """Aggregate completed trades into monthly trade count, avg days-to-target, profit, ROI."""
    completed = [t for t in trades if t.status == "COMPLETED"]
    if not completed:
        return pd.DataFrame(
            columns=["month", "trades", "avg_days_to_target", "monthly_profit", "monthly_roi_pct"]
        )

    records = [
        {
            "month": t.sell_date.strftime("%Y-%m"),
            "holding_days": t.holding_days,
            "profit": t.net_profit,
            "investment": t.investment,
        }
        for t in completed
    ]
    df = pd.DataFrame(records)
    grouped = df.groupby("month").agg(
        trades=("profit", "count"),
        avg_days_to_target=("holding_days", "mean"),
        monthly_profit=("profit", "sum"),
        invested=("investment", "sum"),
    )
    grouped["monthly_roi_pct"] = grouped["monthly_profit"] / grouped["invested"] * 100
    grouped = grouped.drop(columns=["invested"]).reset_index()
    grouped["avg_days_to_target"] = grouped["avg_days_to_target"].round(2)
    grouped["monthly_profit"] = grouped["monthly_profit"].round(2)
    grouped["monthly_roi_pct"] = grouped["monthly_roi_pct"].round(2)
    return grouped
