"""Chart generation for backtest results."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from strategy import Trade

logger = logging.getLogger("backtest")


def _ensure_dir(path: Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def plot_price_with_trades(data: pd.DataFrame, trades: list[Trade], ticker: str, output_dir: Path) -> Path:
    """Chart 1: stock closing price with buy/sell markers."""
    out_dir = _ensure_dir(output_dir)
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(data.index, data["Close"], color="#4C72B0", linewidth=1, label="Close Price")

    buy_dates = [t.buy_date for t in trades]
    buy_prices = [t.buy_price for t in trades]
    ax.scatter(buy_dates, buy_prices, marker="^", color="green", s=80, zorder=5, label="Buy")

    completed = [t for t in trades if t.status == "COMPLETED"]
    sell_dates = [t.sell_date for t in completed]
    sell_prices = [t.sell_price for t in completed]
    ax.scatter(sell_dates, sell_prices, marker="v", color="red", s=80, zorder=5, label="Sell")

    ax.set_title(f"{ticker} — Price with Buy/Sell Markers")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price (₹)")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()

    path = out_dir / "price_with_trades.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_equity_curve(trades: list[Trade], investment_amount: float, output_dir: Path) -> Path:
    """Chart 2: equity curve across the sequence of trades."""
    out_dir = _ensure_dir(output_dir)
    completed = [t for t in trades if t.status == "COMPLETED"]

    equity = investment_amount
    dates = [completed[0].buy_date] if completed else []
    values = [equity]
    for t in completed:
        equity += t.net_profit or 0.0
        dates.append(t.sell_date)
        values.append(equity)

    fig, ax = plt.subplots(figsize=(14, 6))
    if dates:
        ax.plot(dates, values, color="#55A868", marker="o", markersize=4)
    ax.axhline(investment_amount, color="gray", linestyle="--", linewidth=1, label="Starting Capital")
    ax.set_title("Equity Curve")
    ax.set_xlabel("Date")
    ax.set_ylabel("Equity (₹)")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()

    path = out_dir / "equity_curve.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_holding_days_histogram(trades: list[Trade], output_dir: Path) -> Path:
    """Chart 3: histogram of holding days for completed trades."""
    out_dir = _ensure_dir(output_dir)
    holding_days = [t.holding_days for t in trades if t.status == "COMPLETED" and t.holding_days is not None]

    fig, ax = plt.subplots(figsize=(10, 6))
    if holding_days:
        bins = min(max(len(set(holding_days)), 5), 30)
        ax.hist(holding_days, bins=bins, color="#C44E52", edgecolor="black", alpha=0.8)
    ax.set_title("Distribution of Holding Days to Reach Target")
    ax.set_xlabel("Holding Days")
    ax.set_ylabel("Number of Trades")
    fig.tight_layout()

    path = out_dir / "holding_days_histogram.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_cumulative_profit(trades: list[Trade], output_dir: Path) -> Path:
    """Chart 4: cumulative realized profit over time."""
    out_dir = _ensure_dir(output_dir)
    completed = [t for t in trades if t.status == "COMPLETED"]

    cumulative = 0.0
    dates, values = [], []
    for t in completed:
        cumulative += t.net_profit or 0.0
        dates.append(t.sell_date)
        values.append(cumulative)

    fig, ax = plt.subplots(figsize=(14, 6))
    if dates:
        ax.step(dates, values, where="post", color="#8172B2", linewidth=2)
        ax.fill_between(dates, values, step="post", alpha=0.2, color="#8172B2")
    ax.axhline(0, color="gray", linewidth=0.8)
    ax.set_title("Cumulative Realized Profit")
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative Profit (₹)")
    fig.autofmt_xdate()
    fig.tight_layout()

    path = out_dir / "cumulative_profit.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_target_comparison(sensitivity_df: pd.DataFrame, output_dir: Path) -> Path:
    """Chart 5: bar/line comparison of annualized return and trade count across targets."""
    out_dir = _ensure_dir(output_dir)
    fig, ax1 = plt.subplots(figsize=(12, 6))

    x = sensitivity_df["target_pct"].astype(str)
    ax1.bar(x, sensitivity_df["completed_trades"], color="#4C72B0", alpha=0.6, label="Completed Trades")
    ax1.set_xlabel("Target %")
    ax1.set_ylabel("Completed Trades", color="#4C72B0")
    ax1.tick_params(axis="y", labelcolor="#4C72B0")

    ax2 = ax1.twinx()
    ax2.plot(x, sensitivity_df["annualized_return_pct"], color="#C44E52", marker="o", linewidth=2, label="Annualized Return %")
    ax2.set_ylabel("Annualized Return %", color="#C44E52")
    ax2.tick_params(axis="y", labelcolor="#C44E52")

    ax1.set_title("Target Sensitivity: Trade Count vs Annualized Return")
    fig.tight_layout()

    path = out_dir / "target_comparison.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_trade_duration_timeline(trades: list[Trade], output_dir: Path) -> Path:
    """Chart 6: horizontal timeline of each trade's buy-to-sell duration."""
    out_dir = _ensure_dir(output_dir)
    fig, ax = plt.subplots(figsize=(14, max(4, 0.4 * len(trades))))

    for i, t in enumerate(trades):
        end = t.sell_date if t.sell_date is not None else t.buy_date
        color = "#55A868" if t.status == "COMPLETED" else "#DD8452"
        ax.barh(i, (end - t.buy_date).days or 1, left=t.buy_date, color=color, height=0.6)

    ax.set_yticks(range(len(trades)))
    ax.set_yticklabels([f"Trade {i + 1}" for i in range(len(trades))])
    ax.set_xlabel("Date")
    ax.set_title("Trade Duration Timeline (green=completed, orange=open)")
    fig.autofmt_xdate()
    fig.tight_layout()

    path = out_dir / "trade_duration_timeline.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def generate_all_charts(
    data: pd.DataFrame,
    trades: list[Trade],
    ticker: str,
    investment_amount: float,
    sensitivity_df: pd.DataFrame,
    output_dir: Path,
) -> list[Path]:
    """Generate and save all six charts, returning their file paths."""
    charts_dir = _ensure_dir(Path(output_dir) / "charts")
    paths = [
        plot_price_with_trades(data, trades, ticker, charts_dir),
        plot_equity_curve(trades, investment_amount, charts_dir),
        plot_holding_days_histogram(trades, charts_dir),
        plot_cumulative_profit(trades, charts_dir),
        plot_target_comparison(sensitivity_df, charts_dir),
        plot_trade_duration_timeline(trades, charts_dir),
    ]
    logger.info("Saved %d charts to %s", len(paths), charts_dir)
    return paths
