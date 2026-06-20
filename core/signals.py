"""
core/signals.py
Advanced signal detection: MACD, Bollinger Bands, MA Crossovers,
VIX filter, and multi-timeframe confirmation.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime

try:
    import ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False


def generate_all_signals(df: pd.DataFrame, symbol: str = "",
                         params: Dict = None) -> List[Dict]:
    """Generate signals from all indicators on a single DataFrame.
    Returns a list of signal dicts with type, direction, strength, and reason.
    """
    if params is None:
        params = {}

    signals = []
    if df is None or df.empty or len(df) < 50:
        return signals

    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    # RSI Signal
    rsi_signal = _rsi_signal(df, params)
    if rsi_signal:
        rsi_signal["symbol"] = symbol
        signals.append(rsi_signal)

    # MACD Signal
    macd_signal = _macd_signal(df, params)
    if macd_signal:
        macd_signal["symbol"] = symbol
        signals.append(macd_signal)

    # Bollinger Band Signal
    bb_signal = _bollinger_signal(df, params)
    if bb_signal:
        bb_signal["symbol"] = symbol
        signals.append(bb_signal)

    # Moving Average Crossover
    ma_signal = _ma_crossover_signal(df, params)
    if ma_signal:
        ma_signal["symbol"] = symbol
        signals.append(ma_signal)

    # Volume Spike Signal
    vol_signal = _volume_spike_signal(df, params)
    if vol_signal:
        vol_signal["symbol"] = symbol
        signals.append(vol_signal)

    # ATR (volatility) Signal
    atr_signal = _atr_signal(df, params)
    if atr_signal:
        atr_signal["symbol"] = symbol
        signals.append(atr_signal)

    return signals


def calculate_combined_score(signals: List[Dict], params: Dict = None) -> Dict:
    """Combine multiple signals into a single score with direction and confidence."""
    if not signals:
        return {"signal": "HOLD", "confidence": 0, "reason": "No signals", "details": []}

    if params is None:
        params = {}

    weights = params.get("signal_weights", {
        "rsi": 1.0, "macd": 1.2, "bollinger": 0.8,
        "ma_cross": 1.5, "volume": 0.6, "atr": 0.5
    })

    buy_score = 0
    sell_score = 0
    total_weight = 0
    details = []

    for sig in signals:
        sig_type = sig.get("type", "")
        direction = sig.get("direction", "NEUTRAL")
        strength = sig.get("strength", 0)
        weight = weights.get(sig_type, 1.0)

        if direction == "BUY":
            buy_score += strength * weight
        elif direction == "SELL":
            sell_score += strength * weight
        total_weight += weight
        details.append(f"{sig_type}: {direction} ({strength:.2f})")

    if total_weight == 0:
        return {"signal": "HOLD", "confidence": 0, "reason": "No weighted signals", "details": details}

    net_score = buy_score - sell_score
    max_possible = total_weight * 2
    confidence = min(abs(net_score) / max(max_possible * 0.5, 1), 1.0)

    if net_score > 0.5:
        return {"signal": "BUY", "confidence": confidence, "reason": f"Net buy score: {net_score:.2f}", "details": details}
    elif net_score < -0.5:
        return {"signal": "SELL", "confidence": confidence, "reason": f"Net sell score: {net_score:.2f}", "details": details}
    else:
        return {"signal": "HOLD", "confidence": confidence, "reason": "Signals mixed/neutral", "details": details}


def multi_timeframe_check(symbol: str, params: Dict = None) -> Dict:
    """Check signals across multiple timeframes for confirmation.
    Weekly trend → Daily signal → confirmation.
    Returns a combined signal with higher confidence if multiple timeframes agree.
    """
    if not YF_AVAILABLE:
        return {"signal": "HOLD", "confidence": 0, "reason": "YFinance unavailable"}

    if params is None:
        params = {}

    results = {"weekly": None, "daily": None, "combined": None}

    # Weekly trend
    try:
        df_weekly = yf.Ticker(symbol).history(period="2y", interval="1wk")
        if df_weekly is not None and len(df_weekly) >= 50:
            weekly_signals = generate_all_signals(df_weekly, symbol, params)
            weekly_score = calculate_combined_score(weekly_signals, params)
            results["weekly"] = weekly_score
    except Exception:
        pass

    # Daily signal
    try:
        df_daily = yf.Ticker(symbol).history(period="6mo", interval="1d")
        if df_daily is not None and len(df_daily) >= 50:
            daily_signals = generate_all_signals(df_daily, symbol, params)
            daily_score = calculate_combined_score(daily_signals, params)
            results["daily"] = daily_score
    except Exception:
        pass

    # Combine
    weekly_dir = results.get("weekly", {}).get("signal", "HOLD")
    daily_dir = results.get("daily", {}).get("signal", "HOLD")

    if weekly_dir == daily_dir and daily_dir != "HOLD":
        confidence = min(
            results.get("weekly", {}).get("confidence", 0) + results.get("daily", {}).get("confidence", 0),
            1.0
        )
        results["combined"] = {
            "signal": daily_dir,
            "confidence": confidence,
            "reason": f"Weekly + Daily confirm: {daily_dir}",
            "weekly": weekly_dir,
            "daily": daily_dir,
        }
    elif daily_dir != "HOLD":
        results["combined"] = {
            "signal": daily_dir,
            "confidence": results.get("daily", {}).get("confidence", 0) * 0.6,
            "reason": f"Daily says {daily_dir}, Weekly says {weekly_dir} (reduced confidence)",
            "weekly": weekly_dir,
            "daily": daily_dir,
        }
    else:
        results["combined"] = {
            "signal": "HOLD",
            "confidence": 0,
            "reason": "No clear signal across timeframes",
            "weekly": weekly_dir,
            "daily": daily_dir,
        }

    return results


# ==========================================
# INDIVIDUAL SIGNAL FUNCTIONS
# ==========================================

def _rsi_signal(df: pd.DataFrame, params: Dict) -> Optional[Dict]:
    """RSI oversold/overbought signal."""
    if not TA_AVAILABLE:
        return None
    try:
        oversold = params.get("rsi_oversold", 35)
        overbought = params.get("rsi_overbought", 65)
        rsi = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
        current_rsi = rsi.iloc[-1]
        if pd.isna(current_rsi):
            return None

        if current_rsi < oversold:
            strength = (oversold - current_rsi) / oversold
            return {"type": "rsi", "direction": "BUY", "strength": min(strength, 1.0),
                    "value": round(current_rsi, 1), "reason": f"RSI={current_rsi:.1f} (oversold)"}
        elif current_rsi > overbought:
            strength = (current_rsi - overbought) / (100 - overbought)
            return {"type": "rsi", "direction": "SELL", "strength": min(strength, 1.0),
                    "value": round(current_rsi, 1), "reason": f"RSI={current_rsi:.1f} (overbought)"}
    except Exception:
        pass
    return None


def _macd_signal(df: pd.DataFrame, params: Dict) -> Optional[Dict]:
    """MACD crossover signal."""
    if not TA_AVAILABLE:
        return None
    try:
        macd = ta.trend.MACD(df["close"])
        macd_line = macd.macd()
        signal_line = macd.macd_signal()
        histogram = macd.macd_diff()

        if len(macd_line) < 2 or pd.isna(macd_line.iloc[-1]):
            return None

        current_macd = macd_line.iloc[-1]
        current_signal = signal_line.iloc[-1]
        current_hist = histogram.iloc[-1]
        prev_hist = histogram.iloc[-2] if len(histogram) >= 2 else 0

        # Bullish crossover: MACD crosses above signal
        if current_macd > current_signal and prev_hist <= 0 and current_hist > 0:
            strength = min(abs(current_hist) / max(abs(df["close"].iloc[-1]) * 0.01, 0.01), 1.0)
            return {"type": "macd", "direction": "BUY", "strength": max(strength, 0.5),
                    "value": round(current_macd, 4),
                    "reason": f"MACD bullish crossover (hist={current_hist:.4f})"}

        # Bearish crossover: MACD crosses below signal
        elif current_macd < current_signal and prev_hist >= 0 and current_hist < 0:
            strength = min(abs(current_hist) / max(abs(df["close"].iloc[-1]) * 0.01, 0.01), 1.0)
            return {"type": "macd", "direction": "SELL", "strength": max(strength, 0.5),
                    "value": round(current_macd, 4),
                    "reason": f"MACD bearish crossover (hist={current_hist:.4f})"}

        # Momentum increasing
        elif current_hist > prev_hist and current_hist > 0:
            return {"type": "macd", "direction": "BUY", "strength": 0.3,
                    "value": round(current_macd, 4),
                    "reason": f"MACD momentum increasing"}
        elif current_hist < prev_hist and current_hist < 0:
            return {"type": "macd", "direction": "SELL", "strength": 0.3,
                    "value": round(current_macd, 4),
                    "reason": f"MACD momentum decreasing"}

    except Exception:
        pass
    return None


def _bollinger_signal(df: pd.DataFrame, params: Dict) -> Optional[Dict]:
    """Bollinger Band squeeze and touch signal."""
    if not TA_AVAILABLE:
        return None
    try:
        bb = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
        upper = bb.bollinger_hband()
        lower = bb.bollinger_lband()
        current = df["close"].iloc[-1]

        if pd.isna(upper.iloc[-1]) or pd.isna(lower.iloc[-1]):
            return None

        current_upper = upper.iloc[-1]
        current_lower = lower.iloc[-1]
        current_middle = (current_upper + current_lower) / 2
        bb_width = (current_upper - current_lower) / current_middle if current_middle > 0 else 0

        # Price touching lower band (oversold)
        if current <= current_lower * 1.01:
            strength = min((current_lower - current) / max(abs(current_lower * 0.02), 0.01) + 0.5, 1.0)
            return {"type": "bollinger", "direction": "BUY", "strength": strength,
                    "value": round(current, 2),
                    "reason": f"Price touching lower BB (${current:.2f} <= ${current_lower:.2f})"}

        # Price touching upper band (overbought)
        elif current >= current_upper * 0.99:
            strength = min((current - current_upper) / max(abs(current_upper * 0.02), 0.01) + 0.5, 1.0)
            return {"type": "bollinger", "direction": "SELL", "strength": strength,
                    "value": round(current, 2),
                    "reason": f"Price touching upper BB (${current:.2f} >= ${current_upper:.2f})"}

        # Bollinger squeeze (low volatility → potential breakout)
        avg_bb_width = bb_width
        if len(upper) >= 20:
            recent_widths = [(upper.iloc[-i] - lower.iloc[-i]) / ((upper.iloc[-i] + lower.iloc[-i]) / 2) for i in range(1, min(21, len(upper))) if not pd.isna(upper.iloc[-i])]
            if recent_widths:
                avg_bb_width = np.mean(recent_widths)

        if bb_width < avg_bb_width * 0.7:
            return {"type": "bollinger", "direction": "HOLD", "strength": 0.4,
                    "value": round(bb_width, 4),
                    "reason": f"Bollinger squeeze (width={bb_width:.4f} < avg={avg_bb_width:.4f})"}

    except Exception:
        pass
    return None


def _ma_crossover_signal(df: pd.DataFrame, params: Dict) -> Optional[Dict]:
    """50/200 SMA golden cross / death cross signal."""
    try:
        sma_50 = df["close"].rolling(50).mean()
        sma_200 = df["close"].rolling(200).mean()

        if len(df) < 200 or pd.isna(sma_200.iloc[-1]) or pd.isna(sma_50.iloc[-1]):
            # Try shorter MAs for shorter datasets
            sma_short = df["close"].rolling(20).mean()
            sma_long = df["close"].rolling(50).mean()
            if pd.isna(sma_short.iloc[-1]) or pd.isna(sma_long.iloc[-1]):
                return None

            if sma_short.iloc[-1] > sma_long.iloc[-1] and sma_short.iloc[-2] <= sma_long.iloc[-2]:
                return {"type": "ma_cross", "direction": "BUY", "strength": 0.7,
                        "value": round(sma_short.iloc[-1], 2),
                        "reason": "20/50 SMA bullish crossover"}
            elif sma_short.iloc[-1] < sma_long.iloc[-1] and sma_short.iloc[-2] >= sma_long.iloc[-2]:
                return {"type": "ma_cross", "direction": "SELL", "strength": 0.7,
                        "value": round(sma_short.iloc[-1], 2),
                        "reason": "20/50 SMA bearish crossover"}
            return None

        # Golden cross (50 SMA crosses above 200 SMA)
        if sma_50.iloc[-1] > sma_200.iloc[-1] and sma_50.iloc[-2] <= sma_200.iloc[-2]:
            return {"type": "ma_cross", "direction": "BUY", "strength": 1.0,
                    "value": round(sma_50.iloc[-1], 2),
                    "reason": "Golden Cross (50/200 SMA)"}

        # Death cross (50 SMA crosses below 200 SMA)
        elif sma_50.iloc[-1] < sma_200.iloc[-1] and sma_50.iloc[-2] >= sma_200.iloc[-2]:
            return {"type": "ma_cross", "direction": "SELL", "strength": 1.0,
                    "value": round(sma_50.iloc[-1], 2),
                    "reason": "Death Cross (50/200 SMA)"}

        # Trend direction
        elif sma_50.iloc[-1] > sma_200.iloc[-1]:
            return {"type": "ma_cross", "direction": "BUY", "strength": 0.3,
                    "value": round(sma_50.iloc[-1], 2),
                    "reason": "50 SMA above 200 SMA (bullish trend)"}
        else:
            return {"type": "ma_cross", "direction": "SELL", "strength": 0.3,
                    "value": round(sma_50.iloc[-1], 2),
                    "reason": "50 SMA below 200 SMA (bearish trend)"}

    except Exception:
        pass
    return None


def _volume_spike_signal(df: pd.DataFrame, params: Dict) -> Optional[Dict]:
    """Volume spike signal (> 3x average volume)."""
    try:
        min_rvol = params.get("min_rvol", 1.5)
        avg_vol = df["volume"].rolling(20).mean().iloc[-1]
        curr_vol = df["volume"].iloc[-1]

        if pd.isna(avg_vol) or avg_vol <= 0:
            return None

        rvol = curr_vol / avg_vol

        if rvol >= 3.0:
            return {"type": "volume", "direction": "BUY", "strength": min(rvol / 5, 1.0),
                    "value": round(rvol, 2),
                    "reason": f"Massive volume spike (RVOL={rvol:.1f}x)"}
        elif rvol >= 2.0:
            return {"type": "volume", "direction": "BUY", "strength": 0.4,
                    "value": round(rvol, 2),
                    "reason": f"Strong volume (RVOL={rvol:.1f}x)"}
    except Exception:
        pass
    return None


def _atr_signal(df: pd.DataFrame, params: Dict) -> Optional[Dict]:
    """ATR (Average True Range) volatility signal.
    Low ATR = low volatility (good for dividend stocks).
    High ATR = high volatility (risky for penny stocks)."""
    if not TA_AVAILABLE:
        return None
    try:
        atr = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=14)
        current_atr = atr.average_true_range().iloc[-1]
        current_price = df["close"].iloc[-1]

        if pd.isna(current_atr) or current_price <= 0:
            return None

        atr_pct = current_atr / current_price

        if atr_pct > 0.05:
            return {"type": "atr", "direction": "SELL", "strength": min(atr_pct / 0.1, 0.8),
                    "value": round(atr_pct * 100, 2),
                    "reason": f"High volatility (ATR={atr_pct*100:.1f}% of price)"}
        elif atr_pct < 0.01:
            return {"type": "atr", "direction": "BUY", "strength": 0.3,
                    "value": round(atr_pct * 100, 2),
                    "reason": f"Low volatility (ATR={atr_pct*100:.1f}% of price)"}
    except Exception:
        pass
    return None


def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calculate current ATR for position sizing."""
    if not TA_AVAILABLE or df is None or len(df) < period + 1:
        return 0
    try:
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        atr_indicator = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=period)
        atr_series = atr_indicator.average_true_range()
        if len(atr_series) > 0 and not pd.isna(atr_series.iloc[-1]):
            return float(atr_series.iloc[-1])
    except Exception:
        pass
    return 0


def vix_filter(vix_threshold: float = 25.0) -> Dict:
    """Check VIX for market fear. Returns whether to avoid trading."""
    if not YF_AVAILABLE:
        return {"safe_to_trade": True, "vix": 0, "level": "Unknown", "reason": "YFinance unavailable"}

    try:
        vix_data = yf.Ticker("^VIX").history(period="5d")
        if vix_data is None or vix_data.empty:
            return {"safe_to_trade": True, "vix": 0, "level": "Unknown", "reason": "No VIX data"}

        vix_value = float(vix_data['Close'].iloc[-1])

        if vix_value > 30:
            return {"safe_to_trade": False, "vix": vix_value, "level": "Extreme Fear",
                    "reason": f"VIX={vix_value:.1f} (Extreme Fear). Consider reducing exposure."}
        elif vix_value > vix_threshold:
            return {"safe_to_trade": False, "vix": vix_value, "level": "Fear",
                    "reason": f"VIX={vix_value:.1f} (Fear). Cautious trading only."}
        elif vix_value > 20:
            return {"safe_to_trade": True, "vix": vix_value, "level": "Elevated",
                    "reason": f"VIX={vix_value:.1f} (Elevated). Normal conditions."}
        else:
            return {"safe_to_trade": True, "vix": vix_value, "level": "Calm",
                    "reason": f"VIX={vix_value:.1f} (Calm). Good for buying."}
    except Exception as e:
        return {"safe_to_trade": True, "vix": 0, "level": "Error",
                "reason": f"VIX error: {str(e)[:50]}"}
