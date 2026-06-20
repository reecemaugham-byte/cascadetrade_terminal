"""
trading_engine.py
QuantPro Terminal — Diamond Standard Trading Engine
3-bucket system: Dividend (🟢), Growth (🔵), Penny (🔴), Withdrawal (🟡)
Advanced signals: MACD, Bollinger, MA Cross, ATR, VIX filter
ATR position sizing, backtesting, dividend calendar, audit trail
Batch scanning for speed, Sell Everything, Rebalance, Move from Withdrawal
"""

import os
import threading
import time
import json
import csv
from datetime import datetime, timedelta, date, time as dt_time
from pathlib import Path
from typing import List, Dict, Optional
from math import sqrt

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

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import alpaca_trade_api as tradeapi
    ALPACA_AVAILABLE = True
except ImportError:
    tradeapi = None
    ALPACA_AVAILABLE = False

# ==========================================
# DIAMOND STANDARD MODULE IMPORTS
# ==========================================
try:
    from core.signals import (
        generate_all_signals, calculate_combined_score,
        multi_timeframe_check, calculate_atr, vix_filter
    )
    ADVANCED_SIGNALS_AVAILABLE = True
except ImportError:
    ADVANCED_SIGNALS_AVAILABLE = False

try:
    from core.backtest import BacktestEngine
    BACKTEST_AVAILABLE = True
except ImportError:
    BACKTEST_AVAILABLE = False

try:
    from core.metrics import (
        calculate_sortino_ratio, calculate_calmar_ratio,
        calculate_omega_ratio, calculate_rolling_returns,
        calculate_drawdown_analysis, calculate_attribution_by_bucket,
        generate_full_report
    )
    ADVANCED_METRICS_AVAILABLE = True
except ImportError:
    ADVANCED_METRICS_AVAILABLE = False

try:
    from core.dividends import (
        get_upcoming_ex_dividends, get_dividend_yield as get_div_yield_external,
        get_dividend_history as get_div_history_external,
        get_dividend_growth, calculate_drip, get_dividend_comparison
    )
    DIVIDEND_CALENDAR_AVAILABLE = True
except ImportError:
    DIVIDEND_CALENDAR_AVAILABLE = False

try:
    from core.audit import (
        log_audit, get_audit_trail, save_journal_entry,
        get_journal_entries, log_trade_audit, log_deposit_audit,
        log_settings_audit, log_login_audit
    )
    AUDIT_AVAILABLE = True
except ImportError:
    AUDIT_AVAILABLE = False

try:
    from core.encryption import encrypt_value, decrypt_value, is_encrypted, is_key_encrypted, verify_encryption_working
    ENCRYPTION_AVAILABLE = True
    ENCRYPTION_READY = verify_encryption_working()
except ImportError:
    ENCRYPTION_AVAILABLE = False
    ENCRYPTION_READY = False
except Exception:
    ENCRYPTION_AVAILABLE = False
    ENCRYPTION_READY = False

# ==========================================
# BUCKET ICONS
# ==========================================
BUCKET_ICONS = {
    "dividend": "🟢",
    "growth": "🔵",
    "penny": "🔴",
    "withdrawal": "🟡",
    "long_term": "🟢",
}

# ==========================================
# PREDEFINED STOCK LISTS
# ==========================================
US_QUICK_TURNOVER = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META",
    "AMD", "NFLX", "PYPL", "SQ", "ROKU", "ZM", "PLTR", "COIN",
    "SOFI", "RIVN", "LCID", "NIO", "MARA", "RIOT",
    "BAC", "C", "WFC", "GS", "MS", "JPM",
    "CCL", "NCLH", "UAL", "AAL", "DAL",
    "DIS", "WBD", "PARA", "SNAP", "PINS", "SHOP", "ETSY",
    "BABA", "JD", "PDD",
    "XOM", "CVX", "FANG",
    "MRNA", "BIIB",
    "F", "GM", "NKE", "INTC", "MU", "LRCX",
]

US_LONG_TERM = [
    "JNJ", "PG", "KO", "PEP", "V", "MA", "UNH", "HD", "COST",
    "ABBV", "LLY", "MRK", "TMO", "AVGO", "TXN", "AAPL", "MSFT",
    "BRK-B", "VZ", "T", "XOM", "CVX", "SPY", "QQQ",
    "WM", "LIN", "RTX", "HON", "UPS", "CAT", "DE",
    "LOW", "BLK", "CME", "ICE", "MMC", "AON",
]

DIVIDEND_STOCKS = [
    "JNJ", "PG", "KO", "PEP", "VZ", "T", "XOM", "CVX", "ABBV", "MRK",
    "HD", "WMT", "COST", "V", "MA", "UNH", "LLY", "AVGO", "TXN", "LIN",
    "WM", "RTX", "HON", "UPS", "CAT", "DE", "LOW", "BLK", "CME", "ICE",
    "MMC", "AON", "O", "OHI", "STAG", "VICI", "AMT", "PLD", "DLR",
    "EQIX", "PSA", "ESS", "UDR", "INVH", "IBM", "CSCO", "PFE", "MO",
    "PM", "BMY", "GILD", "VFC", "TGT", "CL", "KMB", "ED", "NEE", "DUK",
    "SO", "D", "AEP", "AWK", "WBA", "KR", "MDLZ", "CLX", "CHD",
    "LGEN.L", "AVST.L", "SSE.L", "NG.L", "ULVR.L", "BP.L", "SHEL.L",
]

GROWTH_STOCKS = [
    "AMZN", "GOOGL", "META", "TSLA", "NVDA", "NFLX", "PLTR", "COIN",
    "SHOP", "SNAP", "ROKU", "ZM", "SQ", "MARA", "RIOT",
    "CRM", "ADBE", "INTU", "SNOW", "DDOG", "NET", "ZS", "CRWD",
    "MRNA", "BIIB", "REGN", "VRTX",
]

SECTOR_MAP = {
    "AAPL": "Tech", "MSFT": "Tech", "GOOGL": "Tech", "AMZN": "Tech",
    "NVDA": "Tech", "TSLA": "Auto/Tech", "META": "Tech", "AMD": "Tech",
    "NFLX": "Tech", "PYPL": "Fintech", "SQ": "Fintech", "ROKU": "Tech",
    "ZM": "Tech", "PLTR": "Tech", "COIN": "Fintech", "SOFI": "Fintech",
    "RIVN": "Auto/Tech", "LCID": "Auto/Tech", "NIO": "Auto/Tech",
    "MARA": "Crypto", "RIOT": "Crypto", "BAC": "Financials",
    "C": "Financials", "WFC": "Financials", "GS": "Financials",
    "MS": "Financials", "JPM": "Financials", "CCL": "Travel",
    "NCLH": "Travel", "UAL": "Travel", "AAL": "Travel", "DAL": "Travel",
    "DIS": "Media", "WBD": "Media", "PARA": "Media", "SNAP": "Tech",
    "PINS": "Tech", "SHOP": "Tech", "ETSY": "Tech", "BABA": "China Tech",
    "JD": "China Tech", "PDD": "China Tech", "XOM": "Energy",
    "CVX": "Energy", "FANG": "Energy", "MRNA": "Biotech", "BIIB": "Biotech",
    "F": "Auto", "GM": "Auto", "NKE": "Consumer", "INTC": "Tech",
    "MU": "Tech", "LRCX": "Tech",
    "JNJ": "Healthcare", "PG": "Consumer Staples", "KO": "Consumer Staples",
    "PEP": "Consumer Staples", "V": "Fintech", "MA": "Fintech",
    "UNH": "Healthcare", "HD": "Consumer", "COST": "Consumer",
    "ABBV": "Healthcare", "LLY": "Healthcare", "MRK": "Healthcare",
    "TMO": "Healthcare", "AVGO": "Tech", "TXN": "Tech", "LIN": "Materials",
    "WM": "Industrials", "RTX": "Industrials", "HON": "Industrials",
    "UPS": "Industrials", "CAT": "Industrials", "DE": "Industrials",
    "LOW": "Consumer", "BLK": "Financials", "CME": "Financials",
    "ICE": "Financials", "MMC": "Financials", "AON": "Financials",
    "VZ": "Telecom", "T": "Telecom", "BRK-B": "Financials",
    "WBA": "Consumer", "IBM": "Tech", "CSCO": "Tech", "PFE": "Healthcare",
    "MO": "Consumer Staples", "PM": "Consumer Staples", "BMY": "Healthcare",
    "GILD": "Healthcare", "O": "REITs", "OHI": "REITs", "STAG": "REITs",
    "VICI": "REITs", "AMT": "REITs", "PLD": "REITs", "DLR": "REITs",
    "CRM": "Tech", "ADBE": "Tech", "INTU": "Tech",
    "SNOW": "Tech", "DDOG": "Tech", "NET": "Tech", "ZS": "Tech",
    "CRWD": "Tech", "REGN": "Biotech", "VRTX": "Biotech",
}


class TradingEngine:
    """Diamond Standard Trading Engine with 3-bucket system, advanced signals,
    ATR position sizing, VIX filter, backtesting, dividend calendar, and audit trail."""

    def __init__(self):
        self.errors = []
        self.api = None
        self.connected = False
        self.running = False
        self.thread = None
        self._stop_event = threading.Event()
        self._alpaca_api_ref = None

        self.MAX_RECONNECT_ATTEMPTS = 5
        self.RECONNECT_BASE_DELAY = 10
        self.MAX_RECONNECT_DELAY = 300

        self._stock_info_cache = {}

        self.terms_accepted = False
        self.terms_accepted_date = None

        if ENCRYPTION_AVAILABLE and not ENCRYPTION_READY:
            self._log_error("WARNING: Encryption module available but not working properly. API keys may not be secure.")

        # ============================================================
        # TRADING SETTINGS
        # ============================================================
        self.settings = {
            "mode": "quick",
            "max_positions": 10,
            "max_position_pct": 0.08,
            "daily_loss_limit_pct": 0.03,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.10,
            "trailing_stop_pct": 0.03,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "min_rvol": 1.5,
            "min_confidence": 0.25,
            "max_same_sector": 3,
            "scan_interval_min": 5,
            "watchlist": US_QUICK_TURNOVER.copy(),
            "slippage_pct": 0.05,
            "sec_fee_pct": 0.00002,
            # --- BUCKET SETTINGS (3-bucket) ---
            "deposit_amount": 1000,
            "dividend_pct": 0.35,
            "growth_pct": 0.35,
            "penny_pct": 0.30,
            "min_dividend_yield": 0.03,
            "penny_price_threshold": 5.0,
            "profit_threshold_amount": 10000,
            "profit_threshold_pct": 0.10,
            "use_pct_threshold": True,
            "auto_extract_profits": True,
            "penny_profits_to_growth": True,
            "growth_profits_to_dividend": True,
            "dividends_to_withdrawal": True,
            "original_capital": 100000,
            "watchlist_auto": False,
            "watchlist_auto_count": 100,
            # --- PRIVACY ---
            "discord_privacy_mode": True,
            # --- DISCORD ALERTS ---
            "discord_webhook_url": "",
            # --- ADVANCED SIGNAL SETTINGS ---
            "use_advanced_signals": True,
            "use_multi_timeframe": False,
            "use_vix_filter": True,
            "vix_max_threshold": 28.0,
            "use_atr_position_sizing": True,
            "atr_risk_pct": 0.01,
            "signal_weights": {
                "rsi": 1.0, "macd": 1.2, "bollinger": 0.8,
                "ma_cross": 1.5, "volume": 0.6, "atr": 0.5
            },
            # --- BUCKET-SPECIFIC SETTINGS ---
            "penny_settings": {
                "stop_loss_pct": 0.03,
                "take_profit_pct": 0.08,
                "trailing_stop_pct": 0.02,
                "max_position_pct": 0.04,
                "rsi_oversold": 25,
                "rsi_overbought": 60,
                "min_confidence": 0.30,
                "min_rvol": 1.5,
            },
            "growth_settings": {
                "stop_loss_pct": 0.06,
                "take_profit_pct": 0.12,
                "trailing_stop_pct": 0.04,
                "max_position_pct": 0.08,
                "rsi_oversold": 30,
                "rsi_overbought": 65,
                "min_confidence": 0.25,
                "min_rvol": 1.0,
            },
            "dividend_settings": {
                "stop_loss_pct": 0.08,
                "take_profit_pct": 0.15,
                "trailing_stop_pct": 0.05,
                "max_position_pct": 0.08,
                "rsi_oversold": 35,
                "rsi_overbought": 70,
                "min_confidence": 0.20,
                "min_rvol": 0.8,
            },
        }

        # State tracking
        self.daily_pnl = 0.0
        self.daily_start_equity = 0.0
        self.daily_reset_date = None
        self.signals_found = []
        self.near_signals = []
        self.trade_log = []
        self.last_scan_time = None
        self.status_message = "Not started"
        self.cycle_count = 0
        self.errors = []

        self.reconnect_count = 0
        self.last_reconnect_time = None
        self.last_successful_cycle = None
        self.consecutive_failures = 0

        self.equity_snapshots = []
        self.signal_history = []
        self.performance_metrics = {}
        self._spy_start_value = None
        self._spy_start_date = None
        self._portfolio_start_value = None

        # ============================================================
        # 3-BUCKET SYSTEM
        # ============================================================
        self.buckets = {
            "dividend": {
                "positions": [],
                "cash_allocated": 0,
                "total_deposited": 0,
                "total_dividends_earned": 0,
            },
            "growth": {
                "positions": [],
                "cash_allocated": 0,
                "total_deposited": 0,
                "profits_moved_in": 0,
            },
            "penny": {
                "positions": [],
                "cash_allocated": 0,
                "total_deposited": 0,
                "profits_to_growth": 0,
            },
            "withdrawal": {
                "available": 0,
                "total_withdrawn": 0,
                "dividends_received": 0,
                "profits_extracted": 0,
            },
            "original_capital": 100000,
            "last_deposit_date": None,
            "deposit_history": [],
            "extraction_history": [],
            "dividend_history": [],
        }

        self.scan_summary = {
            "last_scan": None,
            "stocks_scanned": 0,
            "stocks_success": 0,
            "stocks_no_data": 0,
            "errors_count": 0,
            "error_details": [],
            "data_source": "none",
        }

        self.log_dir = Path("data/trading_logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir = Path("data/exports")
        self.exports_dir.mkdir(parents=True, exist_ok=True)

        self._load_trade_log()
        self._load_equity_snapshots()
        self._load_signal_history()
        self._load_performance_metrics()
        self._load_buckets()
        self.load_settings()

    def set_username(self, username: str):
        self._username = username

    # ==========================================
    # BUCKET SYSTEM: SAVE / LOAD / MIGRATE
    # ==========================================

    def _load_buckets(self):
        bucket_file = self.log_dir / "buckets.json"
        if bucket_file.exists():
            try:
                with open(bucket_file, "r") as f:
                    saved = json.load(f)
                if "long_term" in saved and "dividend" not in saved:
                    old_lt = saved.pop("long_term")
                    div_pct = self.settings.get("dividend_pct", 0.35)
                    gro_pct = self.settings.get("growth_pct", 0.35)
                    total = div_pct + gro_pct if (div_pct + gro_pct) > 0 else 1
                    self.buckets["dividend"] = {
                        "positions": old_lt.get("positions", []),
                        "cash_allocated": old_lt.get("cash_allocated", 0) * (div_pct / total),
                        "total_deposited": old_lt.get("total_deposited", 0) * (div_pct / total),
                        "total_dividends_earned": old_lt.get("total_dividends_earned", 0),
                    }
                    self.buckets["growth"] = {
                        "positions": [],
                        "cash_allocated": old_lt.get("cash_allocated", 0) * (gro_pct / total),
                        "total_deposited": old_lt.get("total_deposited", 0) * (gro_pct / total),
                        "profits_moved_in": 0,
                    }
                    if "penny" in saved:
                        self.buckets["penny"] = saved["penny"]
                    self.buckets["withdrawal"] = saved.get("withdrawal", self.buckets["withdrawal"])
                    self.buckets["original_capital"] = saved.get("original_capital", self.buckets["original_capital"])
                    self.buckets["last_deposit_date"] = saved.get("last_deposit_date")
                    self.buckets["deposit_history"] = saved.get("deposit_history", [])
                    self.buckets["extraction_history"] = saved.get("extraction_history", [])
                    self.buckets["dividend_history"] = saved.get("dividend_history", [])
                    self._log_error("Migrated buckets from 2-bucket to 3-bucket format")
                    self._save_buckets()
                else:
                    for key in self.buckets:
                        if key in saved:
                            self.buckets[key] = saved[key]
            except Exception as e:
                self._log_error(f"Failed to load buckets.json, using defaults: {e}")

    def _save_buckets(self):
        bucket_file = self.log_dir / "buckets.json"
        try:
            with open(bucket_file, "w") as f:
                json.dump(self.buckets, f, indent=2)
        except Exception as e:
            self._log_error(f"Save buckets error: {e}")

    # ==========================================
    # STOCK CLASSIFICATION (Dynamic)
    # ==========================================

    def assign_bucket(self, symbol: str) -> str:
        penny_threshold = self.settings.get("penny_price_threshold", 5.0)
        min_div_yield = self.settings.get("min_dividend_yield", 0.03)
        symbol_upper = symbol.upper()
        cache_key = symbol_upper

        is_in_dividend_list = symbol_upper in DIVIDEND_STOCKS
        is_in_growth_list = symbol_upper in GROWTH_STOCKS or symbol_upper in US_LONG_TERM

        if cache_key in self._stock_info_cache:
            cached = self._stock_info_cache[cache_key]
            age_hours = (datetime.now() - cached["timestamp"]).total_seconds() / 3600
            if age_hours < 24 and cached.get("bucket"):
                cached_bucket = cached.get("bucket")
                cached_price = cached.get("price")

                if cached_bucket != "dividend" and is_in_dividend_list:
                    self._log_error(f"[BUCKET FIX] {symbol_upper} cached as '{cached_bucket}' but is in DIVIDEND_STOCKS → correcting to 'dividend'")
                    cached["bucket"] = "dividend"
                    return "dividend"

                if cached_price is not None and cached_price < penny_threshold and cached_bucket != "penny":
                    self._log_error(f"[BUCKET FIX] {symbol_upper} cached as '{cached_bucket}' but price ${cached_price:.2f} < ${penny_threshold:.2f} → correcting to 'penny'")
                    cached["bucket"] = "penny"
                    return "penny"

                self._log_error(f"[BUCKET] {symbol_upper}: cache hit → {cached_bucket.upper()} (price={cached_price}, div_yield={cached.get('div_yield')}, age={age_hours:.1f}h)")
                return cached_bucket

        cached_price = None
        cached_div_yield = None
        if cache_key in self._stock_info_cache:
            cached_price = self._stock_info_cache[cache_key].get("price")
            cached_div_yield = self._stock_info_cache[cache_key].get("div_yield")

        if cached_price is None and YF_AVAILABLE:
            try:
                ticker = yf.Ticker(symbol_upper)
                info = ticker.info or {}
                fresh_price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
                if fresh_price is not None:
                    cached_price = fresh_price
                    self._log_error(f"[BUCKET] {symbol_upper}: fetched price=${cached_price:.2f} from yfinance")
                fresh_div = info.get('dividendYield')
                if fresh_div is not None:
                    cached_div_yield = fresh_div
                    self._log_error(f"[BUCKET] {symbol_upper}: fetched div_yield={cached_div_yield:.4f} ({cached_div_yield:.2%}) from yfinance")
            except Exception as e:
                self._log_error(f"[BUCKET] {symbol_upper}: yfinance fetch failed: {str(e)[:80]}")

        if cached_price is not None and cached_div_yield is None and YF_AVAILABLE:
            try:
                ticker = yf.Ticker(symbol_upper)
                info = ticker.info or {}
                fresh_div = info.get('dividendYield')
                if fresh_div is not None:
                    cached_div_yield = fresh_div
                    self._log_error(f"[BUCKET] {symbol_upper}: fetched div_yield={cached_div_yield:.4f} ({cached_div_yield:.2%}) from yfinance (second attempt)")
            except Exception:
                pass

        if cached_price is not None and cached_price < penny_threshold:
            bucket = "penny"
            self._log_error(f"[BUCKET] {symbol_upper}: price=${cached_price:.2f} < ${penny_threshold:.2f} → PENNY")
        elif cached_div_yield is not None and cached_div_yield >= min_div_yield:
            bucket = "dividend"
            self._log_error(f"[BUCKET] {symbol_upper}: yield={cached_div_yield:.2%} >= {min_div_yield:.2%} → DIVIDEND")
        elif cached_price is not None and cached_price >= penny_threshold:
            if cached_div_yield is not None and cached_div_yield > 0:
                bucket = "growth"
                self._log_error(f"[BUCKET] {symbol_upper}: yield={cached_div_yield:.2%} < {min_div_yield:.2%} threshold, price=${cached_price:.2f} → GROWTH")
            else:
                if is_in_dividend_list:
                    bucket = "dividend"
                    self._log_error(f"[BUCKET] {symbol_upper}: div_yield=Unknown, in DIVIDEND_STOCKS list → DIVIDEND")
                elif is_in_growth_list:
                    bucket = "growth"
                    self._log_error(f"[BUCKET] {symbol_upper}: div_yield=Unknown, in GROWTH_STOCKS list → GROWTH")
                else:
                    bucket = "growth"
                    self._log_error(f"[BUCKET] {symbol_upper}: div_yield=Unknown, not in any list, price=${cached_price:.2f} → GROWTH (default)")
        else:
            if is_in_dividend_list:
                bucket = "dividend"
                self._log_error(f"[BUCKET] {symbol_upper}: no price data, in DIVIDEND_STOCKS list → DIVIDEND")
            elif is_in_growth_list:
                bucket = "growth"
                self._log_error(f"[BUCKET] {symbol_upper}: no price data, in GROWTH_STOCKS/US_LONG_TERM list → GROWTH")
            else:
                bucket = "growth"
                self._log_error(f"[BUCKET] {symbol_upper}: no price data, not in any list → GROWTH (default)")

        self._stock_info_cache[cache_key] = {
            "price": cached_price,
            "div_yield": cached_div_yield,
            "bucket": bucket,
            "timestamp": datetime.now()
        }
        return bucket

    def classify_stock(self, symbol: str) -> str:
        penny_threshold = self.settings.get("penny_price_threshold", 5.0)
        min_div_yield = self.settings.get("min_dividend_yield", 0.03)
        symbol_upper = symbol.upper()
        price = None
        div_yield = None
        if self.api and self.connected:
            try:
                quote = self.api.get_latest_quote(symbol_upper)
                if quote:
                    price = (float(quote.ask_price) + float(quote.bid_price)) / 2
            except Exception:
                pass
        if YF_AVAILABLE:
            try:
                ticker = yf.Ticker(symbol_upper)
                info = ticker.info or {}
                if price is None:
                    price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
                div_yield = info.get('dividendYield')
            except Exception:
                pass
        if div_yield is None:
            if symbol_upper in DIVIDEND_STOCKS:
                div_yield = 0.03
            elif symbol_upper in GROWTH_STOCKS:
                div_yield = 0.0
        if price is not None and price < penny_threshold:
            bucket = "penny"
        elif div_yield is not None and div_yield >= min_div_yield:
            bucket = "dividend"
        elif price is not None and price >= penny_threshold:
            bucket = "growth"
        else:
            if symbol_upper in DIVIDEND_STOCKS:
                bucket = "dividend"
            elif symbol_upper in GROWTH_STOCKS or symbol_upper in US_LONG_TERM:
                bucket = "growth"
            else:
                bucket = "penny"
        self._stock_info_cache[symbol_upper] = {"price": price, "div_yield": div_yield, "bucket": bucket, "timestamp": datetime.now()}
        return bucket

    def get_bucket_icon(self, bucket: str) -> str:
        return BUCKET_ICONS.get(bucket, "⚪")

    def get_bucket_settings(self, bucket: str) -> dict:
        key = f"{bucket}_settings"
        bucket_specific = self.settings.get(key, {})
        defaults = {
            "stop_loss_pct": self.settings.get("stop_loss_pct", 0.05),
            "take_profit_pct": self.settings.get("take_profit_pct", 0.10),
            "trailing_stop_pct": self.settings.get("trailing_stop_pct", 0.03),
            "max_position_pct": self.settings.get("max_position_pct", 0.08),
            "rsi_oversold": self.settings.get("rsi_oversold", 30),
            "rsi_overbought": self.settings.get("rsi_overbought", 65),
            "min_confidence": self.settings.get("min_confidence", 0.25),
            "min_rvol": self.settings.get("min_rvol", 1.0),
        }
        defaults.update(bucket_specific)
        return defaults

    def debug_bucket(self, symbol: str) -> Dict:
        penny_threshold = self.settings.get("penny_price_threshold", 5.0)
        min_div_yield = self.settings.get("min_dividend_yield", 0.03)
        symbol_upper = symbol.upper()

        debug = {
            "symbol": symbol_upper,
            "penny_threshold": penny_threshold,
            "min_div_yield": min_div_yield,
            "in_dividend_list": symbol_upper in DIVIDEND_STOCKS,
            "in_growth_list": symbol_upper in GROWTH_STOCKS,
            "in_long_term_list": symbol_upper in US_LONG_TERM,
            "cached_price": None,
            "cached_div_yield": None,
            "yfinance_price": None,
            "yfinance_div_yield": None,
            "final_bucket": None,
            "log": [],
        }

        if symbol_upper in self._stock_info_cache:
            cached = self._stock_info_cache[symbol_upper]
            debug["cached_price"] = cached.get("price")
            debug["cached_div_yield"] = cached.get("div_yield")
            debug["cached_bucket"] = cached.get("bucket")
            debug["cached_age_hours"] = (datetime.now() - cached["timestamp"]).total_seconds() / 3600
            debug["log"].append(f"Cache hit: price={cached.get('price')}, div_yield={cached.get('div_yield')}, bucket={cached.get('bucket')}")

        if YF_AVAILABLE:
            try:
                ticker = yf.Ticker(symbol_upper)
                info = ticker.info or {}
                price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
                div_yield = info.get('dividendYield')
                debug["yfinance_price"] = price
                debug["yfinance_div_yield"] = div_yield
                debug["log"].append(f"yfinance: price={price}, div_yield={div_yield}")
            except Exception as e:
                debug["log"].append(f"yfinance error: {str(e)[:80]}")
        else:
            debug["log"].append("yfinance not available")

        old_cache = self._stock_info_cache.pop(symbol_upper, None)
        bucket = self.assign_bucket(symbol)
        debug["final_bucket"] = bucket
        debug["log"].append(f"Final classification: {bucket}")

        if old_cache:
            self._stock_info_cache[symbol_upper] = old_cache

        return debug

    def invalidate_bucket_cache(self):
        self._stock_info_cache = {}

    # ==========================================
    # BUCKET SYSTEM: DEPOSIT MONEY
    # ==========================================

    def deposit_money(self, amount: float) -> Dict:
        div_pct = self.settings.get("dividend_pct", 0.35)
        gro_pct = self.settings.get("growth_pct", 0.35)
        pen_pct = self.settings.get("penny_pct", 0.30)
        dividend_amount = round(amount * div_pct, 2)
        growth_amount = round(amount * gro_pct, 2)
        penny_amount = round(amount * pen_pct, 2)
        self.buckets["dividend"]["total_deposited"] += dividend_amount
        self.buckets["dividend"]["cash_allocated"] += dividend_amount
        self.buckets["growth"]["total_deposited"] += growth_amount
        self.buckets["growth"]["cash_allocated"] += growth_amount
        self.buckets["penny"]["total_deposited"] += penny_amount
        self.buckets["penny"]["cash_allocated"] += penny_amount
        entry = {"date": datetime.now().isoformat(), "amount": amount, "dividend": dividend_amount, "growth": growth_amount, "penny": penny_amount, "div_pct": div_pct, "gro_pct": gro_pct, "pen_pct": pen_pct}
        self.buckets["deposit_history"].append(entry)
        self.buckets["last_deposit_date"] = datetime.now().date().isoformat()
        self._save_buckets()
        if AUDIT_AVAILABLE:
            try:
                log_deposit_audit("system", amount, {"dividend": dividend_amount, "growth": growth_amount, "penny": penny_amount})
            except Exception:
                pass
        return {"status": "success", "amount": amount, "dividend": dividend_amount, "growth": growth_amount, "penny": penny_amount, "message": f"Deposited ${amount:,.2f}: 🟢 ${dividend_amount:,.2f} Dividend, 🔵 ${growth_amount:,.2f} Growth, 🔴 ${penny_amount:,.2f} Penny"}

    # ==========================================
    # BUCKET SYSTEM: GET OVERVIEW
    # ==========================================

    def get_bucket_overview(self) -> Dict:
        overview = {
            "dividend": {"value": 0, "positions": 0, "cash": 0, "total_deposited": 0, "unrealized_pl": 0, "dividends_earned": 0},
            "growth": {"value": 0, "positions": 0, "cash": 0, "total_deposited": 0, "unrealized_pl": 0, "profits_moved_in": 0},
            "penny": {"value": 0, "positions": 0, "cash": 0, "total_deposited": 0, "unrealized_pl": 0, "profits_to_growth": 0},
            "withdrawal": {"available": 0, "total_withdrawn": 0, "dividends_received": 0, "profits_extracted": 0},
            "original_capital": self.buckets.get("original_capital", self.settings.get("original_capital", 100000)),
            "total_profit": 0, "total_portfolio": 0, "withdrawable": 0, "profit_threshold_hit": False,
        }
        positions = self.get_positions()
        account = self.get_account_info()
        dividend_value = growth_value = penny_value = 0
        dividend_positions = growth_positions = penny_positions = []
        for pos in positions:
            symbol = pos["symbol"]
            bucket = self.assign_bucket(symbol)
            pos_value = float(pos.get("market_value", 0))
            if bucket == "dividend":
                dividend_value += pos_value
                dividend_positions.append(pos)
            elif bucket == "growth":
                growth_value += pos_value
                growth_positions.append(pos)
            else:
                penny_value += pos_value
                penny_positions.append(pos)
        total_equity = float(account.get("equity", 0)) if "error" not in account else 0
        total_cash = float(account.get("cash", 0)) if "error" not in account else 0
        original_capital = overview["original_capital"]
        withdrawal_cash = self.buckets["withdrawal"]["available"]
        trading_cash = max(0, total_cash - withdrawal_cash)
        div_pct = self.settings.get("dividend_pct", 0.35)
        gro_pct = self.settings.get("growth_pct", 0.35)
        pen_pct = self.settings.get("penny_pct", 0.30)
        total_pct = div_pct + gro_pct + pen_pct
        if total_pct <= 0:
            total_pct = 1
        overview["dividend"]["value"] = round(dividend_value + (trading_cash * div_pct / total_pct), 2)
        overview["dividend"]["positions"] = len(dividend_positions)
        overview["dividend"]["position_list"] = dividend_positions
        overview["dividend"]["cash"] = round(trading_cash * div_pct / total_pct, 2)
        overview["dividend"]["total_deposited"] = self.buckets["dividend"]["total_deposited"]
        overview["dividend"]["dividends_earned"] = self.buckets["dividend"].get("total_dividends_earned", 0)
        if dividend_value > 0:
            dv_cost = sum(float(p.get("avg_entry_price", 0)) * float(p.get("qty", 0)) for p in dividend_positions)
            overview["dividend"]["unrealized_pl"] = round(dividend_value - dv_cost, 2)
        overview["growth"]["value"] = round(growth_value + (trading_cash * gro_pct / total_pct), 2)
        overview["growth"]["positions"] = len(growth_positions)
        overview["growth"]["position_list"] = growth_positions
        overview["growth"]["cash"] = round(trading_cash * gro_pct / total_pct, 2)
        overview["growth"]["total_deposited"] = self.buckets["growth"]["total_deposited"]
        overview["growth"]["profits_moved_in"] = self.buckets["growth"].get("profits_moved_in", 0)
        if growth_value > 0:
            gr_cost = sum(float(p.get("avg_entry_price", 0)) * float(p.get("qty", 0)) for p in growth_positions)
            overview["growth"]["unrealized_pl"] = round(growth_value - gr_cost, 2)
        overview["penny"]["value"] = round(penny_value + (trading_cash * pen_pct / total_pct), 2)
        overview["penny"]["positions"] = len(penny_positions)
        overview["penny"]["position_list"] = penny_positions
        overview["penny"]["cash"] = round(trading_cash * pen_pct / total_pct, 2)
        overview["penny"]["total_deposited"] = self.buckets["penny"]["total_deposited"]
        overview["penny"]["profits_to_growth"] = self.buckets["penny"].get("profits_to_growth", 0)
        if penny_value > 0:
            pn_cost = sum(float(p.get("avg_entry_price", 0)) * float(p.get("qty", 0)) for p in penny_positions)
            overview["penny"]["unrealized_pl"] = round(penny_value - pn_cost, 2)
        overview["withdrawal"]["available"] = withdrawal_cash
        overview["withdrawal"]["total_withdrawn"] = self.buckets["withdrawal"]["total_withdrawn"]
        overview["withdrawal"]["dividends_received"] = self.buckets["withdrawal"]["dividends_received"]
        overview["withdrawal"]["profits_extracted"] = self.buckets["withdrawal"]["profits_extracted"]
        overview["total_portfolio"] = round(total_equity, 2)
        overview["total_profit"] = round(total_equity - original_capital, 2)
        overview["withdrawable"] = withdrawal_cash
        profit_pct = (total_equity / original_capital - 1) * 100 if original_capital > 0 else 0
        use_pct = self.settings.get("use_pct_threshold", False)
        if use_pct:
            threshold_hit = profit_pct >= (self.settings.get("profit_threshold_pct", 0.20) * 100)
        else:
            threshold_hit = overview["total_profit"] >= self.settings.get("profit_threshold_amount", 20000)
        overview["profit_threshold_hit"] = threshold_hit
        overview["profit_pct"] = round(profit_pct, 2)
        overview["deposit_history"] = self.buckets.get("deposit_history", [])
        overview["extraction_history"] = self.buckets.get("extraction_history", [])
        overview["dividend_history"] = self.buckets.get("dividend_history", [])
        return overview

    # ==========================================
    # BUCKET SYSTEM: EXTRACT PROFITS
    # ==========================================

    def extract_profits(self) -> Dict:
        overview = self.get_bucket_overview()
        total_profit = overview["total_profit"]
        original_capital = overview["original_capital"]
        use_pct = self.settings.get("use_pct_threshold", False)
        if use_pct:
            threshold_pct = self.settings.get("profit_threshold_pct", 0.20)
            threshold_amount = original_capital * threshold_pct
        else:
            threshold_amount = self.settings.get("profit_threshold_amount", 20000)
        if total_profit < threshold_amount:
            return {"status": "below_threshold", "message": f"Profit ${total_profit:,.2f} is below threshold ${threshold_amount:,.2f}", "profit": total_profit, "threshold": threshold_amount}
        positions = self.get_positions()
        if not positions:
            return {"status": "no_positions", "message": "No positions to sell"}
        profitable = []
        for pos in positions:
            pl_pct = float(pos.get("unrealized_plpc", 0))
            if pl_pct > 0:
                profitable.append({"symbol": pos["symbol"], "pl_pct": pl_pct, "market_value": float(pos.get("market_value", 0)), "qty": float(pos.get("qty", 0)), "current_price": float(pos.get("current_price", 0)), "entry_price": float(pos.get("avg_entry_price", 0))})
        profitable.sort(key=lambda x: x["pl_pct"], reverse=True)
        amount_to_free = threshold_amount
        sold = []
        remaining = amount_to_free
        for pos in profitable:
            if remaining <= 0:
                break
            try:
                result = self.close_position(pos["symbol"], reason=f"Profit extraction: {pos['pl_pct']:.1%} gain")
                if "error" not in result:
                    freed = pos["market_value"]
                    remaining -= freed
                    sold.append({"symbol": pos["symbol"], "shares": pos["qty"], "profit_pct": pos["pl_pct"], "value_freed": round(freed, 2), "bucket": self.assign_bucket(pos["symbol"])})
            except Exception as e:
                self._log_error(f"Profit extraction sell error: {e}")
        total_freed = sum(s["value_freed"] for s in sold)
        self.buckets["withdrawal"]["available"] += total_freed
        self.buckets["withdrawal"]["profits_extracted"] += total_freed
        extraction_entry = {"date": datetime.now().isoformat(), "profit_at_extraction": total_profit, "amount_extracted": total_freed, "threshold": threshold_amount, "positions_sold": sold}
        self.buckets["extraction_history"].append(extraction_entry)
        self._save_buckets()
        return {"status": "extracted", "message": f"Extracted ${total_freed:,.2f} profit from {len(sold)} positions", "amount_extracted": total_freed, "positions_sold": sold, "withdrawal_pot": self.buckets["withdrawal"]["available"]}

    # ==========================================
    # NEW: SELL EVERYTHING
    # ==========================================

    def sell_everything(self) -> Dict:
        """Sell all open positions and move proceeds to Withdrawal Pot (LOCKED from trading)."""
        if not self.api or not self.connected:
            return {"status": "error", "message": "Not connected to Alpaca"}

        positions = self.get_positions()
        if not positions:
            return {"status": "no_positions", "message": "No open positions to sell"}

        sold = []
        total_freed = 0.0

        for pos in positions:
            symbol = pos["symbol"]
            bucket = self.assign_bucket(symbol)
            try:
                result = self.close_position(symbol, reason="Sell Everything: Moving to Withdrawal Pot")
                if "error" not in result:
                    freed = float(pos.get("market_value", 0))
                    total_freed += freed
                    sold.append({
                        "symbol": symbol,
                        "market_value": freed,
                        "pl_pct": float(pos.get("unrealized_plpc", 0)),
                        "bucket": bucket
                    })
            except Exception as e:
                self._log_error(f"Sell Everything error for {symbol}: {e}")

        # Move freed cash to Withdrawal Pot
        if total_freed > 0:
            self.buckets["withdrawal"]["available"] += total_freed
            self.buckets["withdrawal"]["profits_extracted"] += total_freed

            extraction_entry = {
                "date": datetime.now().isoformat(),
                "type": "sell_everything",
                "total_freed": total_freed,
                "positions_sold": len(sold),
            }
            self.buckets["extraction_history"].append(extraction_entry)
            self._save_buckets()

        return {
            "status": "sold",
            "message": f"Sold {len(sold)} positions, ${total_freed:,.2f} moved to Withdrawal Pot (🔒 LOCKED)",
            "positions_sold": sold,
            "total_freed": total_freed,
            "withdrawal_pot": self.buckets["withdrawal"]["available"]
        }

    # ==========================================
    # NEW: MOVE FROM WITHDRAWAL
    # ==========================================

    def move_from_withdrawal(self, amount: float, target_bucket: str) -> Dict:
        """Move money from Withdrawal Pot back to a trading bucket."""
        withdrawal_available = self.buckets["withdrawal"]["available"]

        if amount <= 0:
            return {"status": "error", "message": "Amount must be positive"}

        # Allow small rounding tolerance (e.g., $0.01) for currency rounding
        if amount > withdrawal_available + 0.01:
            return {"status": "error", "message": f"Amount ${amount:,.2f} exceeds Withdrawal Pot balance ${withdrawal_available:,.2f}"}

        # Cap amount to actual available (handles rounding up from UI)
        actual_amount = min(amount, withdrawal_available)

        if target_bucket not in ["dividend", "growth", "penny"]:
            return {"status": "error", "message": f"Invalid bucket: {target_bucket}"}

        self.buckets["withdrawal"]["available"] -= actual_amount
        self.buckets[target_bucket]["cash_allocated"] += actual_amount
        self.buckets[target_bucket]["total_deposited"] += actual_amount

        entry = {
            "date": datetime.now().isoformat(),
            "amount": actual_amount,
            "from": "withdrawal",
            "to": target_bucket,
            "type": "move_from_withdrawal"
        }
        self.buckets["deposit_history"].append(entry)
        self._save_buckets()

        bucket_icon = BUCKET_ICONS.get(target_bucket, "⚪")
        return {
            "status": "success",
            "message": f"Moved ${actual_amount:,.2f} from 🟡 Withdrawal → {bucket_icon} {target_bucket.title()}",
            "amount_moved": actual_amount,
            "target_bucket": target_bucket,
            "withdrawal_remaining": self.buckets["withdrawal"]["available"]
        }

    # ==========================================
    # NEW: REDISTRIBUTE FROM WITHDRAWAL
    # ==========================================

    def redistribute_from_withdrawal(self) -> Dict:
        """Redistribute Withdrawal Pot across all 3 buckets based on allocation %."""
        withdrawal_available = self.buckets["withdrawal"]["available"]

        if withdrawal_available <= 0:
            return {"status": "error", "message": "No money in Withdrawal Pot to redistribute"}

        div_pct = self.settings.get("dividend_pct", 0.35)
        gro_pct = self.settings.get("growth_pct", 0.35)
        pen_pct = self.settings.get("penny_pct", 0.30)
        total_pct = div_pct + gro_pct + pen_pct
        if total_pct <= 0:
            return {"status": "error", "message": "Allocation percentages must add up to more than 0%"}

        div_amount = round(withdrawal_available * div_pct / total_pct, 2)
        gro_amount = round(withdrawal_available * gro_pct / total_pct, 2)
        pen_amount = round(withdrawal_available * pen_pct / total_pct, 2)

        # Adjust for rounding
        remainder = round(withdrawal_available - div_amount - gro_amount - pen_amount, 2)
        if remainder > 0:
            pen_amount += remainder

        self.buckets["withdrawal"]["available"] = 0
        self.buckets["dividend"]["cash_allocated"] += div_amount
        self.buckets["dividend"]["total_deposited"] += div_amount
        self.buckets["growth"]["cash_allocated"] += gro_amount
        self.buckets["growth"]["total_deposited"] += gro_amount
        self.buckets["penny"]["cash_allocated"] += pen_amount
        self.buckets["penny"]["total_deposited"] += pen_amount

        entry = {
            "date": datetime.now().isoformat(),
            "amount": withdrawal_available,
            "dividend": div_amount,
            "growth": gro_amount,
            "penny": pen_amount,
            "type": "redistribute_from_withdrawal"
        }
        self.buckets["deposit_history"].append(entry)
        self._save_buckets()

        return {
            "status": "success",
            "message": f"Redistributed ${withdrawal_available:,.2f} from Withdrawal: 🟢 ${div_amount:,.2f} Dividend, 🔵 ${gro_amount:,.2f} Growth, 🔴 ${pen_amount:,.2f} Penny",
            "dividend": div_amount,
            "growth": gro_amount,
            "penny": pen_amount,
            "total_redistributed": withdrawal_available,
            "withdrawal_remaining": 0
        }

    # ==========================================
    # BUCKET SYSTEM: MOVE PROFITS
    # ==========================================

    def move_profits(self) -> Dict:
        results = {}
        if self.settings.get("penny_profits_to_growth", True):
            penny_profits = self._calculate_bucket_profits("penny")
            if penny_profits > 0:
                self.buckets["growth"]["profits_moved_in"] = self.buckets["growth"].get("profits_moved_in", 0) + penny_profits
                self.buckets["penny"]["profits_to_growth"] = self.buckets["penny"].get("profits_to_growth", 0) + penny_profits
                self.buckets["growth"]["cash_allocated"] = self.buckets["growth"].get("cash_allocated", 0) + penny_profits
                results["penny_to_growth"] = penny_profits
        if self.settings.get("growth_profits_to_dividend", True):
            growth_profits = self._calculate_bucket_profits("growth")
            if growth_profits > 0:
                self.buckets["dividend"]["cash_allocated"] = self.buckets["dividend"].get("cash_allocated", 0) + growth_profits
                results["growth_to_dividend"] = growth_profits
        self._save_buckets()
        return results

    def _calculate_bucket_profits(self, bucket: str) -> float:
        total_profit = 0.0
        for t in self.trade_log:
            if t.get("side") in ["sell", "close"] and t.get("bucket") == bucket:
                symbol = t.get("symbol", "")
                buy_entry = None
                for bt in reversed(self.trade_log):
                    if bt.get("symbol") == symbol and bt.get("side") == "buy":
                        buy_entry = bt
                        break
                if buy_entry:
                    buy_price = float(buy_entry.get("price", 0))
                    sell_price = float(t.get("price", 0))
                    qty = float(t.get("qty", 0))
                    if buy_price > 0:
                        profit = (sell_price - buy_price) * qty
                        if profit > 0:
                            total_profit += profit
        return total_profit

    # ==========================================
    # BUCKET SYSTEM: CHECK DIVIDENDS
    # ==========================================

    def check_dividends(self) -> Dict:
        if not self.api or not self.connected:
            return {"status": "error", "message": "Not connected"}
        try:
            activities = self.api.get_activities(activity_types="DIV")
            dividends_found = 0.0
            dividend_details = []
            for activity in activities:
                symbol = getattr(activity, 'symbol', '')
                amount = float(getattr(activity, 'net_amount', 0) or 0)
                act_date = str(getattr(activity, 'date', ''))
                if amount > 0:
                    existing_dates = [d.get("date", "") for d in self.buckets.get("dividend_history", [])]
                    existing_amounts = [d.get("amount", 0) for d in self.buckets.get("dividend_history", [])]
                    is_duplicate = False
                    for i, ed in enumerate(existing_dates):
                        if ed == act_date and i < len(existing_amounts) and abs(existing_amounts[i] - amount) < 0.01:
                            is_duplicate = True
                            break
                    if not is_duplicate:
                        dividends_found += amount
                        bucket = self.assign_bucket(symbol)
                        dividend_details.append({"symbol": symbol, "amount": amount, "date": act_date, "bucket": bucket})
                        self.buckets.setdefault("dividend_history", []).append({"date": act_date, "symbol": symbol, "amount": amount, "status": "received", "bucket": bucket, "moved_to_withdrawal": self.settings.get("dividends_to_withdrawal", True), "recorded_at": datetime.now().isoformat()})
            if dividends_found > 0 and self.settings.get("dividends_to_withdrawal", True):
                self.buckets["withdrawal"]["dividends_received"] += dividends_found
                self.buckets["withdrawal"]["available"] += dividends_found
                self.buckets["dividend"]["total_dividends_earned"] = self.buckets["dividend"].get("total_dividends_earned", 0) + dividends_found
            self._save_buckets()
            return {"status": "success", "dividends_found": dividends_found, "details": dividend_details, "message": f"Found ${dividends_found:,.2f} in dividends" if dividends_found > 0 else "No new dividends"}
        except Exception as e:
            self._log_error(f"Dividend check error: {e}")
            return {"status": "error", "message": str(e)}

    def get_dividend_history(self) -> List[Dict]:
        return self.buckets.get("dividend_history", [])

    # ==========================================
    # BUCKET SYSTEM: GET AVAILABLE TRADING CASH
    # ==========================================

    def get_available_trading_cash(self) -> float:
        account = self.get_account_info()
        if "error" in account:
            return 0
        total_cash = float(account.get("cash", 0))
        withdrawal_cash = self.buckets["withdrawal"]["available"]
        return round(max(0, total_cash - withdrawal_cash), 2)

    # ==========================================
    # ALPACA UNIVERSE: AUTO BUILD WATCHLIST
    # ==========================================

    def get_alpaca_universe(self, min_price: float = 5.0, max_price: float = 500.0) -> List[Dict]:
        if not self.api or not self.connected:
            return []
        try:
            all_assets = self.api.list_assets(status='active')
            candidates = []
            for asset in all_assets:
                if not asset.tradable:
                    continue
                symbol = asset.symbol
                if len(symbol) > 5 or '.' in symbol or '-' in symbol:
                    continue
                if any(p in symbol for p in ['ETF', 'ETN', 'PRN']):
                    continue
                if asset.exchange not in ['NYSE', 'NASDAQ', 'ARCA', 'AMEX', 'BATS']:
                    continue
                candidates.append({'symbol': symbol, 'name': getattr(asset, 'name', '') or '', 'exchange': asset.exchange})
            symbols = [c['symbol'] for c in candidates]
            price_filtered = []
            batch_size = 200
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i + batch_size]
                try:
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=5)
                    bars = self.api.get_bars(batch, tradeapi.TimeFrame.Day, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), feed='iex')
                    latest = {}
                    for bar in bars:
                        sym = bar.S
                        if sym not in latest or bar.t > latest[sym]['time']:
                            latest[sym] = {'price': bar.c, 'volume': bar.v, 'time': bar.t}
                    for sym, data in latest.items():
                        if min_price <= data['price'] <= max_price:
                            price_filtered.append({'symbol': sym, 'price': round(data['price'], 2), 'volume': data['volume'], 'bucket': self.assign_bucket(sym)})
                except Exception as e:
                    self._log_error(f"Universe batch error: {e}")
                    time.sleep(0.5)
            price_filtered.sort(key=lambda x: x.get('volume', 0), reverse=True)
            return price_filtered
        except Exception as e:
            self._log_error(f"Universe fetch error: {e}")
            return []

    def auto_build_watchlist(self, top_n: int = 100, min_price: float = 5.0, max_price: float = 500.0) -> List[str]:
        universe = self.get_alpaca_universe(min_price=min_price, max_price=max_price)
        if not universe:
            self._log_error("Universe empty, keeping current watchlist")
            return self.settings.get("watchlist", [])
        watchlist = [s['symbol'] for s in universe[:top_n]]
        for ds in DIVIDEND_STOCKS:
            if ds not in watchlist:
                watchlist.append(ds)
        for gs in GROWTH_STOCKS:
            if gs not in watchlist:
                watchlist.append(gs)
        manual = self.settings.get("watchlist", [])
        for s in manual:
            if s not in watchlist:
                watchlist.append(s)
        self.settings["watchlist"] = watchlist
        self.settings["watchlist_auto"] = True
        self.save_settings()
        return watchlist

    # ==========================================
    # PERSISTENCE: SAVE / LOAD ALL DATA
    # ==========================================

    def save_settings(self):
        settings_file = self.log_dir / "settings.json"
        try:
            with open(settings_file, "w") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            self._log_error(f"Save settings error: {e}")

    def load_settings(self):
        settings_file = self.log_dir / "settings.json"
        if settings_file.exists():
            try:
                with open(settings_file, "r") as f:
                    saved = json.load(f)
                if "long_term_pct" in saved and "dividend_pct" not in saved:
                    saved["dividend_pct"] = saved.get("long_term_pct", 0.60) * 0.55
                    saved["growth_pct"] = saved.get("long_term_pct", 0.60) * 0.45
                    saved["penny_pct"] = saved.get("penny_pct", 0.40)
                    del saved["long_term_pct"]
                self.settings.update(saved)
                return True
            except Exception:
                return False
        return False

    def reset_settings(self):
        self.settings = {
            "mode": "quick", "max_positions": 10, "max_position_pct": 0.08,
            "daily_loss_limit_pct": 0.03, "stop_loss_pct": 0.05, "take_profit_pct": 0.15,
            "trailing_stop_pct": 0.03, "rsi_oversold": 30, "rsi_overbought": 70,
            "min_rvol": 1.5, "min_confidence": 0.25, "max_same_sector": 3,
            "scan_interval_min": 5, "watchlist": US_QUICK_TURNOVER.copy(),
            "slippage_pct": 0.05, "sec_fee_pct": 0.00002,
            "deposit_amount": 1000, "dividend_pct": 0.35, "growth_pct": 0.35, "penny_pct": 0.30,
            "min_dividend_yield": 0.03, "penny_price_threshold": 5.0,
            "profit_threshold_amount": 10000, "profit_threshold_pct": 0.10,
            "use_pct_threshold": True, "auto_extract_profits": True,
            "penny_profits_to_growth": True, "growth_profits_to_dividend": True,
            "dividends_to_withdrawal": True, "original_capital": 100000,
            "watchlist_auto": False, "watchlist_auto_count": 100,
            "discord_privacy_mode": True,
            "use_advanced_signals": True, "use_multi_timeframe": False,
            "use_vix_filter": True, "vix_max_threshold": 28.0,
            "use_atr_position_sizing": True, "atr_risk_pct": 0.01,
            "signal_weights": {"rsi": 1.0, "macd": 1.2, "bollinger": 0.8, "ma_cross": 1.5, "volume": 0.6, "atr": 0.5},
            "penny_settings": {
                "stop_loss_pct": 0.03, "take_profit_pct": 0.08, "trailing_stop_pct": 0.02,
                "max_position_pct": 0.04, "rsi_oversold": 25, "rsi_overbought": 60,
                "min_confidence": 0.30, "min_rvol": 1.5,
            },
            "growth_settings": {
                "stop_loss_pct": 0.06, "take_profit_pct": 0.12, "trailing_stop_pct": 0.04,
                "max_position_pct": 0.08, "rsi_oversold": 30, "rsi_overbought": 65,
                "min_confidence": 0.25, "min_rvol": 1.0,
            },
            "dividend_settings": {
                "stop_loss_pct": 0.08, "take_profit_pct": 0.15, "trailing_stop_pct": 0.05,
                "max_position_pct": 0.08, "rsi_oversold": 35, "rsi_overbought": 70,
                "min_confidence": 0.20, "min_rvol": 0.8,
            },
        }
        self.invalidate_bucket_cache()
        self.save_settings()

    def _load_trade_log(self):
        try:
            from core.database import load_trades_from_db
            username = getattr(self, '_username', None)
            if username:
                db_trades = load_trades_from_db(username, limit=5000)
                if db_trades:
                    self.trade_log = db_trades
                    return
        except Exception as e:
            self._log_error(f"Load trades from DB failed: {e}")
        log_file = self.log_dir / "trade_log.json"
        if log_file.exists():
            try:
                with open(log_file, "r") as f:
                    self.trade_log = json.load(f)
            except Exception:
                self.trade_log = []

    def _save_trade_log(self):
        log_file = self.log_dir / "trade_log.json"
        try:
            with open(log_file, "w") as f:
                json.dump(self.trade_log, f, indent=2)
        except Exception as e:
            self._log_error(f"Save log error: {e}")
        try:
            from core.database import save_trade_to_db
            username = getattr(self, '_username', None)
            if username and self.trade_log:
                last_trade = self.trade_log[-1]
                save_trade_to_db(username, last_trade)
        except Exception as e:
            self._log_error(f"Save trade to DB error: {e}")

    def _load_equity_snapshots(self):
        snap_file = self.log_dir / "equity_snapshots.json"
        if snap_file.exists():
            try:
                with open(snap_file, "r") as f:
                    self.equity_snapshots = json.load(f)
            except Exception:
                self.equity_snapshots = []

    def _save_equity_snapshots(self):
        snap_file = self.log_dir / "equity_snapshots.json"
        try:
            with open(snap_file, "w") as f:
                json.dump(self.equity_snapshots[-365:], f, indent=2)
        except Exception as e:
            self._log_error(f"Save equity error: {e}")

    def _load_signal_history(self):
        sig_file = self.log_dir / "signal_history.json"
        if sig_file.exists():
            try:
                with open(sig_file, "r") as f:
                    self.signal_history = json.load(f)
            except Exception:
                self.signal_history = []

    def _save_signal_history(self):
        sig_file = self.log_dir / "signal_history.json"
        try:
            with open(sig_file, "w") as f:
                json.dump(self.signal_history[-1000:], f, indent=2)
        except Exception as e:
            self._log_error(f"Save signal history error: {e}")

    def _load_performance_metrics(self):
        metrics_file = self.log_dir / "performance_metrics.json"
        if metrics_file.exists():
            try:
                with open(metrics_file, "r") as f:
                    self.performance_metrics = json.load(f)
            except Exception:
                self.performance_metrics = {}

    def _save_performance_metrics(self):
        metrics_file = self.log_dir / "performance_metrics.json"
        try:
            with open(metrics_file, "w") as f:
                json.dump(self.performance_metrics, f, indent=2)
        except Exception as e:
            self._log_error(f"Save metrics error: {e}")

    # ==========================================
    # EQUITY SNAPSHOTS
    # ==========================================

    def record_equity_snapshot(self):
        try:
            today = datetime.now().date().isoformat()
            if self.equity_snapshots and self.equity_snapshots[-1].get("date") == today:
                snap = self.equity_snapshots[-1]
            else:
                snap = {"date": today}
            account = self.get_account_info()
            if "error" in account:
                return
            snap["portfolio_value"] = float(account.get("equity", 0))
            snap["cash"] = float(account.get("cash", 0))
            snap["buying_power"] = float(account.get("buying_power", 0))
            snap["daily_pnl"] = round(self.daily_pnl, 2)
            snap["positions_count"] = len(self.get_positions())
            bucket_ov = self.get_bucket_overview()
            snap["dividend_value"] = bucket_ov["dividend"]["value"]
            snap["growth_value"] = bucket_ov["growth"]["value"]
            snap["penny_value"] = bucket_ov["penny"]["value"]
            snap["withdrawal_value"] = bucket_ov["withdrawal"]["available"]
            snap["total_profit"] = bucket_ov["total_profit"]
            if len(self.equity_snapshots) >= 2:
                prev_value = self.equity_snapshots[-2].get("portfolio_value", snap["portfolio_value"])
                if prev_value > 0:
                    snap["daily_return_pct"] = round(((snap["portfolio_value"] - prev_value) / prev_value) * 100, 4)
                else:
                    snap["daily_return_pct"] = 0
            else:
                snap["daily_return_pct"] = 0
            try:
                spy_data = yf.Ticker("SPY").history(period="1d")
                if not spy_data.empty:
                    spy_close = float(spy_data['Close'].iloc[-1])
                    snap["spy_price"] = round(spy_close, 2)
                    if self._spy_start_value is None:
                        self._spy_start_value = spy_close
                        self._spy_start_date = today
                    snap["spy_start_value"] = self._spy_start_value
                    if self._spy_start_value > 0:
                        snap["spy_return_pct"] = round(((spy_close - self._spy_start_value) / self._spy_start_value) * 100, 4)
            except Exception:
                pass
            if self._portfolio_start_value is None:
                self._portfolio_start_value = snap["portfolio_value"]
                snap["portfolio_start_value"] = snap["portfolio_value"]
            else:
                snap["portfolio_start_value"] = self._portfolio_start_value
            if self._portfolio_start_value > 0:
                snap["portfolio_return_pct"] = round(((snap["portfolio_value"] - self._portfolio_start_value) / self._portfolio_start_value) * 100, 4)
            if len(self.equity_snapshots) > 0 and self.equity_snapshots[-1].get("date") == today:
                self.equity_snapshots[-1] = snap
            else:
                self.equity_snapshots.append(snap)
            if "long_term_value" in snap and "dividend_value" not in snap:
                snap["dividend_value"] = snap.pop("long_term_value", 0)
                snap["growth_value"] = 0
            self._save_equity_snapshots()
        except Exception as e:
            self._log_error(f"Equity snapshot error: {e}")

    # ==========================================
    # SIGNAL HISTORY
    # ==========================================

    def record_signal(self, signal: Dict, action: str, reason: str = ""):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "symbol": signal.get("symbol", ""),
            "signal_type": signal.get("signal", ""),
            "confidence": signal.get("confidence", 0),
            "rsi": signal.get("rsi", 0),
            "rvol": signal.get("rvol", 0),
            "price": signal.get("price", 0),
            "reason": signal.get("reason", ""),
            "action_taken": action,
            "rejection_reason": reason if action == "rejected" else "",
            "tier": self._get_tier(signal),
            "sector": SECTOR_MAP.get(signal.get("symbol", ""), "Unknown"),
            "bucket": self.assign_bucket(signal.get("symbol", "")),
        }
        self.signal_history.append(entry)
        self._save_signal_history()

    def _get_tier(self, signal: Dict) -> str:
        rsi = signal.get("rsi", 50)
        rvol = signal.get("rvol", 0)
        oversold = self.settings["rsi_oversold"]
        overbought = self.settings["rsi_overbought"]
        min_rvol = self.settings["min_rvol"]
        if signal.get("signal") == "BUY":
            if rsi < oversold and rvol >= min_rvol:
                return "Tier 1"
            elif rsi < (oversold + 5) and rvol >= (min_rvol * 1.3):
                return "Tier 2"
            else:
                return "Tier 3"
        elif signal.get("signal") == "SELL":
            if rsi > overbought and rvol >= min_rvol:
                return "Tier 1"
            elif rsi > (overbought - 5) and rvol >= (min_rvol * 1.3):
                return "Tier 2"
            else:
                return "Tier 3"
        return "Unknown"

    # ==========================================
    # PERFORMANCE METRICS
    # ==========================================

    def calculate_performance(self) -> Dict:
        metrics = {
            "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
            "win_rate": 0, "avg_win_pct": 0, "avg_loss_pct": 0,
            "total_return_pct": 0, "spy_return_pct": 0, "outperformance_pct": 0,
            "max_drawdown_pct": 0, "sharpe_ratio": 0, "profit_factor": 0,
            "avg_holding_days": 0, "max_consecutive_wins": 0,
            "max_consecutive_losses": 0, "current_streak": "",
            "by_tier": {"Tier 1": {"trades": 0, "wins": 0, "return_pct": 0}, "Tier 2": {"trades": 0, "wins": 0, "return_pct": 0}, "Tier 3": {"trades": 0, "wins": 0, "return_pct": 0}},
            "by_sector": {},
            "by_bucket": {"dividend": {"trades": 0, "wins": 0, "return_pct": 0}, "growth": {"trades": 0, "wins": 0, "return_pct": 0}, "penny": {"trades": 0, "wins": 0, "return_pct": 0}},
            "signals_found": 0, "signals_executed": 0, "signals_rejected": 0,
            "rejection_rate": 0, "net_cost_impact_pct": 0,
            "total_slippage": 0, "total_fees": 0,
            "equity_curve": [], "daily_returns": [],
            "worst_day_pct": 0, "best_day_pct": 0,
            "withdrawal_pot": 0, "total_profits_extracted": 0,
            "total_dividends_earned": 0,
            "sortino_ratio": 0, "calmar_ratio": 0, "omega_ratio": 0,
            "calculation_date": datetime.now().isoformat(),
        }
        completed = []
        buys = {}
        for t in self.trade_log:
            if t.get("side") == "buy":
                buys[t["symbol"]] = {
                    "entry_price": t.get("price", 0), "entry_time": t.get("timestamp", ""),
                    "qty": t.get("qty", 0), "confidence": t.get("confidence", 0),
                    "reason": t.get("reason", ""), "estimated_cost": t.get("estimated_cost", 0),
                    "bucket": t.get("bucket", self.assign_bucket(t["symbol"])),
                }
            elif t.get("side") in ["sell", "close"]:
                if t["symbol"] in buys:
                    buy_info = buys[t["symbol"]]
                    entry = buy_info["entry_price"]
                    exit_p = t.get("price", 0)
                    if entry > 0 and exit_p > 0:
                        ret_pct = ((exit_p - entry) / entry) * 100
                        slippage_cost = entry * (self.settings.get("slippage_pct", 0.05) / 100) * buy_info["qty"]
                        slippage_cost += exit_p * (self.settings.get("slippage_pct", 0.05) / 100) * t.get("qty", buy_info["qty"])
                        sec_fee = exit_p * (self.settings.get("sec_fee_pct", 0.00002) / 100) * t.get("qty", buy_info["qty"])
                        net_ret_pct = ret_pct - (self.settings.get("slippage_pct", 0.05) * 2)
                        completed.append({
                            "symbol": t["symbol"], "entry_price": entry, "exit_price": exit_p,
                            "return_pct": ret_pct, "net_return_pct": net_ret_pct,
                            "entry_time": buy_info["entry_time"], "exit_time": t.get("timestamp", ""),
                            "confidence": buy_info["confidence"], "side": t.get("side", ""),
                            "reason": t.get("reason", ""), "slippage": slippage_cost, "fees": sec_fee,
                            "bucket": buy_info.get("bucket", "penny"),
                        })
                        del buys[t["symbol"]]
        metrics["total_trades"] = len(completed)
        wins = [t for t in completed if t["return_pct"] > 0]
        losses = [t for t in completed if t["return_pct"] <= 0]
        metrics["winning_trades"] = len(wins)
        metrics["losing_trades"] = len(losses)
        if completed:
            metrics["win_rate"] = round(len(wins) / len(completed) * 100, 1)
            metrics["avg_win_pct"] = round(sum(t["return_pct"] for t in wins) / len(wins), 2) if wins else 0
            metrics["avg_loss_pct"] = round(sum(t["return_pct"] for t in losses) / len(losses), 2) if losses else 0
            total_wins = sum(t["return_pct"] for t in wins)
            total_losses = abs(sum(t["return_pct"] for t in losses))
            metrics["profit_factor"] = round(total_wins / total_losses, 2) if total_losses > 0 else float('inf') if total_wins > 0 else 0
            metrics["total_slippage"] = round(sum(t["slippage"] for t in completed), 2)
            metrics["total_fees"] = round(sum(t["fees"] for t in completed), 4)
            metrics["net_cost_impact_pct"] = round(metrics["total_slippage"] + metrics["total_fees"], 4)
            streak = 0; max_wins = 0; max_losses = 0; current_type = None
            for t in completed:
                if t["return_pct"] > 0:
                    if current_type == "win": streak += 1
                    else: streak = 1; current_type = "win"
                    max_wins = max(max_wins, streak)
                else:
                    if current_type == "loss": streak += 1
                    else: streak = 1; current_type = "loss"
                    max_losses = max(max_losses, streak)
            metrics["max_consecutive_wins"] = max_wins
            metrics["max_consecutive_losses"] = max_losses
            metrics["current_streak"] = f"{max_wins}W / {max_losses}L"
            for t in completed:
                tier = "Tier 2"
                for sig in reversed(self.signal_history):
                    if sig.get("symbol") == t["symbol"] and sig.get("action_taken") == "executed":
                        tier = sig.get("tier", "Tier 2"); break
                if tier not in metrics["by_tier"]: tier = "Tier 2"
                metrics["by_tier"][tier]["trades"] += 1
                if t["return_pct"] > 0: metrics["by_tier"][tier]["wins"] += 1
                metrics["by_tier"][tier]["return_pct"] += t["return_pct"]
            for t in completed:
                sector = SECTOR_MAP.get(t["symbol"], "Unknown")
                if sector not in metrics["by_sector"]: metrics["by_sector"][sector] = {"trades": 0, "wins": 0, "return_pct": 0}
                metrics["by_sector"][sector]["trades"] += 1
                if t["return_pct"] > 0: metrics["by_sector"][sector]["wins"] += 1
                metrics["by_sector"][sector]["return_pct"] += t["return_pct"]
            for t in completed:
                bucket = t.get("bucket", "penny")
                if bucket == "long_term": bucket = "dividend"
                if bucket not in metrics["by_bucket"]: bucket = "penny"
                metrics["by_bucket"][bucket]["trades"] += 1
                if t["return_pct"] > 0: metrics["by_bucket"][bucket]["wins"] += 1
                metrics["by_bucket"][bucket]["return_pct"] += t["return_pct"]
        if len(self.equity_snapshots) >= 2:
            values = [s["portfolio_value"] for s in self.equity_snapshots if "portfolio_value" in s]
            if values:
                metrics["total_return_pct"] = round(((values[-1] - values[0]) / values[0]) * 100, 2)
                spy_returns = [s for s in self.equity_snapshots if "spy_return_pct" in s]
                if spy_returns: metrics["spy_return_pct"] = spy_returns[-1]["spy_return_pct"]
                metrics["outperformance_pct"] = round(metrics["total_return_pct"] - metrics["spy_return_pct"], 2)
                peak = values[0]; max_dd = 0
                for v in values:
                    if v > peak: peak = v
                    dd = ((peak - v) / peak) * 100
                    max_dd = max(max_dd, dd)
                metrics["max_drawdown_pct"] = round(max_dd, 2)
                daily_returns = []
                for i in range(1, len(values)):
                    if values[i-1] > 0:
                        daily_returns.append((values[i] - values[i-1]) / values[i-1])
                if daily_returns:
                    metrics["daily_returns"] = [round(r * 100, 4) for r in daily_returns]
                    avg_ret = sum(daily_returns) / len(daily_returns)
                    std_ret = sqrt(sum((r - avg_ret) ** 2 for r in daily_returns) / len(daily_returns)) if len(daily_returns) > 1 else 0
                    metrics["sharpe_ratio"] = round((avg_ret / std_ret) * sqrt(252), 2) if std_ret > 0 else 0
                    metrics["worst_day_pct"] = round(min(daily_returns) * 100, 2)
                    metrics["best_day_pct"] = round(max(daily_returns) * 100, 2)
                    if ADVANCED_METRICS_AVAILABLE:
                        try:
                            metrics["sortino_ratio"] = calculate_sortino_ratio(daily_returns)
                            metrics["omega_ratio"] = calculate_omega_ratio(daily_returns)
                        except Exception:
                            pass
                    if max_dd > 0 and metrics.get("total_return_pct", 0) != 0:
                        annual_return = metrics["total_return_pct"] / max(len(daily_returns) / 252, 0.1)
                        if ADVANCED_METRICS_AVAILABLE:
                            try: metrics["calmar_ratio"] = calculate_calmar_ratio(annual_return, max_dd)
                            except Exception: pass
                metrics["equity_curve"] = [
                    {"date": s["date"], "value": s.get("portfolio_value", 0), "spy_return": s.get("spy_return_pct", 0), "portfolio_return": s.get("portfolio_return_pct", 0)}
                    for s in self.equity_snapshots if "portfolio_value" in s
                ]
        metrics["signals_found"] = len([s for s in self.signal_history if s.get("action_taken") in ["executed", "rejected"]])
        metrics["signals_executed"] = len([s for s in self.signal_history if s.get("action_taken") == "executed"])
        metrics["signals_rejected"] = len([s for s in self.signal_history if s.get("action_taken") == "rejected"])
        if metrics["signals_found"] > 0:
            metrics["rejection_rate"] = round(metrics["signals_rejected"] / metrics["signals_found"] * 100, 1)
        metrics["withdrawal_pot"] = self.buckets["withdrawal"]["available"]
        metrics["total_profits_extracted"] = self.buckets["withdrawal"]["profits_extracted"]
        metrics["total_dividends_earned"] = self.buckets["dividend"].get("total_dividends_earned", 0)
        self.performance_metrics = metrics
        self._save_performance_metrics()
        return metrics

    # ==========================================
    # CSV EXPORT
    # ==========================================

    def export_to_csv(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        watermark = "\nSource: QuantPro Terminal - Unauthorized reproduction prohibited"
        trades_file = self.exports_dir / f"trades_{timestamp}.csv"
        if self.trade_log:
            with open(trades_file, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["timestamp", "symbol", "side", "qty", "price", "filled_price", "filled_qty", "slippage_cost", "sec_fee", "order_id", "status", "reason", "confidence", "stop_loss", "take_profit", "estimated_cost", "sector", "bucket"])
                writer.writeheader()
                for t in self.trade_log:
                    row = {k: t.get(k, "") for k in writer.fieldnames}
                    if row.get("bucket") == "long_term": row["bucket"] = "dividend"
                    writer.writerow(row)
                f.write(watermark)
        equity_file = self.exports_dir / f"equity_{timestamp}.csv"
        if self.equity_snapshots:
            with open(equity_file, "w", newline="") as f:
                keys = set()
                for s in self.equity_snapshots: keys.update(s.keys())
                writer = csv.DictWriter(f, fieldnames=sorted(keys))
                writer.writeheader()
                for s in self.equity_snapshots: writer.writerow(s)
                f.write(watermark)
        signals_file = self.exports_dir / f"signals_{timestamp}.csv"
        if self.signal_history:
            with open(signals_file, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["timestamp", "symbol", "signal_type", "confidence", "rsi", "rvol", "price", "reason", "action_taken", "rejection_reason", "tier", "sector", "bucket"])
                writer.writeheader()
                for s in self.signal_history:
                    row = {k: s.get(k, "") for k in writer.fieldnames}
                    if row.get("bucket") == "long_term": row["bucket"] = "dividend"
                    writer.writerow(row)
                f.write(watermark)
        perf_file = self.exports_dir / f"performance_{timestamp}.csv"
        perf = self.calculate_performance()
        summary = {
            "Total Trades": perf["total_trades"], "Win Rate (%)": perf["win_rate"],
            "Avg Win (%)": perf["avg_win_pct"], "Avg Loss (%)": perf["avg_loss_pct"],
            "Total Return (%)": perf["total_return_pct"], "SPY Return (%)": perf["spy_return_pct"],
            "Outperformance (%)": perf["outperformance_pct"], "Max Drawdown (%)": perf["max_drawdown_pct"],
            "Sharpe Ratio": perf["sharpe_ratio"], "Sortino Ratio": perf.get("sortino_ratio", 0),
            "Calmar Ratio": perf.get("calmar_ratio", 0), "Omega Ratio": perf.get("omega_ratio", 0),
            "Profit Factor": perf["profit_factor"],
            "Withdrawal Pot ($)": perf["withdrawal_pot"], "Total Extracted ($)": perf["total_profits_extracted"],
            "Total Dividends ($)": perf["total_dividends_earned"],
        }
        with open(perf_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["Metric", "Value"])
            writer.writeheader()
            for k, v in summary.items(): writer.writerow({"Metric": k, "Value": v})
            f.write(watermark)
        buckets_file = self.exports_dir / f"buckets_{timestamp}.csv"
        ov = self.get_bucket_overview()
        bucket_data = {
            "Dividend Value": ov["dividend"]["value"], "Dividend Positions": ov["dividend"]["positions"],
            "Growth Value": ov["growth"]["value"], "Growth Positions": ov["growth"]["positions"],
            "Penny Value": ov["penny"]["value"], "Penny Positions": ov["penny"]["positions"],
            "Withdrawal Available": ov["withdrawal"]["available"],
            "Total Profit": ov["total_profit"], "Original Capital": ov["original_capital"],
        }
        with open(buckets_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["Metric", "Value"])
            writer.writeheader()
            for k, v in bucket_data.items(): writer.writerow({"Metric": k, "Value": v})
            f.write(watermark)
        return str(self.exports_dir)

    # ==========================================
    # ADVANCED SIGNALS INTEGRATION
    # ==========================================

    def scan_advanced(self, symbol: str, df=None) -> Dict:
        if not ADVANCED_SIGNALS_AVAILABLE:
            return {"signal": "HOLD", "confidence": 0, "reason": "Advanced signals not available", "details": []}
        try:
            if df is None:
                df, source = self._fetch_stock_data(symbol)
            if df is None or df.empty or len(df) < 50:
                return {"signal": "HOLD", "confidence": 0, "reason": "Insufficient data", "details": []}
            params = {
                "rsi_oversold": self.settings.get("rsi_oversold", 35),
                "rsi_overbought": self.settings.get("rsi_overbought", 65),
                "min_rvol": self.settings.get("min_rvol", 1.0),
                "signal_weights": self.settings.get("signal_weights", {}),
            }
            signals = generate_all_signals(df, symbol, params)
            if not signals:
                return {"signal": "HOLD", "confidence": 0, "reason": "No signals generated", "details": []}
            combined = calculate_combined_score(signals, params)
            combined["symbol"] = symbol
            combined["price"] = float(df['close'].iloc[-1])
            combined["bucket"] = self.assign_bucket(symbol)
            combined["signals"] = signals
            return combined
        except Exception as e:
            self._log_error(f"Advanced scan error for {symbol}: {str(e)[:60]}")
            return {"signal": "HOLD", "confidence": 0, "reason": f"Error: {str(e)[:50]}", "details": []}

    def check_vix(self) -> Dict:
        if not ADVANCED_SIGNALS_AVAILABLE:
            return {"safe_to_trade": True, "vix": 0, "level": "Unknown", "reason": "Advanced signals not available"}
        threshold = self.settings.get("vix_max_threshold", 28.0)
        result = vix_filter(threshold)
        if AUDIT_AVAILABLE:
            try: log_audit("system", "vix_check", "risk", details=result)
            except Exception: pass
        return result

    # ==========================================
    # BACKTESTING
    # ==========================================

    def run_backtest(self, symbols: List[str] = None, start_date: str = "2023-01-01",
                     end_date: str = None, strategy: str = "combined") -> Dict:
        if not BACKTEST_AVAILABLE:
            return {"status": "error", "message": "Backtest module not available. Install core/backtest.py"}
        if symbols is None:
            symbols = self.settings.get("watchlist", US_QUICK_TURNOVER)[:20]
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        engine = BacktestEngine(
            initial_capital=self.settings.get("original_capital", 100000),
            dividend_pct=self.settings.get("dividend_pct", 0.35),
            growth_pct=self.settings.get("growth_pct", 0.35),
            penny_pct=self.settings.get("penny_pct", 0.30),
            min_dividend_yield=self.settings.get("min_dividend_yield", 0.03),
            penny_price_threshold=self.settings.get("penny_price_threshold", 5.0),
            stop_loss_pct=self.settings.get("stop_loss_pct", 0.05),
            take_profit_pct=self.settings.get("take_profit_pct", 0.10),
            max_positions=self.settings.get("max_positions", 10),
            max_position_pct=self.settings.get("max_position_pct", 0.08),
        )
        result = engine.run_backtest(symbols=symbols, start_date=start_date, end_date=end_date, strategy=strategy)
        if AUDIT_AVAILABLE:
            try: log_audit("system", "backtest_run", "backtest", details={"symbols": len(symbols), "start": start_date, "end": end_date, "strategy": strategy, "result": result.get("status", "unknown")})
            except Exception: pass
        return result

    # ==========================================
    # DIVIDEND CALENDAR
    # ==========================================

    def get_upcoming_dividends(self, days_ahead: int = 30) -> List[Dict]:
        if not DIVIDEND_CALENDAR_AVAILABLE:
            return []
        symbols = list(set(self.settings.get("watchlist", []) + DIVIDEND_STOCKS[:20]))
        try:
            upcoming = get_upcoming_ex_dividends(symbols, days_ahead)
            if AUDIT_AVAILABLE:
                try: log_audit("system", "dividend_calendar", "dividends", details={"symbols_checked": len(symbols), "found": len(upcoming)})
                except Exception: pass
            return upcoming
        except Exception as e:
            self._log_error(f"Dividend calendar error: {str(e)[:60]}")
            return []

    def get_dividend_stock_comparison(self) -> List[Dict]:
        if not DIVIDEND_CALENDAR_AVAILABLE:
            return []
        symbols = list(set(self.settings.get("watchlist", [])[:30] + DIVIDEND_STOCKS[:30]))
        try:
            return get_dividend_comparison(symbols)
        except Exception as e:
            self._log_error(f"Dividend comparison error: {str(e)[:60]}")
            return []

    def calculate_drip_for_position(self, symbol: str, shares: int = None) -> Dict:
        if not DIVIDEND_CALENDAR_AVAILABLE:
            return {"error": "Dividend module not available"}
        positions = self.get_positions()
        current_price = 0; qty = shares
        for p in positions:
            if p["symbol"] == symbol:
                current_price = float(p.get("current_price", 0))
                if qty is None: qty = int(float(p.get("qty", 0)))
                break
        if current_price == 0:
            if YF_AVAILABLE:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="1d")
                    if not hist.empty: current_price = float(hist['Close'].iloc[-1])
                except Exception: pass
        if qty is None or qty <= 0: qty = 1
        div_yield = get_div_yield_external(symbol)
        if div_yield is None: div_yield = 0
        return calculate_drip(symbol, qty, current_price, div_yield, years=10)

    # ==========================================
    # DIAMOND STANDARD REPORT
    # ==========================================

    def generate_diamond_report(self) -> Dict:
        if ADVANCED_METRICS_AVAILABLE:
            try:
                return generate_full_report(self.trade_log, self.equity_snapshots)
            except Exception as e:
                self._log_error(f"Diamond report error: {str(e)[:60]}")
        return self.calculate_performance()

    # ==========================================
    # TRADE JOURNAL
    # ==========================================

    def save_trade_note(self, username: str, trade_id: str = "", symbol: str = "",
                        action: str = "", entry_reason: str = "",
                        emotion: str = "", lesson_learned: str = "",
                        tags: str = "") -> bool:
        if not AUDIT_AVAILABLE: return False
        try:
            bucket = self.assign_bucket(symbol) if symbol else ""
            entry = save_journal_entry(username=username, trade_id=trade_id, symbol=symbol, action=action,
                                       entry_reason=entry_reason, emotion=emotion, lesson_learned=lesson_learned,
                                       bucket=bucket, tags=tags)
            return entry is not None
        except Exception as e:
            self._log_error(f"Journal save error: {str(e)[:60]}")
            return False

    def get_trade_notes(self, username: str, symbol: str = None) -> List[Dict]:
        if not AUDIT_AVAILABLE: return []
        try: return get_journal_entries(username, symbol)
        except Exception as e:
            self._log_error(f"Journal query error: {str(e)[:60]}")
            return []

    # ==========================================
    # ENCRYPTED API KEY HANDLING
    # ==========================================

    def connect_encrypted(self, api_key_encrypted: str, secret_key_encrypted: str,
                          base_url: str = 'https://paper-api.alpaca.markets') -> bool:
        try:
            if ENCRYPTION_AVAILABLE and is_encrypted(api_key_encrypted):
                api_key = decrypt_value(api_key_encrypted)
                secret_key = decrypt_value(secret_key_encrypted)
            elif is_key_encrypted(api_key_encrypted):
                api_key = decrypt_value(api_key_encrypted)
                secret_key = decrypt_value(secret_key_encrypted)
            else:
                self._log_error("WARNING: API keys appear to be stored in plaintext!")
                api_key = api_key_encrypted
                secret_key = secret_key_encrypted
            alpaca_api = tradeapi.REST(api_key, secret_key, base_url=base_url, api_version='v2')
            return self.connect(alpaca_api)
        except Exception as e:
            self.connected = False
            self._log_error(f"Encrypted connection error: {str(e)[:60]}")
            return False

    # ==========================================
    # CONNECTION
    # ==========================================

    def connect(self, alpaca_api=None):
        if alpaca_api:
            self._alpaca_api_ref = alpaca_api
            self.api = alpaca_api
        else:
            try:
                from utils import alpaca_api
                self._alpaca_api_ref = alpaca_api
                self.api = alpaca_api
            except Exception:
                self.api = None
                self._alpaca_api_ref = None
        if self.api is None:
            self.connected = False
            self.status_message = "Alpaca API not available."
            return False
        return self._test_connection()

    def _test_connection(self):
        if self.api is None:
            self.connected = False
            return False
        try:
            account = self.api.get_account()
            self.connected = True
            today = datetime.now().date()
            if self.daily_reset_date != today:
                self.daily_pnl = 0.0
                self.daily_start_equity = float(account.equity)
                self.daily_reset_date = today
            self.consecutive_failures = 0
            self.status_message = f"Connected. Paper balance: ${float(account.buying_power):,.2f}"
            return True
        except Exception as e:
            self.connected = False
            self._log_error(f"Connection test failed: {str(e)[:80]}")
            return False

    def _reconnect(self):
        if self._alpaca_api_ref is None:
            self._log_error("Cannot reconnect: no Alpaca API reference")
            return False
        self.reconnect_count += 1
        self.last_reconnect_time = datetime.now().isoformat()
        for attempt in range(1, self.MAX_RECONNECT_ATTEMPTS + 1):
            delay = min(self.RECONNECT_BASE_DELAY * (2 ** (attempt - 1)), self.MAX_RECONNECT_DELAY)
            self.status_message = f"Reconnecting... attempt {attempt}/{self.MAX_RECONNECT_ATTEMPTS}"
            self._log_error(f"Reconnect attempt {attempt}/{self.MAX_RECONNECT_ATTEMPTS}, waiting {delay}s")
            if self._stop_event.wait(delay): return False
            try:
                from utils import alpaca_api
                self._alpaca_api_ref = alpaca_api
                self.api = alpaca_api
            except Exception as e:
                self._log_error(f"Failed to import alpaca_api: {str(e)[:60]}")
                continue
            if self._test_connection():
                self.consecutive_failures = 0
                return True
        self.status_message = f"Failed to reconnect after {self.MAX_RECONNECT_ATTEMPTS} attempts."
        return False

    def _check_and_reset_daily(self):
        today = datetime.now().date()
        if self.daily_reset_date is None or self.daily_reset_date != today:
            old_date = self.daily_reset_date
            self.daily_reset_date = today
            self.daily_pnl = 0.0
            if old_date is not None:
                self._log_error(f"Daily reset: {old_date} → {today}.")
            try:
                if self.connected and self.api:
                    account = self.api.get_account()
                    self.daily_start_equity = float(account.equity)
            except Exception as e:
                self._log_error(f"Could not fetch equity for daily reset: {str(e)[:60]}")

    # ==========================================
    # MARKET HOURS
    # ==========================================

    def is_market_open(self) -> Dict:
        try:
            from zoneinfo import ZoneInfo
            eastern = ZoneInfo("US/Eastern")
            now_et = datetime.now(eastern)
            market_open = dt_time(9, 30)
            market_close = dt_time(16, 0)
            is_weekday = now_et.weekday() < 5
            is_trading_hours = market_open <= now_et.time() <= market_close
            is_open = is_weekday and is_trading_hours
            if is_weekday and now_et.time() < market_open:
                next_open = datetime.combine(now_et.date(), market_open)
            elif is_weekday and now_et.time() >= market_close:
                next_date = now_et.date() + timedelta(days=1)
                while next_date.weekday() >= 5: next_date += timedelta(days=1)
                next_open = datetime.combine(next_date, market_open)
            else:
                next_date = now_et.date() + timedelta(days=1)
                while next_date.weekday() >= 5: next_date += timedelta(days=1)
                next_open = datetime.combine(next_date, market_open)
            return {"is_open": is_open, "current_time_et": now_et.strftime("%I:%M %p"), "current_time_uk": now_et.strftime("%H:%M") + " UK",
                    "market_open_time": "9:30 AM ET / 2:30 PM UK", "market_close_time": "4:00 PM ET / 9:00 PM UK",
                    "is_weekday": is_weekday, "day_name": now_et.strftime("%A"), "next_open": next_open.strftime("%A %I:%M %p ET")}
        except Exception as e:
            return {"is_open": True, "error": str(e), "current_time_et": "Unknown", "market_open_time": "9:30 AM ET / 2:30 PM UK", "market_close_time": "4:00 PM ET / 9:00 PM UK", "next_open": "Unknown"}

    # ==========================================
    # ACCOUNT & POSITIONS
    # ==========================================

    def get_account_info(self) -> Dict:
        if not self.api or not self.connected:
            return {"error": "Not connected"}
        try:
            account = self.api.get_account()
            return {"cash": float(account.cash), "buying_power": float(account.buying_power),
                    "portfolio_value": float(account.portfolio_value), "equity": float(account.equity),
                    "status": account.status, "pattern_day_trader": account.pattern_day_trader,
                    "trade_count_today": int(account.daytrade_count)}
        except Exception as e:
            self.connected = False
            self._log_error(f"Account info error: {str(e)[:60]}")
            return {"error": str(e)}

    def get_positions(self) -> List[Dict]:
        if not self.api or not self.connected: return []
        try:
            positions = self.api.list_positions()
            result = []
            for pos in positions:
                result.append({
                    "symbol": pos.symbol, "qty": float(pos.qty), "side": pos.side,
                    "avg_entry_price": float(pos.avg_entry_price), "current_price": float(pos.current_price),
                    "market_value": float(pos.market_value), "unrealized_pl": float(pos.unrealized_pl),
                    "unrealized_plpc": float(pos.unrealized_plpc),
                    "change_today": float(pos.change_today) if hasattr(pos, "change_today") else 0,
                    "sector": SECTOR_MAP.get(pos.symbol, "Unknown"),
                    "bucket": self.assign_bucket(pos.symbol),
                })
            return result
        except Exception as e:
            self.connected = False
            self._log_error(f"Get positions error: {str(e)[:60]}")
            return []

    def get_open_orders(self) -> List[Dict]:
        if not self.api or not self.connected: return []
        try:
            orders = self.api.list_orders(status="open")
            return [{"id": str(o.id), "symbol": o.symbol, "qty": float(o.qty), "side": o.side, "type": o.type, "status": o.status} for o in orders]
        except Exception: return []

    # ==========================================
    # DATA FETCHING
    # ==========================================

    def _fetch_stock_data(self, symbol: str, period: str = "3mo"):
        df = None
        if self.api and self.connected and ALPACA_AVAILABLE:
            if '.L' not in symbol and '-' not in symbol:
                try:
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=90)
                    bars = self.api.get_bars(symbol, tradeapi.TimeFrame.Day, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), feed='iex')
                    df = bars.df
                    if df is not None and not df.empty and len(df) >= 20:
                        df.columns = [c.lower() for c in df.columns]
                        return df, "alpaca_live"
                except Exception as e:
                    self._log_error(f"Alpaca data failed for {symbol}: {str(e)[:60]}")
                    df = None
        if YF_AVAILABLE:
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=period)
                if df is not None and not df.empty and len(df) >= 20:
                    df.columns = [c.lower() for c in df.columns]
                    return df, "yahoo_delay"
            except Exception as e:
                self._log_error(f"Yahoo data failed for {symbol}: {str(e)[:60]}")
                df = None
        return None, "none"

    # ==========================================
    # BATCH DATA FETCHING (NEW - Change 1)
    # ==========================================

    def _batch_fetch_data(self, symbols: List[str]) -> Dict[str, 'pd.DataFrame']:
        """Batch fetch stock data using Alpaca or yf.download for speed."""
        results = {}
        failed_symbols = []

        # Strategy 1: Try Alpaca batch bars first (if connected)
        if self.api and self.connected and ALPACA_AVAILABLE:
            try:
                chunk_size = 200
                for c in range(0, len(symbols), chunk_size):
                    chunk = symbols[c:c + chunk_size]
                    try:
                        end_date = datetime.now()
                        start_date = end_date - timedelta(days=90)
                        bars = self.api.get_bars(
                            chunk,
                            tradeapi.TimeFrame.Day,
                            start=start_date.strftime('%Y-%m-%d'),
                            end=end_date.strftime('%Y-%m-%d'),
                            feed='iex'
                        )
                        symbol_bars = {}
                        for bar in bars:
                            sym = bar.S
                            if sym not in symbol_bars:
                                symbol_bars[sym] = []
                            symbol_bars[sym].append({
                                'open': bar.o, 'high': bar.h, 'low': bar.l,
                                'close': bar.c, 'volume': bar.v,
                                'timestamp': bar.t
                            })
                        for sym, bar_list in symbol_bars.items():
                            try:
                                sym_df = pd.DataFrame(bar_list)
                                sym_df['timestamp'] = pd.to_datetime(sym_df['timestamp'])
                                sym_df = sym_df.set_index('timestamp')
                                sym_df = sym_df.sort_index()
                                if len(sym_df) >= 20:
                                    results[sym] = sym_df
                            except Exception:
                                pass
                    except Exception as e:
                        self._log_error(f"Alpaca batch fetch error: {str(e)[:80]}")
                        # Don't add to failed_symbols yet, yf.download will handle them
            except Exception as e:
                self._log_error(f"Alpaca batch error: {str(e)[:80]}")

        # Strategy 2: Use yf.download for remaining symbols (in chunks of 50)
        remaining = [s for s in symbols if s not in results]
        if remaining and YF_AVAILABLE:
            chunk_size = 50
            for c in range(0, len(remaining), chunk_size):
                chunk = remaining[c:c + chunk_size]
                ticker_string = " ".join(chunk)
                try:
                    batch_df = yf.download(
                        ticker_string,
                        period="3mo",
                        group_by="ticker",
                        threads=True,
                        progress=False
                    )

                    for symbol in chunk:
                        try:
                            if len(chunk) == 1:
                                sym_df = batch_df.copy()
                            else:
                                try:
                                    sym_df = batch_df[symbol].copy()
                                except (KeyError, TypeError):
                                    # Try alternative access for different yfinance versions
                                    try:
                                        sym_df = batch_df.xs(symbol, axis=1, level=0).copy()
                                    except Exception:
                                        failed_symbols.append(symbol)
                                        continue

                            # Handle MultiIndex columns
                            if isinstance(sym_df.columns, pd.MultiIndex):
                                sym_df.columns = [str(col[1]) if col[1] else str(col[0]) for col in sym_df.columns]

                            # Normalize columns
                            sym_df.columns = [str(col).lower().replace(' ', '_') for col in sym_df.columns]

                            # Drop adj_close if present
                            if 'adj_close' in sym_df.columns:
                                sym_df = sym_df.drop(columns=['adj_close'])

                            # Drop rows with NaN close
                            if 'close' in sym_df.columns:
                                sym_df = sym_df.dropna(subset=['close'])

                            if not sym_df.empty and len(sym_df) >= 20:
                                results[symbol] = sym_df
                            else:
                                failed_symbols.append(symbol)
                        except Exception:
                            failed_symbols.append(symbol)
                except Exception as e:
                    self._log_error(f"Batch download error for chunk: {str(e)[:80]}")
                    failed_symbols.extend(chunk)

        # Strategy 3: Fallback to one-by-one for failed symbols
        if failed_symbols and YF_AVAILABLE:
            self._log_error(f"Fallback: Fetching {len(failed_symbols)} symbols individually")
            for symbol in failed_symbols:
                if symbol not in results:
                    try:
                        df, source = self._fetch_stock_data(symbol)
                        if df is not None and not df.empty and len(df) >= 20:
                            results[symbol] = df
                    except Exception:
                        pass

        return results

    # ==========================================
    # SIGNAL DETECTION (Enhanced with Batch Scanning - Change 1)
    # ==========================================

    def scan_all(self) -> List[Dict]:
        if not TA_AVAILABLE or not PANDAS_AVAILABLE:
            self._log_error("Missing libraries: ta or pandas")
            return []

        all_stocks = []
        signals = []
        watchlist = self.settings["watchlist"]
        global_oversold = self.settings["rsi_oversold"]
        global_overbought = self.settings["rsi_overbought"]
        global_min_rvol = self.settings["min_rvol"]
        global_min_confidence = self.settings.get("min_confidence", 0.20)
        mode = self.settings["mode"]
        use_advanced = self.settings.get("use_advanced_signals", True)

        self.scan_summary = {
            "last_scan": datetime.now().isoformat(), "stocks_scanned": len(watchlist),
            "stocks_success": 0, "stocks_no_data": 0, "errors_count": 0,
            "error_details": [], "data_source": "none", "mode": mode,
            "oversold_threshold": global_oversold, "overbought_threshold": global_overbought,
            "min_rvol_threshold": global_min_rvol, "min_confidence": global_min_confidence,
            "advanced_signals_used": use_advanced,
        }
        data_source_used = "none"

        # VIX filter
        vix_ok = True
        if self.settings.get("use_vix_filter", True) and ADVANCED_SIGNALS_AVAILABLE:
            vix_result = self.check_vix()
            vix_ok = vix_result.get("safe_to_trade", True)
            self.scan_summary["vix"] = vix_result

        # ===== CHANGE 1: Batch fetch data instead of one-by-one =====
        batch_data = self._batch_fetch_data(watchlist)

        # Process each symbol
        for i, symbol in enumerate(watchlist):
            try:
                # Get data from batch or fallback
                if symbol in batch_data:
                    df = batch_data[symbol]
                    source = "⚡ batch"
                else:
                    df, source = self._fetch_stock_data(symbol)

                if df is None or df.empty or len(df) < 20:
                    self.scan_summary["stocks_no_data"] += 1
                    self.scan_summary["error_details"].append(f"{symbol}: no data")
                    continue

                if source.startswith("⚡"):
                    data_source_used = source

                rsi_series = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
                rsi = rsi_series.iloc[-1]
                if rsi is None or (PANDAS_AVAILABLE and pd.isna(rsi)):
                    self.scan_summary["error_details"].append(f"{symbol}: RSI is NaN")
                    continue

                avg_vol = df["volume"].rolling(20).mean().iloc[-1]
                curr_vol = df["volume"].iloc[-1]
                rvol = curr_vol / avg_vol if avg_vol > 0 else 0
                price = df['close'].iloc[-1]

                # Get bucket-specific thresholds
                bucket = self.assign_bucket(symbol)
                bucket_settings = self.get_bucket_settings(bucket)
                oversold = bucket_settings.get("rsi_oversold", global_oversold)
                overbought = bucket_settings.get("rsi_overbought", global_overbought)
                min_rvol = bucket_settings.get("min_rvol", global_min_rvol)
                min_confidence = bucket_settings.get("min_confidence", global_min_confidence)

                # Cache price for bucket classification
                sym_key = symbol.upper()
                if sym_key in self._stock_info_cache:
                    self._stock_info_cache[sym_key]["price"] = price
                    self._stock_info_cache[sym_key]["timestamp"] = datetime.now()
                else:
                    self._stock_info_cache[sym_key] = {
                        "price": price, "div_yield": None,
                        "bucket": None, "timestamp": datetime.now()
                    }

                if rsi < oversold and rvol >= min_rvol: status = "BUY SIGNAL"
                elif rsi < oversold: status = "Almost Buy (low volume)"
                elif rsi < oversold + 10: status = "Approaching Buy"
                elif rsi > overbought and rvol >= min_rvol: status = "SELL SIGNAL"
                elif rsi > overbought: status = "Almost Sell (low volume)"
                elif rsi > overbought - 10: status = "Approaching Sell"
                else: status = "Neutral"

                signal = None
                confidence = 0.0
                reason = ""
                signal_details = []

                # ADVANCED signals (if enabled and enough data)
                if use_advanced and ADVANCED_SIGNALS_AVAILABLE and len(df) >= 50:
                    advanced_result = self.scan_advanced(symbol, df)
                    signal = advanced_result.get("signal", "HOLD")
                    confidence = advanced_result.get("confidence", 0)
                    reason = advanced_result.get("reason", "")
                    signal_details = advanced_result.get("details", [])
                    if signal == "HOLD" or signal == "":
                        signal = None; confidence = 0; reason = ""
                    # Block buys when VIX is high
                    if signal and not vix_ok:
                        signal = None; confidence = 0
                        reason = f"Blocked by VIX filter: {vix_result.get('reason', 'VIX too high')}"

                if signal is None:
                    # FALLBACK: Basic RSI/RVOL logic (bucket-specific thresholds)
                    if mode == "quick":
                        if rsi < oversold and rvol >= min_rvol:
                            signal = "BUY"; confidence = min(0.95, (oversold - rsi) / oversold + rvol / 3)
                            reason = f"RSI={rsi:.1f} (oversold) + RVOL={rvol:.1f}. Strong bounce. [{bucket}]"
                        elif rsi < (oversold + 5) and rvol >= (min_rvol * 1.3):
                            signal = "BUY"; confidence = min(0.80, 0.5 + (rvol / 5))
                            reason = f"RSI={rsi:.1f} (near oversold) + RVOL={rvol:.1f}. Volume-backed. [{bucket}]"
                        elif rsi < oversold and rvol >= 1.0:
                            signal = "BUY"; confidence = min(0.65, (oversold - rsi) / oversold + 0.2)
                            reason = f"RSI={rsi:.1f} (oversold) but RVOL={rvol:.1f}. Cautious. [{bucket}]"
                        elif rsi > overbought and rvol >= min_rvol:
                            signal = "SELL"; confidence = min(0.95, (rsi - overbought) / (100 - overbought) + rvol / 3)
                            reason = f"RSI={rsi:.1f} (overbought) + RVOL={rvol:.1f}. Strong sell. [{bucket}]"
                        elif rsi > (overbought - 5) and rvol >= (min_rvol * 1.3):
                            signal = "SELL"; confidence = min(0.80, 0.5 + (rvol / 5))
                            reason = f"RSI={rsi:.1f} (near overbought) + RVOL={rvol:.1f}. Volume-backed exit. [{bucket}]"
                        elif rsi > overbought and rvol >= 1.0:
                            signal = "SELL"; confidence = min(0.65, (rsi - overbought) / (100 - overbought) + 0.2)
                            reason = f"RSI={rsi:.1f} (overbought) but RVOL={rvol:.1f}. Cautious exit. [{bucket}]"
                    elif mode == "longterm":
                        if rsi < 45 and rvol < 1.5:
                            signal = "BUY"; confidence = 0.6; reason = f"RSI={rsi:.1f} + Low volatility. Long-term entry."
                        elif rsi < 40 and rvol >= 1.0:
                            signal = "BUY"; confidence = 0.7; reason = f"RSI={rsi:.1f} + RVOL={rvol:.1f}. Solid entry."
                        elif rsi > 75:
                            signal = "SELL"; confidence = 0.7; reason = f"RSI={rsi:.1f}. Take profits."
                        elif rsi > 80 and rvol >= 1.5:
                            signal = "SELL"; confidence = 0.85; reason = f"RSI={rsi:.1f} + RVOL={rvol:.1f}. Strong exit."

                    if signal and confidence < min_confidence:
                        reason += f" [Below min confidence {min_confidence:.0%}]"
                        signal = None; confidence = 0

                    # VIX filter (block buys when VIX is high)
                    if signal == "BUY" and not vix_ok:
                        signal = None; confidence = 0
                        reason = f"VIX filter active: {vix_result.get('reason', 'VIX too high')}"

                stock_entry = {
                    "symbol": symbol, "price": round(price, 2), "rsi": round(rsi, 1),
                    "rvol": round(rvol, 2), "status": status,
                    "signal": signal if signal else "", "confidence": round(confidence, 2) if signal else 0,
                    "reason": reason, "data_source": source,
                    "sector": SECTOR_MAP.get(symbol, "Unknown"),
                    "bucket": bucket,
                }
                all_stocks.append(stock_entry)

                if signal:
                    signals.append({
                        "symbol": symbol, "signal": signal,
                        "confidence": round(confidence, 2), "reason": reason,
                        "price": round(price, 2), "rsi": round(rsi, 1), "rvol": round(rvol, 2),
                        "timestamp": datetime.now().isoformat(), "mode": mode,
                        "sector": SECTOR_MAP.get(symbol, "Unknown"),
                        "bucket": bucket,
                        "details": signal_details if isinstance(signal_details, list) else [],
                    })

                self.scan_summary["stocks_success"] += 1
            except Exception as e:
                self.scan_summary["errors_count"] += 1
                self.scan_summary["error_details"].append(f"{symbol}: {str(e)[:80]}")
                self._log_error(f"Scan error: {symbol}: {str(e)[:60]}")
                continue

        def sort_key(x):
            s = x.get("status", "")
            if "SIGNAL" in s: return 0
            elif "Almost" in s: return 1
            elif "Approaching" in s: return 2
            else: return 3
        all_stocks.sort(key=sort_key)
        signals.sort(key=lambda s: s["confidence"], reverse=True)

        self.near_signals = all_stocks
        self.signals_found = signals
        self.last_scan_time = datetime.now().isoformat()
        self.scan_summary["data_source"] = data_source_used if data_source_used != "none" else "mixed"
        self.status_message = f"Scan done: {len(all_stocks)} stocks, {len(signals)} signals (batch mode)"
        return all_stocks

    def scan_signals(self) -> List[Dict]:
        self.scan_all()
        return self.signals_found
    
    # ==========================================
    # RISK MANAGEMENT (Enhanced with Bucket-Specific Settings)
    # ==========================================

    def evaluate_risk(self, signal: Dict) -> Dict:
        settings = self.settings
        min_confidence = settings.get("min_confidence", 0.20)
        max_same_sector = settings.get("max_same_sector", 3)
        account = self.get_account_info()

        if "error" in account:
            return {"approved": False, "reason": f"Account error: {account['error']}"}

        if self.daily_reset_date != datetime.now().date():
            self.daily_pnl = 0.0
            self.daily_start_equity = float(account.get("equity", 0))
            self.daily_reset_date = datetime.now().date()

        equity = float(account.get("equity", 0))

        # VIX filter check
        if settings.get("use_vix_filter", True) and ADVANCED_SIGNALS_AVAILABLE:
            vix_result = self.check_vix()
            if not vix_result.get("safe_to_trade", True):
                reason = vix_result.get("reason", "VIX filter active")
                self._log_error(f"Trade blocked by VIX filter: {reason}")
                self.record_signal(signal, "rejected", f"VIX filter: {reason}")
                return {"approved": False, "reason": reason}

        # Daily loss limit
        if equity > 0 and self.daily_pnl < 0 and self.daily_start_equity > 0:
            loss_pct = abs(self.daily_pnl) / self.daily_start_equity
            if loss_pct >= settings["daily_loss_limit_pct"]:
                reason = f"Daily loss limit reached ({loss_pct:.1%} >= {settings['daily_loss_limit_pct']:.1%})"
                self._log_error(f"Trade rejected: {reason}")
                self.record_signal(signal, "rejected", reason)
                return {"approved": False, "reason": reason}

        positions = self.get_positions()

        if signal["signal"] == "BUY":
            current_symbols = [p["symbol"] for p in positions]
            if len(positions) >= settings["max_positions"]:
                reason = f"Max positions reached ({len(positions)}/{settings['max_positions']})"
                self._log_error(f"Trade rejected: {reason}")
                self.record_signal(signal, "rejected", reason)
                return {"approved": False, "reason": reason}

            if signal["symbol"] in current_symbols:
                reason = f"Already holding {signal['symbol']}"
                self._log_error(f"Trade rejected: {reason}")
                self.record_signal(signal, "rejected", reason)
                return {"approved": False, "reason": reason}

            signal_sector = SECTOR_MAP.get(signal["symbol"], "Unknown")
            sector_count = sum(1 for p in positions if SECTOR_MAP.get(p["symbol"], "Unknown") == signal_sector)
            if sector_count >= max_same_sector:
                reason = f"Sector limit: {sector_count}/{max_same_sector} in {signal_sector}"
                self._log_error(f"Trade rejected: {reason}")
                self.record_signal(signal, "rejected", reason)
                return {"approved": False, "reason": reason}

            # Check bucket allocation — skip if 0%
            bucket = self.classify_stock(signal["symbol"])
            bucket_pct_key = f"{bucket}_pct"
            bucket_pct = self.settings.get(bucket_pct_key, 0.30)
            if bucket_pct <= 0:
                reason = f"{bucket.title()} bucket allocation is 0% — skipping"
                self._log_error(f"Trade rejected: {reason}")
                self.record_signal(signal, "rejected", reason)
                return {"approved": False, "reason": reason}

            # Get bucket-specific confidence threshold
            bucket = self.classify_stock(signal["symbol"]) if signal["signal"] == "BUY" else self.assign_bucket(signal["symbol"])
            bucket_settings = self.get_bucket_settings(bucket)
            bucket_min_confidence = bucket_settings.get("min_confidence", min_confidence)

            if signal.get("confidence", 0) < bucket_min_confidence:
                reason = f"Confidence too low ({signal.get('confidence', 0):.2f} < {bucket_min_confidence:.2f}) [{bucket}]"
                self._log_error(f"Trade rejected: {reason}")
                self.record_signal(signal, "rejected", reason)
                return {"approved": False, "reason": reason}

            if signal["signal"] == "BUY":
                bucket = self.classify_stock(signal["symbol"])
                bucket_settings = self.get_bucket_settings(bucket)
                bucket_max_pct = bucket_settings["max_position_pct"]

                available_cash = self.get_available_trading_cash()

                # ATR-based position sizing
                if settings.get("use_atr_position_sizing", True) and ADVANCED_SIGNALS_AVAILABLE:
                    try:
                        df, source = self._fetch_stock_data(signal["symbol"])
                        if df is not None and len(df) >= 15:
                            atr = calculate_atr(df)
                            if atr > 0:
                                risk_amount = equity * settings.get("atr_risk_pct", 0.01)
                                risk_per_share = 2 * atr
                                qty = max(1, int(risk_amount / risk_per_share))
                                position_value = qty * signal["price"]
                                max_position_value = equity * bucket_max_pct
                                if position_value > max_position_value:
                                    qty = max(1, int(max_position_value / signal["price"]))
                                    position_value = qty * signal["price"]
                                if position_value > available_cash * 0.95:
                                    qty = max(1, int((available_cash * 0.95) / signal["price"]))
                                    position_value = qty * signal["price"]
                            else:
                                max_position_value = equity * bucket_max_pct
                                position_value = min(max_position_value, available_cash * 0.95)
                                qty = max(1, int(position_value / signal["price"]))
                        else:
                            max_position_value = equity * bucket_max_pct
                            position_value = min(max_position_value, available_cash * 0.95)
                            qty = max(1, int(position_value / signal["price"]))
                    except Exception:
                        max_position_value = equity * bucket_max_pct
                        position_value = min(max_position_value, available_cash * 0.95)
                        qty = max(1, int(position_value / signal["price"]))
                else:
                    max_position_value = equity * bucket_max_pct
                    position_value = min(max_position_value, available_cash * 0.95)
                    qty = max(1, int(position_value / signal["price"]))

                if qty <= 0:
                    reason = "Insufficient trading cash (withdrawal pot protected)"
                    self._log_error(f"Trade rejected: {reason}")
                    self.record_signal(signal, "rejected", reason)
                    return {"approved": False, "reason": reason}

                # Bucket-specific stop loss and take profit
                bucket_sl = bucket_settings["stop_loss_pct"]
                bucket_tp = bucket_settings["take_profit_pct"]

                self.record_signal(signal, "executed", "")
                return {
                    "approved": True, "symbol": signal["symbol"], "side": "buy",
                    "qty": qty, "price": signal["price"],
                    "estimated_cost": round(qty * signal["price"], 2),
                    "stop_loss": round(signal["price"] * (1 - bucket_sl), 2),
                    "take_profit": round(signal["price"] * (1 + bucket_tp), 2),
                    "reason": signal["reason"], "confidence": signal["confidence"],
                    "bucket": bucket,
                }

        elif signal["signal"] == "SELL":
            bucket = self.assign_bucket(signal["symbol"])
            for pos in positions:
                if pos["symbol"] == signal["symbol"]:
                    self.record_signal(signal, "executed", "")
                    return {
                        "approved": True, "symbol": signal["symbol"], "side": "sell",
                        "qty": float(pos["qty"]), "price": signal["price"],
                        "reason": signal["reason"], "confidence": signal["confidence"],
                        "bucket": bucket,
                    }
            reason = f"No position in {signal['symbol']} to sell"
            self._log_error(f"Trade rejected: {reason}")
            self.record_signal(signal, "rejected", reason)
            return {"approved": False, "reason": reason}

        return {"approved": False, "reason": "Unknown signal type"}

    # ==========================================
    # DISCORD ALERTS
    # ==========================================

    def send_alert(self, message: str):
        webhook_url = self.settings.get("discord_webhook_url", "")
        if webhook_url:
            try:
                from core.alerts import send_discord_alert
                send_discord_alert(webhook_url, message)
            except Exception as e:
                self._log_error(f"Discord alert failed: {e}")

    # ==========================================
    # ORDER EXECUTION
    # ==========================================

    def place_order(self, approval: Dict, username: str = "system") -> Dict:
        if not self.api or not self.connected:
            return {"error": "Not connected to Alpaca"}
        try:
            order = self.api.submit_order(symbol=approval["symbol"], qty=approval["qty"],
                                           side=approval["side"], type="market", time_in_force="day")

            time.sleep(2)
            filled_price = approval["price"]
            filled_qty = approval["qty"]
            order_status = order.status
            try:
                updated_order = self.api.get_order(order.id)
                order_status = updated_order.status
                if hasattr(updated_order, 'filled_avg_price') and updated_order.filled_avg_price:
                    filled_price = float(updated_order.filled_avg_price)
                if hasattr(updated_order, 'filled_qty') and updated_order.filled_qty:
                    filled_qty = float(updated_order.filled_qty)
            except Exception: pass

            slippage = filled_price * (self.settings.get("slippage_pct", 0.05) / 100)
            sec_fee = filled_price * (self.settings.get("sec_fee_pct", 0.00002) / 100) if approval["side"] == "sell" else 0

            bucket = approval.get("bucket", self.assign_bucket(approval["symbol"]))
            if bucket == "long_term": bucket = "dividend"

            trade_record = {
                "timestamp": datetime.now().isoformat(), "symbol": approval["symbol"], "side": approval["side"],
                "qty": approval["qty"], "price": approval["price"],
                "filled_price": filled_price, "filled_qty": filled_qty,
                "slippage_cost": round(slippage * filled_qty, 4),
                "sec_fee": round(sec_fee * filled_qty, 4),
                "order_id": str(order.id), "status": order_status,
                "reason": approval.get("reason", ""), "confidence": approval.get("confidence", 0),
                "stop_loss": approval.get("stop_loss", ""), "take_profit": approval.get("take_profit", ""),
                "estimated_cost": approval.get("estimated_cost", 0),
                "sector": SECTOR_MAP.get(approval["symbol"], "Unknown"), "bucket": bucket,
            }
            self.trade_log.append(trade_record)
            self._save_trade_log()
            self.status_message = f"Order placed: {approval['side'].upper()} {approval['qty']} {approval['symbol']}"

            # Get bucket-specific settings for Discord message
            bucket_settings = self.get_bucket_settings(bucket)
            bucket_sl = bucket_settings.get("stop_loss_pct", self.settings.get("stop_loss_pct", 0.05))
            bucket_tp = bucket_settings.get("take_profit_pct", self.settings.get("take_profit_pct", 0.10))

            if AUDIT_AVAILABLE:
                try: log_trade_audit(username, {"symbol": approval["symbol"], "side": approval["side"], "qty": approval["qty"], "price": approval["price"], "filled_price": filled_price, "bucket": bucket, "confidence": approval.get("confidence", 0), "reason": approval.get("reason", ""), "order_id": str(order.id)})
                except Exception: pass

            # Discord alert (privacy mode)
            bucket_icon = self.get_bucket_icon(bucket)
            bucket_name = bucket.title()
            if self.settings.get("discord_privacy_mode", True):
                self.send_alert(f"🚨 **Trade Executed!**\n{bucket_icon} **{approval['side'].upper()}** **{approval['symbol']}** ({bucket_name})\nConfidence: {approval.get('confidence', 0):.0%} | Stop: {bucket_sl:.0%} | Target: {bucket_tp:.0%}")
            else:
                self.send_alert(f"🚨 **Trade Executed!**\n{bucket_icon} **{approval['side'].upper()}** {approval['qty']} shares of **{approval['symbol']}** at ${approval['price']:.2f}\nBucket: {bucket_name} | Stop: {bucket_sl:.0%} | Target: {bucket_tp:.0%}\nReason: {approval.get('reason', 'N/A')}\nConfidence: {approval.get('confidence', 0):.0%}")

            # Move profits after sell
            if approval["side"] == "sell":
                if bucket == "penny" and self.settings.get("penny_profits_to_growth", True): self.move_profits()
                elif bucket == "growth" and self.settings.get("growth_profits_to_dividend", True): self.move_profits()

            return trade_record
        except Exception as e:
            self._log_error(f"Order failed: {e}")
            if AUDIT_AVAILABLE:
                try: log_audit(username, "trade_failed", "trading", symbol=approval.get("symbol", ""), details={"error": str(e), "approval": approval})
                except Exception: pass
            return {"error": str(e)}

    def close_position(self, symbol: str, reason: str = "") -> Dict:
        if not self.api or not self.connected:
            return {"error": "Not connected"}
        try:
            positions = self.get_positions()
            current_price = 0.0
            for pos in positions:
                if pos["symbol"] == symbol:
                    current_price = float(pos["current_price"])
                    break
            order = self.api.close_position(symbol)
            bucket = self.assign_bucket(symbol)
            if bucket == "long_term": bucket = "dividend"
            trade_record = {
                "timestamp": datetime.now().isoformat(), "symbol": symbol, "side": "sell", "qty": 0, "price": current_price,
                "order_id": str(order.id), "status": order.status, "reason": reason,
                "sector": SECTOR_MAP.get(symbol, "Unknown"), "bucket": bucket,
            }
            self.trade_log.append(trade_record)
            self._save_trade_log()

            if bucket == "penny" and self.settings.get("penny_profits_to_growth", True): self.move_profits()
            elif bucket == "growth" and self.settings.get("growth_profits_to_dividend", True): self.move_profits()

            return trade_record
        except Exception as e:
            self._log_error(f"Close position failed for {symbol}: {e}")
            return {"error": str(e)}

    # ==========================================
    # STOP LOSS & TAKE PROFIT (Bucket-Specific)
    # ==========================================

    def check_stops(self) -> List[Dict]:
        if not self.api or not self.connected: return []
        try:
            positions = self.api.list_positions()
        except Exception:
            return []
        if not positions: return []
        closed = []
        for pos in positions:
            symbol = pos.symbol
            entry_price = float(pos.avg_entry_price)
            current_price = float(pos.current_price)
            pl_pct = float(pos.unrealized_plpc)
            bucket = self.assign_bucket(symbol)
            bucket_settings = self.get_bucket_settings(bucket)

            stop_loss_pct = bucket_settings["stop_loss_pct"]
            take_profit_pct = bucket_settings["take_profit_pct"]
            trailing_stop_pct = bucket_settings["trailing_stop_pct"]

            if pl_pct <= -(stop_loss_pct):
                result = self.close_position(symbol, f"Stop loss ({bucket}): {pl_pct:.2%}")
                if "error" not in result:
                    closed.append({"symbol": symbol, "action": "stop_loss", "pl_pct": round(pl_pct, 4),
                                   "entry_price": entry_price, "exit_price": current_price,
                                   "reason": f"Stop loss ({bucket}): down {pl_pct:.2%}", "bucket": bucket})
            elif pl_pct >= take_profit_pct:
                result = self.close_position(symbol, f"Take profit ({bucket}): {pl_pct:.2%}")
                if "error" not in result:
                    closed.append({"symbol": symbol, "action": "take_profit", "pl_pct": round(pl_pct, 4),
                                   "entry_price": entry_price, "exit_price": current_price,
                                   "reason": f"Take profit ({bucket}): up {pl_pct:.2%}", "bucket": bucket})
            elif pl_pct >= 0.05:
                trailing_trigger = entry_price * (1 + 0.05)
                trailing_stop = current_price * (1 + trailing_stop_pct)
                if current_price <= trailing_stop and current_price >= trailing_trigger:
                    result = self.close_position(symbol, f"Trailing stop ({bucket}): {pl_pct:.2%}")
                    if "error" not in result:
                        closed.append({"symbol": symbol, "action": "trailing_stop", "pl_pct": round(pl_pct, 4),
                                       "entry_price": entry_price, "exit_price": current_price,
                                       "reason": f"Trailing stop ({bucket}): {pl_pct:.2%}", "bucket": bucket})
        return closed

    # ==========================================
    # MAIN TRADING CYCLE
    # ==========================================

    def run_cycle(self) -> Dict:
        with self._lock:
            self.cycle_count += 1
            cycle_log = {"cycle": self.cycle_count, "timestamp": datetime.now().isoformat(),
                         "signals": [], "trades": [], "stops": [], "errors": [],
                         "profit_extraction": None, "dividends": None}

            if not self.connected:
                self._log_error(f"Cycle {self.cycle_count}: Not connected, reconnecting...")
                if not self._reconnect():
                    self.consecutive_failures += 1
                    return cycle_log

            self._check_and_reset_daily()

            try:
                stops = self.check_stops()
                cycle_log["stops"] = stops
                for s in stops:
                    self.status_message = f"{s['action']}: {s['symbol']} - {s['reason']}"
            except Exception as e:
                self._log_error(f"Stop check error: {e}")

            try:
                div_result = self.check_dividends()
                cycle_log["dividends"] = div_result
            except Exception as e:
                self._log_error(f"Dividend check error: {e}")

            try:
                if self.settings.get("auto_extract_profits", True):
                    ov = self.get_bucket_overview()
                    if ov.get("profit_threshold_hit", False):
                        extraction = self.extract_profits()
                        cycle_log["profit_extraction"] = extraction
                        if extraction.get("status") == "extracted":
                            self._log_error(f"Profit extracted: {extraction.get('message', '')}")
            except Exception as e:
                self._log_error(f"Profit extraction error: {e}")

            try:
                self.scan_all()
                active_signals = self.signals_found
                cycle_log["signals"] = [{"symbol": s["symbol"], "signal": s["signal"], "confidence": s["confidence"]} for s in active_signals]
            except Exception as e:
                self._log_error(f"Scan error: {e}")
                self.consecutive_failures += 1
                return cycle_log

            for signal in active_signals:
                if signal["signal"] == "BUY":
                    market = self.is_market_open()
                    if not market.get("is_open", True):
                        self.record_signal(signal, "rejected", "Market closed")
                        continue
                    try:
                        approval = self.evaluate_risk(signal)
                        if not approval.get("approved", False):
                            cycle_log["trades"].append({"symbol": signal["symbol"], "action": "rejected", "reason": approval.get("reason", "")})
                            continue
                        result = self.place_order(approval)
                        if "error" not in result:
                            cycle_log["trades"].append({"symbol": approval["symbol"], "action": "executed", "side": approval["side"], "qty": approval["qty"], "price": approval["price"], "reason": approval.get("reason", "")})
                            self.consecutive_failures = 0
                        else:
                            cycle_log["trades"].append({"symbol": signal["symbol"], "action": "error", "reason": result["error"]})
                    except Exception as e:
                        self._log_error(f"Trade execution error for {signal['symbol']}: {e}")

            try:
                account = self.get_account_info()
                if "error" not in account and self.daily_start_equity > 0:
                    self.daily_pnl = float(account.get("equity", 0)) - self.daily_start_equity
            except Exception: pass

            self.record_equity_snapshot()

            self.last_successful_cycle = datetime.now().isoformat()
            self.consecutive_failures = 0
            self.status_message = f"Cycle {self.cycle_count} done. {len(active_signals)} signals."
            cycle_log["errors"] = self.errors[-10:] if self.errors else []
            return cycle_log

    # ==========================================
    # BACKGROUND THREAD
    # ==========================================

    def start(self):
        if self.running:
            self.status_message = "Already running."
            return False
        if not self.connected:
            self.status_message = "Not connected. Connect to Alpaca first."
            return False
        if not self.terms_accepted:
            self.status_message = "Terms of service must be accepted before trading."
            self._log_error("Bot start blocked: Terms of service not accepted")
            return False
        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        market = self.is_market_open()
        if not market.get("is_open", True):
            self.status_message = f"Bot started. Market closed. Next: {market.get('next_open', '?')}"
        else:
            self.status_message = "Trading bot started."
        return True

    def stop(self):
        self.running = False
        self._stop_event.set()
        self.status_message = "Trading bot stopped."
        return True

    def _run_loop(self):
        while self.running and not self._stop_event.is_set():
            try:
                self._check_and_reset_daily()
                if not self.connected:
                    self._log_error("Connection lost, reconnecting...")
                    if not self._reconnect():
                        self._log_error("Reconnect failed, will retry next cycle")
                if self.connected:
                    market = self.is_market_open()
                    if market.get("is_open", True):
                        self.run_cycle()
                    else:
                        self.status_message = f"Market closed. Next: {market.get('next_open', '?')}. Waiting..."
                else:
                    self.status_message = f"Disconnected. Failures: {self.consecutive_failures}"
            except Exception as e:
                self._log_error(f"Cycle error: {e}")
                self.consecutive_failures += 1
                if self.consecutive_failures >= 10:
                    self._log_error(f"Too many failures ({self.consecutive_failures}). Pausing 5 min.")
                    self._stop_event.wait(300)
                    self.consecutive_failures = 0
            interval = self.settings.get("scan_interval_min", 5) * 60
            self._stop_event.wait(interval)
        self.running = False

    # ==========================================
    # LOGGING & STATUS
    # ==========================================

def _log_error(self, message: str):
    if not hasattr(self, 'errors'):
        self.errors = []
    entry = {"timestamp": datetime.now().isoformat(), "message": message}
    self.errors.append(entry)
    if len(self.errors) > 100: self.errors = self.errors[-50:]

    def get_status(self) -> Dict:
        return {
            "connected": self.connected, "running": self.running,
            "status_message": self.status_message,
            "cycle_count": self.cycle_count, "last_scan": self.last_scan_time,
            "last_successful_cycle": self.last_successful_cycle,
            "daily_pnl": round(self.daily_pnl, 2),
            "signals_count": len(self.signals_found),
            "trades_count": len(self.trade_log),
            "errors_count": len(self.errors),
            "consecutive_failures": self.consecutive_failures,
            "reconnect_count": self.reconnect_count,
            "last_reconnect_time": self.last_reconnect_time,
            "settings": dict(self.settings),
            "scan_summary": dict(self.scan_summary),
            "advanced_signals_available": ADVANCED_SIGNALS_AVAILABLE,
            "backtest_available": BACKTEST_AVAILABLE,
            "dividend_calendar_available": DIVIDEND_CALENDAR_AVAILABLE,
            "audit_available": AUDIT_AVAILABLE,
            "encryption_available": ENCRYPTION_AVAILABLE,
            "encryption_ready": ENCRYPTION_READY,
            "terms_accepted": self.terms_accepted,
        }
