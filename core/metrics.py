"""
core/metrics.py
Advanced performance metrics: Sortino, Calmar, Omega,
rolling returns, drawdown analysis, and attribution.
"""

import numpy as np
from typing import Dict, List, Optional
from math import sqrt
from datetime import datetime


def calculate_sortino_ratio(returns: List[float], risk_free_rate: float = 0.04,
                            annualize: bool = True) -> float:
    """Calculate Sortino Ratio (penalizes downside only).
    Better than Sharpe for asymmetric return distributions.
    """
    if not returns or len(returns) < 2:
        return 0

    daily_rf = risk_free_rate / 252
    excess_returns = [r - daily_rf for r in returns]
    downside_returns = [r for r in excess_returns if r < 0]

    if not downside_returns:
        return float('inf') if sum(excess_returns) > 0 else 0

    downside_std = sqrt(sum(r ** 2 for r in downside_returns) / len(downside_returns))
    if downside_std == 0:
        return 0

    avg_excess = sum(excess_returns) / len(excess_returns)
    sortino = avg_excess / downside_std

    if annualize:
        sortino *= sqrt(252)

    return round(sortino, 3)


def calculate_calmar_ratio(annual_return: float, max_drawdown_pct: float) -> float:
    """Calculate Calmar Ratio (annual return / max drawdown).
    Higher is better. A Calmar > 1 is considered good.
    """
    if max_drawdown_pct <= 0:
        return float('inf') if annual_return > 0 else 0
    return round(annual_return / max_drawdown_pct, 3)


def calculate_omega_ratio(returns: List[float], threshold: float = 0.0) -> float:
    """Calculate Omega Ratio (gains above threshold / losses below threshold).
    An omega > 1 means more gains than losses.
    """
    if not returns:
        return 0

    gains = sum(r - threshold for r in returns if r > threshold)
    losses = sum(threshold - r for r in returns if r <= threshold)

    if losses == 0:
        return float('inf') if gains > 0 else 0

    return round(gains / losses, 3)


def calculate_rolling_returns(equity_values: List[float],
                              dates: List[str] = None,
                              windows: List[int] = None) -> Dict:
    """Calculate rolling returns over various windows (in trading days).
    Windows default to 5 (1 week), 22 (1 month), 66 (3 months), 252 (1 year).
    """
    if not equity_values or len(equity_values) < 2:
        return {}

    if windows is None:
        windows = [5, 22, 66, 252]

    results = {}
    for window in windows:
        if len(equity_values) <= window:
            continue

        rolling_rets = []
        for i in range(window, len(equity_values)):
            start_val = equity_values[i - window]
            if start_val > 0:
                ret = (equity_values[i] / start_val - 1) * 100
                rolling_rets.append({
                    "date": dates[i] if dates and i < len(dates) else f"day_{i}",
                    "return_pct": round(ret, 2),
                })

        if rolling_rets:
            key = f"{window}_day"
            results[key] = {
                "avg_return_pct": round(np.mean([r["return_pct"] for r in rolling_rets]), 2),
                "min_return_pct": round(min(r["return_pct"] for r in rolling_rets), 2),
                "max_return_pct": round(max(r["return_pct"] for r in rolling_rets), 2),
                "current_return_pct": rolling_rets[-1]["return_pct"],
                "data": rolling_rets[-30:],  # Last 30 data points
            }

    return results


def calculate_drawdown_analysis(equity_values: List[float]) -> Dict:
    """Detailed drawdown analysis: max DD, avg DD, duration, recovery."""
    if not equity_values or len(equity_values) < 2:
        return {}

    peak = equity_values[0]
    peak_idx = 0
    drawdowns = []
    max_dd = 0
    max_dd_start = 0
    max_dd_end = 0
    current_dd_start = 0

    for i, val in enumerate(equity_values):
        if val > peak:
            peak = val
            peak_idx = i
            current_dd_start = i

        dd_pct = (peak - val) / peak * 100 if peak > 0 else 0
        drawdowns.append(dd_pct)

        if dd_pct > max_dd:
            max_dd = dd_pct
            max_dd_start = current_dd_start
            max_dd_end = i

    # Find drawdown periods
    in_drawdown = False
    dd_periods = []
    dd_start = 0
    for i, dd in enumerate(drawdowns):
        if dd > 0 and not in_drawdown:
            in_drawdown = True
            dd_start = i
        elif dd == 0 and in_drawdown:
            in_drawdown = False
            max_dd_in_period = max(drawdowns[dd_start:i])
            dd_periods.append({
                "start_day": dd_start,
                "end_day": i,
                "duration_days": i - dd_start,
                "max_drawdown_pct": round(max_dd_in_period, 2),
            })

    if in_drawdown:
        max_dd_in_period = max(drawdowns[dd_start:])
        dd_periods.append({
            "start_day": dd_start,
            "end_day": len(drawdowns) - 1,
            "duration_days": len(drawdowns) - 1 - dd_start,
            "max_drawdown_pct": round(max_dd_in_period, 2),
            "still_in_drawdown": True,
        })

    avg_dd = np.mean([d for d in drawdowns if d > 0]) if any(d > 0 for d in drawdowns) else 0
    avg_duration = np.mean([p["duration_days"] for p in dd_periods]) if dd_periods else 0

    return {
        "max_drawdown_pct": round(max_dd, 2),
        "max_drawdown_start_day": max_dd_start,
        "max_drawdown_end_day": max_dd_end,
        "avg_drawdown_pct": round(avg_dd, 2),
        "avg_drawdown_duration_days": round(avg_duration, 1),
        "total_drawdown_periods": len(dd_periods),
        "drawdown_periods": dd_periods[-10:],  # Last 10 periods
        "currently_in_drawdown": drawdowns[-1] > 0,
        "current_drawdown_pct": round(drawdowns[-1], 2),
    }


def calculate_attribution_by_bucket(trades: List[Dict],
                                     bucket_pnl: Dict = None) -> Dict:
    """Calculate performance attribution by bucket, sector, and reason."""
    attribution = {
        "by_bucket": {},
        "by_sector": {},
        "by_reason": {},
        "by_month": {},
        "by_day_of_week": {},
        "total_pnl": 0,
        "total_trades": len(trades),
    }

    for trade in trades:
        # By bucket
        bucket = trade.get("bucket", "unknown")
        if bucket not in attribution["by_bucket"]:
            attribution["by_bucket"][bucket] = {
                "trades": 0, "wins": 0, "pnl": 0, "pnl_pct_avg": 0,
                "avg_hold_days": 0, "win_rate": 0,
            }
        attribution["by_bucket"][bucket]["trades"] += 1
        if trade["pnl"] > 0:
            attribution["by_bucket"][bucket]["wins"] += 1
        attribution["by_bucket"][bucket]["pnl"] += trade["pnl"]
        attribution["by_bucket"][bucket]["pnl_pct_avg"] = (
            attribution["by_bucket"][bucket].get("pnl_pct_avg", 0) + trade.get("pnl_pct", 0)
        )

        # By reason
        reason = trade.get("reason", "unknown")
        if reason not in attribution["by_reason"]:
            attribution["by_reason"][reason] = {"trades": 0, "wins": 0, "pnl": 0}
        attribution["by_reason"][reason]["trades"] += 1
        if trade["pnl"] > 0:
            attribution["by_reason"][reason]["wins"] += 1
        attribution["by_reason"][reason]["pnl"] += trade["pnl"]

        # By month
        exit_date = trade.get("exit_date", "")[:7]
        if exit_date:
            if exit_date not in attribution["by_month"]:
                attribution["by_month"][exit_date] = {"trades": 0, "wins": 0, "pnl": 0}
            attribution["by_month"][exit_date]["trades"] += 1
            if trade["pnl"] > 0:
                attribution["by_month"][exit_date]["wins"] += 1
            attribution["by_month"][exit_date]["pnl"] += trade["pnl"]

        # By day of week
        try:
            date_str = trade.get("exit_date", "")[:10]
            if date_str:
                day_of_week = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")
                if day_of_week not in attribution["by_day_of_week"]:
                    attribution["by_day_of_week"][day_of_week] = {"trades": 0, "wins": 0, "pnl": 0}
                attribution["by_day_of_week"][day_of_week]["trades"] += 1
                if trade["pnl"] > 0:
                    attribution["by_day_of_week"][day_of_week]["wins"] += 1
                attribution["by_day_of_week"][day_of_week]["pnl"] += trade["pnl"]
        except Exception:
            pass

        attribution["total_pnl"] += trade["pnl"]

    # Calculate averages
    for bucket, data in attribution["by_bucket"].items():
        if data["trades"] > 0:
            data["pnl_pct_avg"] = round(data["pnl_pct_avg"] / data["trades"] * 100, 2)
            data["win_rate"] = round(data["wins"] / data["trades"] * 100, 1)
        data["pnl"] = round(data["pnl"], 2)

    return attribution


def generate_full_report(trade_log: List[Dict], equity_snapshots: List[Dict]) -> Dict:
    """Generate a comprehensive performance report from existing data."""
    if not trade_log and not equity_snapshots:
        return {"status": "no_data"}

    # Extract returns from equity snapshots
    equity_values = [s.get("portfolio_value", 0) for s in equity_snapshots if s.get("portfolio_value")]
    dates = [s.get("date", "") for s in equity_snapshots if s.get("date")]

    # Daily returns
    daily_returns = []
    for i in range(1, len(equity_values)):
        if equity_values[i-1] > 0:
            daily_returns.append((equity_values[i] / equity_values[i-1]) - 1)

    # Completed trades (matching buys and sells)
    buys = {}
    completed_trades = []
    for t in sorted(trade_log, key=lambda x: x.get("timestamp", "")):
        symbol = t.get("symbol", "")
        if t.get("side") == "buy":
            buys[symbol] = t
        elif t.get("side") in ["sell", "close"] and symbol in buys:
            buy = buys[symbol]
            entry_price = float(buy.get("price", 0) or buy.get("filled_price", 0))
            exit_price = float(t.get("price", 0) or t.get("filled_price", 0))
            if entry_price > 0 and exit_price > 0:
                pnl_pct = (exit_price - entry_price) / entry_price
                completed_trades.append({
                    "symbol": symbol,
                    "bucket": t.get("bucket", "unknown"),
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl_pct": pnl_pct,
                    "pnl": (exit_price - entry_price) * float(t.get("qty", buy.get("qty", 1))),
                    "reason": t.get("reason", ""),
                    "hold_days": 0,
                })
            del buys[symbol]

    # Calculate all metrics
    report = {
        "status": "complete",
        "total_trades": len(completed_trades),
        "sharpe_ratio": 0,
        "sortino_ratio": 0,
        "calmar_ratio": 0,
        "omega_ratio": 0,
        "rolling_returns": {},
        "drawdown_analysis": {},
        "attribution": {},
    }

    if daily_returns:
        report["sharpe_ratio"] = round(
            (sum(daily_returns) / len(daily_returns) - 0.04/252) /
            (sqrt(sum((r - sum(daily_returns)/len(daily_returns))**2 for r in daily_returns) / len(daily_returns)) or 1) * sqrt(252),
            3
        )
        report["sortino_ratio"] = calculate_sortino_ratio(daily_returns)
        report["omega_ratio"] = calculate_omega_ratio(daily_returns)

    if equity_values:
        total_return = (equity_values[-1] / equity_values[0] - 1) * 100 if equity_values[0] > 0 else 0
        report["total_return_pct"] = round(total_return, 2)

        dd_analysis = calculate_drawdown_analysis(equity_values)
        report["drawdown_analysis"] = dd_analysis
        report["max_drawdown_pct"] = dd_analysis.get("max_drawdown_pct", 0)

        if dd_analysis.get("max_drawdown_pct", 0) > 0:
            annual_return = total_return / max(len(daily_returns) / 252, 0.1)
            report["calmar_ratio"] = calculate_calmar_ratio(annual_return, dd_analysis["max_drawdown_pct"])

        report["rolling_returns"] = calculate_rolling_returns(equity_values, dates)

    if completed_trades:
        report["attribution"] = calculate_attribution_by_bucket(completed_trades)

    return report
