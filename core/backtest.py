"""
core/backtest.py
Full backtesting engine that simulates the trading strategy
against historical data with the 3-bucket system.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from math import sqrt
import json

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False

try:
    import ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False

from core.signals import generate_all_signals, calculate_combined_score, vix_filter, calculate_atr


class BacktestEngine:
    """Simulates the trading strategy against historical data."""

    def __init__(self, initial_capital: float = 100000,
                 dividend_pct: float = 0.35,
                 growth_pct: float = 0.35,
                 penny_pct: float = 0.30,
                 min_dividend_yield: float = 0.03,
                 penny_price_threshold: float = 5.0,
                 stop_loss_pct: float = 0.05,
                 take_profit_pct: float = 0.10,
                 max_positions: int = 5,
                 max_position_pct: float = 0.08,
                 commission_pct: float = 0.001,
                 slippage_pct: float = 0.0005):
        self.initial_capital = initial_capital
        self.dividend_pct = dividend_pct
        self.growth_pct = growth_pct
        self.penny_pct = penny_pct
        self.min_dividend_yield = min_dividend_yield
        self.penny_price_threshold = penny_price_threshold
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_positions = max_positions
        self.max_position_pct = max_position_pct
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct

    def classify_stock(self, symbol: str, price: float, div_yield: float = None) -> str:
        """Classify a stock into a bucket based on price and dividend yield."""
        if price < self.penny_price_threshold:
            return "penny"
        if div_yield is not None and div_yield >= self.min_dividend_yield:
            return "dividend"
        return "growth"

    def get_dividend_yield(self, symbol: str) -> Optional[float]:
        """Try to get dividend yield from yfinance."""
        if not YF_AVAILABLE:
            return None
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info or {}
            div_yield = info.get('dividendYield')
            return div_yield if div_yield and div_yield > 0 else None
        except Exception:
            return None

    def run_backtest(self, symbols: List[str], start_date: str, end_date: str,
                     strategy: str = "combined") -> Dict:
        """Run a full backtest simulation."""
        results = {
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": self.initial_capital,
            "symbols_tested": len(symbols),
            "strategy": strategy,
            "trades": [],
            "equity_curve": [],
            "bucket_returns": {"dividend": [], "growth": [], "penny": []},
            "metrics": {},
            "status": "starting",
        }

        # Download data
        print(f"[Backtest] Downloading data for {len(symbols)} symbols...")
        price_data = {}
        div_yields = {}
        failed = []

        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(start=start_date, end=end_date)
                if df is not None and len(df) >= 50:
                    df.columns = [c.lower() for c in df.columns]
                    # Strip timezone to avoid tz-aware vs tz-naive comparison errors
                    df.index = df.index.tz_localize(None)
                    price_data[symbol] = df
                    div_yields[symbol] = self.get_dividend_yield(symbol)
                else:
                    failed.append(symbol)
            except Exception:
                failed.append(symbol)

        results["symbols_downloaded"] = len(price_data)
        results["symbols_failed"] = failed

        if not price_data:
            results["status"] = "error"
            results["error"] = "No data downloaded"
            return results

        # Get date range (all tz-naive now)
        dates = sorted(set(date for df in price_data.values() for date in df.index))
        if not dates:
            results["status"] = "error"
            results["error"] = "No dates in data"
            return results

        # Simulate trading
        cash = self.initial_capital
        positions = {}
        closed_trades = []
        equity_curve = []
        bucket_pnl = {"dividend": 0, "growth": 0, "penny": 0}

        print(f"[Backtest] Simulating {len(dates)} trading days...")

        for i, date in enumerate(dates):
            # Skip first 50 days (need indicators to warm up)
            if i < 50:
                continue

            # Calculate current equity
            positions_value = sum(
                p["qty"] * self._get_price(price_data, p["symbol"], date)
                for p in positions.values()
            )
            current_equity = cash + positions_value

            equity_curve.append({
                "date": date.strftime("%Y-%m-%d"),
                "equity": current_equity,
                "cash": cash,
                "positions_value": positions_value,
                "num_positions": len(positions),
            })

            # Check stop-losses and take-profits
            to_close = []
            for symbol, pos in list(positions.items()):
                current_price = self._get_price(price_data, symbol, date)
                if current_price <= 0:
                    continue

                pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"]

                # Stop loss
                if pnl_pct <= -(self.stop_loss_pct):
                    to_close.append((symbol, "stop_loss", pnl_pct))
                # Take profit
                elif pnl_pct >= self.take_profit_pct:
                    to_close.append((symbol, "take_profit", pnl_pct))
                # Trailing stop (5% from peak)
                elif pnl_pct >= 0.05:
                    if pos.get("peak_price", 0) == 0:
                        pos["peak_price"] = current_price
                    elif current_price > pos.get("peak_price", 0):
                        pos["peak_price"] = current_price
                    if pos.get("peak_price", 0) > 0:
                        trailing_stop = pos["peak_price"] * (1 - 0.03)
                        if current_price <= trailing_stop:
                            to_close.append((symbol, "trailing_stop", pnl_pct))

            # Close positions
            for symbol, reason, pnl_pct in to_close:
                if symbol not in positions:
                    continue
                pos = positions[symbol]
                current_price = self._get_price(price_data, symbol, date)
                if current_price <= 0:
                    continue

                sell_value = pos["qty"] * current_price
                commission = sell_value * self.commission_pct
                slippage = sell_value * self.slippage_pct
                net_value = sell_value - commission - slippage

                cash += net_value
                pnl = net_value - (pos["qty"] * pos["entry_price"])
                bucket_pnl[pos["bucket"]] = bucket_pnl.get(pos["bucket"], 0) + pnl

                # Calculate hold days safely (both tz-naive)
                try:
                    entry_ts = pd.Timestamp(pos["entry_date"])
                    hold_days = (date - entry_ts).days
                    if hold_days < 0:
                        hold_days = 0
                except Exception:
                    hold_days = 0

                closed_trades.append({
                    "symbol": symbol,
                    "bucket": pos["bucket"],
                    "entry_date": pos["entry_date"],
                    "exit_date": date.strftime("%Y-%m-%d"),
                    "entry_price": pos["entry_price"],
                    "exit_price": current_price,
                    "qty": pos["qty"],
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "reason": reason,
                    "hold_days": hold_days,
                })
                del positions[symbol]

            # Generate signals and look for new buys
            if len(positions) < self.max_positions:
                for symbol, df in price_data.items():
                    if symbol in positions:
                        continue
                    if len(positions) >= self.max_positions:
                        break

                    # Get data up to current date
                    df_slice = df[df.index <= date].tail(100)
                    if len(df_slice) < 50:
                        continue

                    # Generate signals
                    try:
                        signals = generate_all_signals(df_slice, symbol)
                        combined = calculate_combined_score(signals)

                        if combined["signal"] == "BUY" and combined["confidence"] >= 0.3:
                            current_price = self._get_price(price_data, symbol, date)
                            if current_price <= 0:
                                continue

                            # Classify stock
                            div_yield = div_yields.get(symbol)
                            bucket = self.classify_stock(symbol, current_price, div_yield)

                            # Position sizing (ATR-based)
                            atr = calculate_atr(df_slice)
                            if atr > 0:
                                risk_per_share = 2 * atr
                                risk_amount = current_equity * 0.01
                                qty = max(1, int(risk_amount / risk_per_share))
                            else:
                                max_value = current_equity * self.max_position_pct
                                qty = max(1, int(max_value / current_price))

                            # Ensure we have enough cash
                            cost = qty * current_price * (1 + self.commission_pct + self.slippage_pct)
                            if cost > cash * 0.95:
                                qty = max(1, int((cash * 0.95) / (current_price * (1 + self.commission_pct + self.slippage_pct))))
                                cost = qty * current_price * (1 + self.commission_pct + self.slippage_pct)
                            if cost > cash or qty <= 0:
                                continue

                            cash -= cost
                            positions[symbol] = {
                                "symbol": symbol,
                                "qty": qty,
                                "entry_price": current_price,
                                "stop_loss": current_price * (1 - self.stop_loss_pct),
                                "take_profit": current_price * (1 + self.take_profit_pct),
                                "bucket": bucket,
                                "entry_date": date.strftime("%Y-%m-%d"),
                                "peak_price": current_price,
                                "signals": combined.get("details", []),
                            }
                    except Exception:
                        continue

        # Close any remaining positions at the end
        final_date = dates[-1] if dates else datetime.now()
        for symbol, pos in list(positions.items()):
            current_price = self._get_price(price_data, symbol, final_date)
            if current_price <= 0:
                current_price = pos["entry_price"]

            sell_value = pos["qty"] * current_price
            commission = sell_value * self.commission_pct
            slippage = sell_value * self.slippage_pct
            net_value = sell_value - commission - slippage
            pnl = net_value - (pos["qty"] * pos["entry_price"])
            pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"]

            bucket_pnl[pos["bucket"]] = bucket_pnl.get(pos["bucket"], 0) + pnl

            # Calculate hold days safely
            try:
                final_ts = pd.Timestamp(final_date) if not isinstance(final_date, pd.Timestamp) else final_date
                entry_ts = pd.Timestamp(pos["entry_date"])
                # Ensure both are tz-naive
                if final_ts.tz is not None:
                    final_ts = final_ts.tz_localize(None)
                if entry_ts.tz is not None:
                    entry_ts = entry_ts.tz_localize(None)
                hold_days = (final_ts - entry_ts).days
                if hold_days < 0:
                    hold_days = 0
            except Exception:
                hold_days = 0

            closed_trades.append({
                "symbol": symbol,
                "bucket": pos["bucket"],
                "entry_date": pos["entry_date"],
                "exit_date": final_date.strftime("%Y-%m-%d") + " (open)",
                "entry_price": pos["entry_price"],
                "exit_price": current_price,
                "qty": pos["qty"],
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "reason": "end_of_backtest",
                "hold_days": hold_days,
            })

        cash += sum(p["qty"] * self._get_price(price_data, p["symbol"], final_date) for p in positions.values())
        positions.clear()

        # Calculate metrics
        results["trades"] = closed_trades
        results["equity_curve"] = equity_curve
        results["bucket_pnl"] = bucket_pnl
        results["final_capital"] = cash
        results["total_return"] = (cash - self.initial_capital) / self.initial_capital * 100
        results["metrics"] = self._calculate_metrics(closed_trades, equity_curve)
        results["status"] = "complete"

        return results

    def _get_price(self, price_data: Dict, symbol: str, date) -> float:
        """Get the closing price for a symbol on a given date."""
        if symbol not in price_data:
            return 0
        df = price_data[symbol]
        try:
            # Ensure both are tz-naive for comparison
            target_date = pd.Timestamp(date)
            if target_date.tz is not None:
                target_date = target_date.tz_localize(None)

            if target_date in df.index:
                return float(df.loc[target_date, 'close'])

            # Find nearest date
            mask = df.index <= target_date
            if mask.any():
                return float(df.loc[mask, 'close'].iloc[-1])
        except Exception:
            pass
        return 0

    def _calculate_metrics(self, trades: List[Dict], equity_curve: List[Dict]) -> Dict:
        """Calculate comprehensive backtest metrics."""
        metrics = {
            "total_trades": len(trades),
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0,
            "avg_win_pct": 0,
            "avg_loss_pct": 0,
            "total_return_pct": 0,
            "max_drawdown_pct": 0,
            "sharpe_ratio": 0,
            "sortino_ratio": 0,
            "calmar_ratio": 0,
            "profit_factor": 0,
            "avg_hold_days": 0,
            "by_bucket": {},
            "by_reason": {},
            "monthly_returns": {},
            "worst_trade_pct": 0,
            "best_trade_pct": 0,
            "max_consecutive_wins": 0,
            "max_consecutive_losses": 0,
            "avg_trades_per_month": 0,
        }

        if not trades:
            return metrics

        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]
        metrics["winning_trades"] = len(wins)
        metrics["losing_trades"] = len(losses)
        metrics["win_rate"] = round(len(wins) / len(trades) * 100, 1) if trades else 0

        if wins:
            metrics["avg_win_pct"] = round(sum(t["pnl_pct"] for t in wins) / len(wins) * 100, 2)
            metrics["best_trade_pct"] = round(max(t["pnl_pct"] for t in wins) * 100, 2)
        if losses:
            metrics["avg_loss_pct"] = round(sum(t["pnl_pct"] for t in losses) / len(losses) * 100, 2)
            metrics["worst_trade_pct"] = round(min(t["pnl_pct"] for t in losses) * 100, 2)

        # Profit factor
        total_wins = sum(t["pnl"] for t in wins)
        total_losses = abs(sum(t["pnl"] for t in losses))
        metrics["profit_factor"] = round(total_wins / total_losses, 2) if total_losses > 0 else float('inf')

        # Average hold days
        hold_days = [t.get("hold_days", 0) for t in trades if t.get("hold_days")]
        metrics["avg_hold_days"] = round(sum(hold_days) / len(hold_days), 1) if hold_days else 0

        # By bucket
        for t in trades:
            bucket = t.get("bucket", "unknown")
            if bucket not in metrics["by_bucket"]:
                metrics["by_bucket"][bucket] = {"trades": 0, "wins": 0, "pnl": 0}
            metrics["by_bucket"][bucket]["trades"] += 1
            if t["pnl"] > 0:
                metrics["by_bucket"][bucket]["wins"] += 1
            metrics["by_bucket"][bucket]["pnl"] += t["pnl"]

        # By reason
        for t in trades:
            reason = t.get("reason", "unknown")
            if reason not in metrics["by_reason"]:
                metrics["by_reason"][reason] = {"trades": 0, "wins": 0, "pnl": 0}
            metrics["by_reason"][reason]["trades"] += 1
            if t["pnl"] > 0:
                metrics["by_reason"][reason]["wins"] += 1
            metrics["by_reason"][reason]["pnl"] += t["pnl"]

        # Monthly returns
        for t in trades:
            month = t.get("exit_date", "")[:7]
            if month:
                if month not in metrics["monthly_returns"]:
                    metrics["monthly_returns"][month] = 0
                metrics["monthly_returns"][month] += t["pnl"]

        # Consecutive wins/losses
        streak = 0
        max_wins = 0
        max_losses = 0
        current_type = None
        for t in sorted(trades, key=lambda x: x.get("exit_date", "")):
            if t["pnl"] > 0:
                if current_type == "win":
                    streak += 1
                else:
                    streak = 1
                    current_type = "win"
                max_wins = max(max_wins, streak)
            else:
                if current_type == "loss":
                    streak += 1
                else:
                    streak = 1
                    current_type = "loss"
                max_losses = max(max_losses, streak)
        metrics["max_consecutive_wins"] = max_wins
        metrics["max_consecutive_losses"] = max_losses

        # Equity-based metrics
        if equity_curve:
            values = [e["equity"] for e in equity_curve]
            if len(values) > 1:
                metrics["total_return_pct"] = round((values[-1] / values[0] - 1) * 100, 2)

                # Max drawdown
                peak = values[0]
                max_dd = 0
                for v in values:
                    if v > peak:
                        peak = v
                    dd = (peak - v) / peak * 100
                    max_dd = max(max_dd, dd)
                metrics["max_drawdown_pct"] = round(max_dd, 2)

                # Daily returns
                daily_returns = []
                for j in range(1, len(values)):
                    if values[j-1] > 0:
                        daily_returns.append((values[j] - values[j-1]) / values[j-1])

                if daily_returns:
                    avg_ret = sum(daily_returns) / len(daily_returns)
                    std_ret = sqrt(sum((r - avg_ret) ** 2 for r in daily_returns) / len(daily_returns)) if len(daily_returns) > 1 else 0

                    # Sharpe
                    risk_free = 0.04 / 252
                    metrics["sharpe_ratio"] = round((avg_ret - risk_free) / std_ret * sqrt(252), 2) if std_ret > 0 else 0

                    # Sortino
                    downside = [r for r in daily_returns if r < 0]
                    downside_std = sqrt(sum(r ** 2 for r in downside) / len(downside)) if downside else 0
                    metrics["sortino_ratio"] = round((avg_ret - risk_free) / downside_std * sqrt(252), 2) if downside_std > 0 else 0

                    # Calmar
                    annual_return = ((values[-1] / values[0]) ** (252 / len(daily_returns)) - 1) * 100 if len(daily_returns) > 0 and values[0] > 0 else 0
                    metrics["calmar_ratio"] = round(annual_return / max_dd, 2) if max_dd > 0 else 0

                    metrics["avg_trades_per_month"] = round(len(trades) / max(len(daily_returns) / 22, 1), 1)

        return metrics
