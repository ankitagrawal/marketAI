"""CLI entry point for the swing-trading backtester."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from charts import generate_all_charts
from config import SENSITIVITY_TARGETS, BrokerageConfig, StopLossConfig, StrategyConfig
from metrics import compute_metrics, compute_monthly_stats, identify_optimal_target, run_sensitivity_analysis
from strategy import SwingStrategy, Trade
from utils import download_ohlcv, setup_logging

logger = logging.getLogger("backtest")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest a fixed-amount, sell-at-target swing strategy.")
    parser.add_argument("--ticker", default="ABBOTINDIA", help="Stock ticker, e.g. ABBOTINDIA (Abbott India's NSE symbol)")
    parser.add_argument("--start-date", default="2025-08-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end-date", default="2026-07-31", help="End date YYYY-MM-DD")
    parser.add_argument("--investment", type=float, default=100_000.0, help="Investment amount per trade")
    parser.add_argument("--target-pct", type=float, default=5.0, help="Profit target in percent, e.g. 5 for 5%%")
    parser.add_argument("--buy-day", type=int, default=7, help="Day of month for the first purchase")
    parser.add_argument("--csv-fallback", default=None, help="Path to a local OHLCV CSV fallback")
    parser.add_argument("--output-dir", default="backtest/output", help="Directory for exports and charts")
    parser.add_argument("--sip-mode", action="store_true", help="Deploy a fresh investment every month regardless of open positions")
    parser.add_argument("--reinvest-profits", action="store_true", help="Reinvest realized profits into the next trade")
    parser.add_argument("--brokerage-pct", type=float, default=0.0, help="Brokerage %% per side, e.g. 0.03 for 0.03%%")
    parser.add_argument("--stt-pct", type=float, default=0.0, help="STT %% on sell, e.g. 0.025")
    parser.add_argument("--other-charges-pct", type=float, default=0.0, help="Other charges %% per side")
    parser.add_argument("--tax-pct", type=float, default=0.0, help="Capital gains tax %% on profit")
    parser.add_argument("--stop-loss-pct", type=float, default=None, help="Hard stop-loss %% below buy price")
    parser.add_argument("--trailing-stop-pct", type=float, default=None, help="Trailing stop %% below highest price seen")
    parser.add_argument("--skip-sensitivity", action="store_true", help="Skip the target sensitivity analysis")
    parser.add_argument("--skip-charts", action="store_true", help="Skip chart generation")
    return parser.parse_args(argv)


def build_config(args: argparse.Namespace) -> StrategyConfig:
    stop_loss = StopLossConfig()
    if args.stop_loss_pct is not None:
        stop_loss = StopLossConfig(enabled=True, stop_loss_pct=args.stop_loss_pct / 100)
    elif args.trailing_stop_pct is not None:
        stop_loss = StopLossConfig(enabled=True, trailing=True, trailing_pct=args.trailing_stop_pct / 100)

    costs = BrokerageConfig(
        brokerage_pct=args.brokerage_pct / 100,
        stt_pct=args.stt_pct / 100,
        other_charges_pct=args.other_charges_pct / 100,
        capital_gains_tax_pct=args.tax_pct / 100,
    )

    return StrategyConfig(
        ticker=args.ticker,
        start_date=datetime.strptime(args.start_date, "%Y-%m-%d").date(),
        end_date=datetime.strptime(args.end_date, "%Y-%m-%d").date(),
        investment_amount=args.investment,
        target_pct=args.target_pct / 100,
        buy_day_of_month=args.buy_day,
        sip_mode=args.sip_mode,
        reinvest_profits=args.reinvest_profits,
        costs=costs,
        stop_loss=stop_loss,
        csv_fallback_path=Path(args.csv_fallback) if args.csv_fallback else None,
        output_dir=Path(args.output_dir),
    )


def export_results(
    trades: list[Trade],
    metrics_dict: dict,
    monthly_df: pd.DataFrame,
    sensitivity_df: pd.DataFrame,
    config: StrategyConfig,
    last_close: float,
    optimal_target: float,
) -> None:
    out_dir = Path(config.output_dir) / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    trade_rows = [t.to_dict(last_close) for t in trades]
    trade_df = pd.DataFrame(trade_rows)
    trade_df.to_csv(out_dir / "trade_log.csv", index=False)
    trade_df.to_csv(out_dir / "backtest_results.csv", index=False)

    pd.DataFrame([metrics_dict]).to_csv(out_dir / "performance_metrics.csv", index=False)

    summary = {
        "ticker": config.ticker,
        "start_date": config.start_date.isoformat(),
        "end_date": config.end_date.isoformat(),
        "investment_amount": config.investment_amount,
        "target_pct": config.target_pct * 100,
        "metrics": metrics_dict,
        "monthly_stats": monthly_df.to_dict(orient="records"),
        "sensitivity_analysis": sensitivity_df.to_dict(orient="records"),
        "optimal_target_pct": optimal_target,
    }
    with open(out_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    monthly_df.to_csv(out_dir / "monthly_stats.csv", index=False)
    sensitivity_df.to_csv(out_dir / "sensitivity_analysis.csv", index=False)

    logger.info("Exported CSV/JSON results to %s", out_dir)


def print_report(
    config: StrategyConfig,
    metrics_dict: dict,
    optimal_target: float,
    trades: list[Trade],
    last_close: float,
) -> None:
    print("=" * 60)
    print("Strategy Summary")
    print("=" * 60)
    print(f"Ticker: {config.ticker}")
    print(f"Investment: ₹{config.investment_amount:,.0f}")
    print(f"Target: {config.target_pct * 100:.1f}%")
    print(f"Period: {config.start_date} to {config.end_date}")
    print()
    print(f"Completed Trades: {metrics_dict['num_completed_trades']}")
    print(f"Open Trades: {metrics_dict['num_open_trades']}")
    print(f"Average Holding Days: {metrics_dict['avg_holding_days']:.2f}")
    print(f"Median Holding Days: {metrics_dict['median_holding_days']:.2f}")
    print(f"Maximum Holding Days: {metrics_dict['max_holding_days']}")
    print(f"Minimum Holding Days: {metrics_dict['min_holding_days']}")
    print(f"Total Realized Profit: ₹{metrics_dict['total_realized_profit']:,.2f}")
    print(f"Unrealized Profit: ₹{metrics_dict['unrealized_profit']:,.2f}")
    print(f"Annualized Return: {metrics_dict['annualized_return_pct']:.2f}%")
    print(f"Effective CAGR: {metrics_dict['effective_cagr_pct']:.2f}%")
    print(f"Capital Deployed: ₹{metrics_dict['capital_deployed']:,.2f}")
    print(f"Percentage of Time Invested: {metrics_dict['pct_time_invested']:.2f}%")
    print(f"Average Gain per Trade: ₹{metrics_dict['avg_gain_per_trade']:,.2f}")
    print(f"Win Rate: {metrics_dict['win_rate_pct']:.2f}%")
    print(f"Maximum Wait for Target: {metrics_dict['max_wait_for_target_days']} days")
    print(f"Best Target (by annualized return): {optimal_target:.1f}%")
    print("=" * 60)
    print()

    print("Trade Table")
    print("-" * 60)
    rows = [t.to_dict(last_close) for t in trades]
    if rows:
        df = pd.DataFrame(rows)
        print(df.to_string(index=False))
    else:
        print("No trades executed in this period.")
    print()


def run_backtest(config: StrategyConfig) -> dict:
    """Run the full backtest pipeline and return a dict of all results (used by tests/other callers)."""
    data = download_ohlcv(config.ticker, config.start_date, config.end_date, config.csv_fallback_path)
    last_close = float(data["Close"].iloc[-1])

    strategy = SwingStrategy(config, data)
    trades = strategy.run()

    metrics = compute_metrics(trades, config, last_close)
    monthly_df = compute_monthly_stats(trades)

    return {
        "data": data,
        "trades": trades,
        "metrics": metrics,
        "monthly_df": monthly_df,
        "last_close": last_close,
    }


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    args = parse_args(argv)
    config = build_config(args)

    logger.info("Starting backtest for %s from %s to %s", config.ticker, config.start_date, config.end_date)
    result = run_backtest(config)

    data = result["data"]
    trades = result["trades"]
    metrics = result["metrics"]
    monthly_df = result["monthly_df"]
    last_close = result["last_close"]

    if not args.skip_sensitivity:
        sensitivity_df = run_sensitivity_analysis(config, data, SENSITIVITY_TARGETS)
        optimal_target = identify_optimal_target(sensitivity_df)
    else:
        sensitivity_df = pd.DataFrame()
        optimal_target = config.target_pct * 100

    metrics_dict = metrics.to_dict()
    print_report(config, metrics_dict, optimal_target, trades, last_close)

    export_results(trades, metrics_dict, monthly_df, sensitivity_df, config, last_close, optimal_target)

    if not args.skip_charts:
        generate_all_charts(
            data, trades, config.ticker, config.investment_amount,
            sensitivity_df if not sensitivity_df.empty else pd.DataFrame(
                {"target_pct": [config.target_pct * 100], "completed_trades": [metrics_dict["num_completed_trades"]], "annualized_return_pct": [metrics_dict["annualized_return_pct"]]}
            ),
            config.output_dir,
        )

    logger.info("Backtest complete.")


if __name__ == "__main__":
    main()
