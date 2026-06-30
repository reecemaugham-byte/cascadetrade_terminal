import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import os
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time

# ==========================================
# SET DEFAULTS (prevent NameError if imports fail)
# ==========================================
BACKTEST_AVAILABLE = False
ADVANCED_SIGNALS_AVAILABLE = False
ADVANCED_METRICS_AVAILABLE = False
DIVIDEND_CALENDAR_AVAILABLE = False
AUDIT_AVAILABLE = False
ENCRYPTION_AVAILABLE = False
ENCRYPTION_READY = False
ML_AVAILABLE = False
TA_AVAILABLE = False
YF_AVAILABLE = False
PANDAS_AVAILABLE = False
ALPACA_AVAILABLE = False

# ==========================================
# NOW TRY ACTUAL IMPORTS (overwrite defaults if successful)
# ==========================================

try:
    import yfinance as yf
    YF_AVAILABLE = True
except Exception:
    pass

try:
    import ta
    TA_AVAILABLE = True
except Exception:
    pass

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except Exception:
    pass

try:
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.model_selection import train_test_split
    ML_AVAILABLE = True
except Exception:
    pass

# XGBoost and LightGBM imports (Change 5)
try:
    from xgboost import XGBRegressor
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    from lightgbm import LGBMRegressor
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

try:
    import alpaca_trade_api as tradeapi
    ALPACA_AVAILABLE = True
except Exception:
    tradeapi = None

try:
    from core.backtest import BacktestEngine
    BACKTEST_AVAILABLE = True
except Exception:
    pass

try:
    from core.signals import generate_all_signals, calculate_combined_score, vix_filter
    ADVANCED_SIGNALS_AVAILABLE = True
except Exception:
    pass

try:
    from core.metrics import (
        calculate_sortino_ratio, calculate_calmar_ratio,
        calculate_omega_ratio, calculate_rolling_returns,
        calculate_drawdown_analysis, calculate_attribution_by_bucket,
        generate_full_report
    )
    ADVANCED_METRICS_AVAILABLE = True
except Exception:
    pass

try:
    from core.dividends import (
        get_upcoming_ex_dividends, get_dividend_yield as get_div_yield_external,
        get_dividend_history as get_div_history_external,
        get_dividend_growth, calculate_drip, get_dividend_comparison
    )
    DIVIDEND_CALENDAR_AVAILABLE = True
except Exception:
    pass

try:
    from core.audit import (
        log_audit, get_audit_trail, save_journal_entry,
        get_journal_entries, log_trade_audit, log_deposit_audit,
        log_settings_audit, log_login_audit
    )
    AUDIT_AVAILABLE = True
except Exception:
    pass

try:
    from core.encryption import encrypt_value, decrypt_value, is_encrypted, is_key_encrypted, verify_encryption_working
    ENCRYPTION_AVAILABLE = True
    ENCRYPTION_READY = verify_encryption_working()
except Exception:
    pass

# ==========================================
# TIER SYSTEM IMPORT
# ==========================================
try:
    from core.tiers import (
        get_user_tier, has_feature, get_tier_limits,
        get_tier_display, set_user_tier, get_all_users,
        get_upgrade_message, TIER_FEATURES, TIER_DISPLAY
    )
    TIERS_AVAILABLE = True
except Exception:
    TIERS_AVAILABLE = False

# ==========================================
# MAIN IMPORTS
# ==========================================

from trading_engine import (
    TradingEngine, US_QUICK_TURNOVER, US_LONG_TERM,
    DIVIDEND_STOCKS, GROWTH_STOCKS, BUCKET_ICONS
)

from core.database import (
    SessionLocal, User, Trade, authenticate_user, create_user,
    record_dividend, get_dividend_history,
    save_trade_to_db, load_trades_from_db, clear_trades_from_db
)

from core.terms import TERMS_OF_SERVICE, RISK_DISCLAIMER, PRIVACY_POLICY

# ==========================================
# DATABASE MIGRATION
# ==========================================
def ensure_db_columns():
    from sqlalchemy import text, inspect as sa_inspect
    db = SessionLocal()
    try:
        engine_obj = db.get_bind()
        inspector = sa_inspect(engine_obj)
        try:
            existing_columns = [col['name'] for col in inspector.get_columns('users')]
        except Exception:
            existing_columns = []

        columns_to_add = [
            ("terms_accepted", "BOOLEAN DEFAULT 0"),
            ("terms_accepted_date", "DATETIME"),
            ("login_attempts", "INTEGER DEFAULT 0"),
            ("account_locked_until", "DATETIME"),
            ("created_at", "DATETIME DEFAULT CURRENT_TIMESTAMP"),
            ("last_login", "DATETIME"),
            ("tier", "VARCHAR DEFAULT 'starter'"),
            ("tier_expires", "DATETIME"),
        ]

        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                try:
                    db.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                    db.commit()
                except Exception:
                    db.rollback()
    except Exception as e:
        print(f"DB migration note: {e}")
    finally:
        db.close()

ensure_db_columns()

# ==========================================
# CSV WATERMARK HELPER
# ==========================================
def watermark_csv(csv_string: str) -> str:
    watermark = "\nSource: QuantPro Terminal - Unauthorized reproduction prohibited"
    return csv_string + watermark

# ==========================================
# 1. PAGE CONFIG & STYLING
# ==========================================
st.set_page_config(page_title="QuantPro Terminal", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

hide_st_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)

# ==========================================
# 2. SESSION STATE & AUTH
# ==========================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = None

if "trading_engine" not in st.session_state:
    st.session_state.trading_engine = TradingEngine()

if "needs_onboarding" not in st.session_state:
    st.session_state.needs_onboarding = False

if "onboarding_step" not in st.session_state:
    st.session_state.onboarding_step = 1

if "confirm_start_bot" not in st.session_state:
    st.session_state.confirm_start_bot = False

if "confirm_sell_everything" not in st.session_state:
    st.session_state.confirm_sell_everything = False

if "confirm_rebalance" not in st.session_state:
    st.session_state.confirm_rebalance = False

# ==========================================
# 3. AUTHENTICATION GATE
# ==========================================
if not st.session_state.authenticated:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h1 style='text-align: center; color: #00d4aa;'>📈 QuantPro Terminal</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: #a0a0a0;'>Institutional-Grade Trading Engine</h3>", unsafe_allow_html=True)
        st.markdown("---")

        login_tab, register_tab = st.tabs(["🔑 Login", "🆕 Register"])

        with login_tab:
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pwd")

            if st.button("🔓 Unlock Terminal", use_container_width=True, type="primary"):
                db = SessionLocal()
                user = authenticate_user(db, username, password)
                if user:
                    _username = user.username
                    _terms_accepted = getattr(user, 'terms_accepted', True)
                    db.close()

                    if user:
                        st.session_state.authenticated = True
                        st.session_state.username = _username
                        if not _terms_accepted:
                            st.session_state.needs_onboarding = True
                            st.session_state.onboarding_step = 1
                        else:
                            st.session_state.trading_engine.terms_accepted = True
                            st.session_state.trading_engine.terms_accepted_date = datetime.utcnow()
                        st.session_state.username = _username
                        st.session_state.trading_engine.set_username(_username)
                        st.session_state.trading_engine._load_trade_log()

                        if AUDIT_AVAILABLE:
                            try: log_login_audit(_username)
                            except Exception: pass
                        st.success("Login successful!")
                        st.rerun()
                else:
                    st.error("⛔ Invalid Username or Password.")
                if not user:
                    db.close()

        with register_tab:
            new_user = st.text_input("Choose a Username", key="reg_user")
            new_pwd = st.text_input("Choose a Password", type="password", key="reg_pwd")
            new_pwd_confirm = st.text_input("Confirm Password", type="password", key="reg_pwd_confirm")

            with st.expander("📜 Terms of Service & Risk Disclaimer", expanded=False):
                st.text_area("Terms", value=TERMS_OF_SERVICE, height=200, disabled=True, key="tos_text")
                st.markdown("---")
                st.text_area("Disclaimer", value=RISK_DISCLAIMER, height=150, disabled=True, key="risk_text")
                st.markdown("---")
                st.text_area("Privacy", value=PRIVACY_POLICY, height=150, disabled=True, key="privacy_text")

            terms_agreed = st.checkbox("I agree to the Terms of Service and Risk Disclaimer", key="terms_agreed")

            if st.button("📝 Create Account", use_container_width=True):
                if not terms_agreed:
                    st.warning("You must agree to the Terms of Service and Risk Disclaimer to create an account.")
                elif new_pwd != new_pwd_confirm:
                    st.warning("Passwords do not match.")
                elif len(new_user) < 3:
                    st.warning("Username must be at least 3 characters.")
                elif len(new_pwd) < 6:
                    st.warning("Password must be at least 6 characters.")
                else:
                    db = SessionLocal()
                    existing_user = db.query(User).filter(User.username == new_user).first()
                    if existing_user:
                        st.error("Username already taken.")
                    else:
                        create_user(db, new_user, new_pwd)
                        new_user_obj = db.query(User).filter(User.username == new_user).first()
                        if new_user_obj and hasattr(new_user_obj, 'terms_accepted'):
                            new_user_obj.terms_accepted = False
                            db.commit()
                        st.success("Account created! Please switch to the Login tab.")
                    db.close()
    st.stop()

# ==========================================
# 3b. FIRST-TIME ONBOARDING
# ==========================================
if st.session_state.needs_onboarding:
    st.markdown("<h1 style='text-align: center; color: #00d4aa;'>🚀 Welcome to QuantPro Terminal</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #a0a0a0;'>Let's get you set up in a few quick steps.</h3>", unsafe_allow_html=True)
    st.markdown("---")

    step = st.session_state.onboarding_step

    if step == 1:
        st.markdown("### Step 1 of 4: 🏦 Create Your Alpaca Account")
        st.markdown("""
**Alpaca** is our brokerage partner that executes your trades. Paper Trading is **100% free** — you get a simulated account with fake money to test your strategies.

**What you need to do:**
1. Go to [Alpaca Markets](https://alpaca.markets) and create a free account
2. Navigate to your **Paper Trading** dashboard
3. Go to **App Settings → API Keys**
4. Generate a new API Key and Secret Key
5. Copy both keys — you'll paste them into the Settings panel in the sidebar

> 💡 **Tip:** Paper trading uses real market data but fake money. It's the safest way to learn!
""")
        st.markdown("[🌐 Go to Alpaca Markets](https://alpaca.markets)")
        if st.button("➡️ Next Step", use_container_width=True, type="primary", key="onb_next_1"):
            st.session_state.onboarding_step = 2
            st.rerun()

    elif step == 2:
        st.markdown("### Step 2 of 4: 🧠 OpenAI Account (Optional)")
        st.markdown("""
**OpenAI** powers the AI News Sentiment analysis in the Scanner & Analysis tab. It reads financial news headlines and provides a sentiment score for each stock.

**This is completely optional** — the bot works fine without it. But if you want AI-powered news insights:

1. Go to [OpenAI Platform](https://platform.openai.com) and create an account
2. Navigate to **API Keys** and generate a new key
3. A **$5 free credit** is included — this lasts for months of normal use

> 💡 **Cost:** Each sentiment analysis costs less than $0.001. Your $5 credit will last a very long time!
""")
        st.markdown("[🌐 Go to OpenAI Platform](https://platform.openai.com)")
        col_skip, col_next = st.columns(2)
        with col_skip:
            if st.button("⏭️ Skip This Step", use_container_width=True, key="onb_skip_2"):
                st.session_state.onboarding_step = 3
                st.rerun()
        with col_next:
            if st.button("➡️ Next Step", use_container_width=True, type="primary", key="onb_next_2"):
                st.session_state.onboarding_step = 3
                st.rerun()

    elif step == 3:
        st.markdown("### Step 3 of 4: 📡 Discord Alerts (Optional)")
        st.markdown("""
**Discord webhooks** send instant trade alerts directly to your Discord server. Get notified every time the bot buys, sells, or detects a signal.

**This is completely optional** — the bot runs fine without Discord alerts.

**How to set up a Discord webhook:**
1. Open [Discord](https://discord.com) and go to your server
2. Go to **Server Settings → Integrations → Webhooks**
3. Click **Create Webhook** and give it a name (e.g., "QuantPro Alerts")
4. Copy the **Webhook URL**
5. Paste it into the Settings panel in the sidebar

> 💡 **Tip:** Create two webhooks — one for live trade alerts and one for daily P&L summaries!
""")
        st.markdown("[🌐 Go to Discord](https://discord.com)")
        col_skip, col_next = st.columns(2)
        with col_skip:
            if st.button("⏭️ Skip This Step", use_container_width=True, key="onb_skip_3"):
                st.session_state.onboarding_step = 4
                st.rerun()
        with col_next:
            if st.button("➡️ Next Step", use_container_width=True, type="primary", key="onb_next_3"):
                st.session_state.onboarding_step = 4
                st.rerun()

    elif step == 4:
        st.markdown("### Step 4 of 4: 🎉 You're Ready!")
        st.markdown("""
🎊 **Congratulations!** You're all set to start using QuantPro Terminal.

**Quick start guide:**
1. 📌 Enter your Alpaca API keys in the **Settings** panel (left sidebar)
2. 🔌 Click **Connect** in the Auto Trade tab
3. 🎮 Start with **Paper Trading** to test the system
4. 📚 Check the **Academy** tab to learn how everything works

> ⚠️ **Important:** Always start with Paper Trading. Never risk real money until you're confident in your settings!

**You can always find your API keys and Discord settings in the sidebar.**
""")
        if st.button("✅ Complete Setup & Enter Dashboard", use_container_width=True, type="primary", key="onb_complete"):
            db = SessionLocal()
            user = db.query(User).filter(User.username == st.session_state.username).first()
            if user:
                if hasattr(user, 'terms_accepted'):
                    user.terms_accepted = True
                if hasattr(user, 'terms_accepted_date'):
                    user.terms_accepted_date = datetime.utcnow()
                db.commit()
            db.close()
            st.session_state.trading_engine.terms_accepted = True
            st.session_state.trading_engine.terms_accepted_date = datetime.utcnow()
            st.session_state.needs_onboarding = False
            st.session_state.onboarding_step = 1
            st.rerun()

    st.stop()

# ==========================================
# 4. MAIN DASHBOARD (Logged In)
# ==========================================

# Get user tier
user_tier = "starter"
tier_display = {"icon": "🆓", "label": "Starter (Free)", "color": "#a0a0a0"}
if TIERS_AVAILABLE:
    user_tier = get_user_tier(st.session_state.username)
    tier_display = get_tier_display(st.session_state.username)

with st.sidebar:
    st.markdown("<h1 style='text-align: center; color: #00d4aa;'>📈 QuantPro</h1>", unsafe_allow_html=True)
    st.markdown("---")

    # User info with tier badge
    tier_icon = tier_display.get("icon", "🆓")
    tier_label = tier_display.get("label", "Starter (Free)")
    st.success(f"🟢 Logged in as: **{st.session_state.username}**")
    st.caption(f"{tier_icon} **{tier_label}** | Paper Trading Mode")
    st.caption("⚠️ Trading involves risk. Not financial advice.")
    st.markdown("---")

    # --- MARKET STATUS ---
    engine = st.session_state.trading_engine
    market = engine.is_market_open()
    if market.get("is_open"):
        st.success(f"🟢 Market Open — {market.get('current_time_et', '')} ET")
        st.caption(f"Closes {market.get('market_close_time', '4:00 PM ET')}")
    else:
        st.error(f"🔴 Market Closed — {market.get('day_name', '')}")
        st.caption(f"Opens: {market.get('next_open', 'Unknown')}")

    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

    try:
        spy_data = yf.Ticker("SPY").history(period="1d")
        vix_data = yf.Ticker("^VIX").history(period="1d")
        if not spy_data.empty:
            spy_price = spy_data['Close'].iloc[-1]
            spy_open = spy_data['Open'].iloc[-1]
            spy_change = ((spy_price - spy_open) / spy_open) * 100
            st.metric("S&P 500 (SPY)", f"${spy_price:.2f}", f"{spy_change:.2f}%")
        if not vix_data.empty:
            vix_val = vix_data['Close'].iloc[-1]
            fear_level = "Extreme Fear" if vix_val > 25 else "Fear" if vix_val > 20 else "Neutral"
            vix_color = "🔴" if vix_val > 25 else "🟡" if vix_val > 20 else "🟢"
            st.metric("VIX (Fear Index)", f"{vix_val:.1f}", f"{vix_color} {fear_level}")
    except:
        st.warning("Market data unavailable.")

    if engine.settings.get("use_vix_filter", True) and ADVANCED_SIGNALS_AVAILABLE:
        vix_result = engine.check_vix()
        if not vix_result.get("safe_to_trade", True):
            st.error(f"🛡️ VIX Filter: {vix_result.get('reason', 'VIX too high')}")

    st.markdown("---")

    # --- TIER INFORMATION ---
    with st.expander("📋 Plan Details"):
        tier_limits = get_tier_limits(st.session_state.username) if TIERS_AVAILABLE else TIER_FEATURES.get("starter", {})

        st.markdown(f"**Your Plan: {tier_display.get('icon', '')} {tier_display.get('label', 'Starter')}**")
        st.markdown("---")

        features_list = [
            ("Paper Trading", "paper_trading", True),
            ("Basic Signals (RSI, MACD)", "basic_signals", True),
            ("Advanced Signals (Bollinger, MA Cross, VIX)", "advanced_signals", False),
            ("OpenAI Sentiment Analysis", "ai_sentiment", False),
            ("Multi-Timeframe Confirmation", "multi_timeframe", False),
            ("Live Trading (Real Money)", "live_trading", False),
            ("DRIP Calculator", "drip_calculator", False),
            ("Diamond Metrics (Sortino, Calmar, Omega)", "diamond_metrics", False),
            ("Auto Profit Extraction", "auto_profit_extraction", False),
            ("Backtesting", "backtesting", True),
            ("Discord Alerts", "discord_alerts", True),
            ("Dividend Calendar", "dividend_calendar", True),
            ("Trade Journal", "trade_journal", True),
        ]

        for feature_name, feature_key, default in features_list:
            has_access = tier_limits.get(feature_key, default)
            if has_access:
                st.markdown(f"✅ {feature_name}")
            else:
                st.markdown(f"🔒 {feature_name}")

        st.markdown("---")

        if user_tier == "starter":
            st.markdown("""
---

**⚡ Upgrade to Pro — $29/month**
- ✅ Advanced Signals (Bollinger, MA Cross, VIX Filter)
- ✅ OpenAI Sentiment Analysis
- ✅ Live Trading with Real Money
- ✅ DRIP Calculator & Dividend Calendar
- ✅ Diamond Metrics
- ✅ Auto Profit Extraction

---

**💎 Upgrade to Fund — $99/month**
- ✅ Everything in Pro
- ✅ Multiple Accounts
- ✅ Auto-Rebalancing
- ✅ Weekly Reports
- ✅ Priority Support
""")
        elif user_tier == "pro":
            st.markdown("""
---

**💎 Upgrade to Fund — $99/month**
- ✅ Multiple Accounts
- ✅ Auto-Rebalancing
- ✅ Weekly Reports
- ✅ Priority Support
""")

    # --- BROKER & ALERT SETTINGS ---
    with st.expander("⚙️ Settings (APIs & Discord)"):
        st.markdown("##### 🏦 Alpaca API Keys")
        st.caption("Enter your Alpaca Paper Trading keys.")

        db = SessionLocal()
        current_user = db.query(User).filter(User.username == st.session_state.username).first()
        if current_user:
            current_key = current_user.alpaca_api_key if current_user.alpaca_api_key else ""
            current_secret = current_user.alpaca_secret_key if current_user.alpaca_secret_key else ""
            current_webhook = current_user.discord_webhook_url if current_user.discord_webhook_url else ""
            current_webhook_daily = current_user.discord_webhook_url_daily if current_user.discord_webhook_url_daily else ""
            current_openai = current_user.openai_api_key if current_user.openai_api_key else ""
        else:
            current_key = ""
            current_secret = ""
            current_webhook = ""
            current_webhook_daily = ""
            current_openai = ""
        db.close()

        st.markdown("---")
        new_key = st.text_input("Alpaca API Key", value=current_key, type="password", key="api_key_input")
        st.caption("🔒 Your keys are encrypted at rest. Revoke anytime at [alpaca.markets](https://alpaca.markets)")
        new_secret = st.text_input("Alpaca Secret Key", value=current_secret, type="password", key="secret_key_input")
        st.caption("🔒 Never share your secret key.")

        st.markdown("---")
        st.markdown("##### 📡 Discord Webhooks")
        st.caption("Use two separate channels to keep alerts clean.")
        new_webhook = st.text_input("Live Trade Alerts URL", value=current_webhook, type="password", key="webhook_input")
        st.caption("🔔 Get instant trade alerts.")
        new_webhook_daily = st.text_input("Daily P&L URL", value=current_webhook_daily, type="password", key="webhook_daily_input")
        st.caption("📊 Receive daily summary reports.")

        st.markdown("---")
        st.markdown("##### 🧠 OpenAI Sentiment")
        st.caption("Used for AI news analysis only.")

        # Check tier for OpenAI
        if TIERS_AVAILABLE and not has_feature(st.session_state.username, "ai_sentiment"):
            st.warning("🔒 OpenAI Sentiment requires Pro or Fund tier.")
            new_openai = st.text_input("OpenAI API Key", value="", type="password", key="openai_input", disabled=True)
        else:
            new_openai = st.text_input("OpenAI API Key", value=current_openai, type="password", key="openai_input")
            st.caption("🧠 Used for AI news sentiment analysis only. $5 credit lasts months.")

        st.markdown("---")
        st.markdown("##### 🔒 Privacy Mode")
        privacy_mode = st.checkbox(
            "Privacy Mode (Discord shows % only, no $)",
            value=st.session_state.trading_engine.settings.get("discord_privacy_mode", True),
            key="privacy_mode_input"
        )
        st.session_state.trading_engine.settings["discord_privacy_mode"] = privacy_mode

        st.markdown("---")
        st.markdown("##### 🧪 Signal Settings")

        # Advanced signals tier check
        use_advanced = st.checkbox(
            "🔬 Advanced Signals (MACD, Bollinger, MA Cross)",
            value=st.session_state.trading_engine.settings.get("use_advanced_signals", True),
            key="use_advanced_signals_input",
            disabled=TIERS_AVAILABLE and not has_feature(st.session_state.username, "advanced_signals")
        )
        if TIERS_AVAILABLE and not has_feature(st.session_state.username, "advanced_signals"):
            st.caption("🔒 Advanced Signals require Pro tier or above.")
        else:
            st.session_state.trading_engine.settings["use_advanced_signals"] = use_advanced

        use_vix = st.checkbox(
            "🛡️ VIX Filter (Block buys when VIX > 28)",
            value=st.session_state.trading_engine.settings.get("use_vix_filter", True),
            key="use_vix_filter_input"
        )
        st.session_state.trading_engine.settings["use_vix_filter"] = use_vix

        use_atr = st.checkbox(
            "📐 ATR Position Sizing (Volatility-based)",
            value=st.session_state.trading_engine.settings.get("use_atr_position_sizing", True),
            key="use_atr_input"
        )
        st.session_state.trading_engine.settings["use_atr_position_sizing"] = use_atr

        if st.button("💾 Save All Settings", use_container_width=True, type="primary"):
            db = SessionLocal()
            user_to_update = db.query(User).filter(User.username == st.session_state.username).first()

            if user_to_update:
                user_to_update.alpaca_api_key = new_key
                user_to_update.alpaca_secret_key = new_secret
                user_to_update.discord_webhook_url = new_webhook
                user_to_update.discord_webhook_url_daily = new_webhook_daily
                user_to_update.openai_api_key = new_openai
                # Save profit skim to database
                user_to_update.profit_skim_pct = engine.settings.get("profit_skim_pct", 1.0)
                db.commit()

                st.session_state.trading_engine.settings["discord_webhook_url"] = new_webhook
                st.success("All settings saved securely!")
            else:
                st.error("User not found.")
            db.close()
            st.session_state.trading_engine.connected = False

        with st.columns(2)[1]:
            if st.button("🔔 Test Discord", use_container_width=True):
                if not new_webhook:
                    st.warning("Enter Webhook URL first.")
                else:
                    with st.spinner("Sending..."):
                        try:
                            from core.alerts import send_discord_alert
                            success = send_discord_alert(new_webhook, "🟢 **QuantPro Terminal is Online!**")
                            if success: st.success("Check Discord!")
                            else: st.error("Failed. Check URL.")
                        except Exception as e:
                            st.error(f"Error: {e}")

    st.markdown("---")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.session_state.needs_onboarding = False
        st.session_state.onboarding_step = 1
        st.session_state.confirm_start_bot = False
        st.rerun()

st.header("📊 QuantPro Terminal")
st.markdown(f"### Welcome back, **{st.session_state.username}**.")

# TABS - Now 6 tabs (Scanner + Deep AI merged)
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["📚 Academy", "🔬 Scanner & Analysis", "💰 Auto Trade", "📊 Portfolio", "🔬 Backtest", "💎 Dividends"])

# ==========================================
# TAB 1: ACADEMY (Education Content)
# ==========================================
with tab1:
    st.markdown("### 📚 Academy: How It Works")
    st.caption("Everything you need to know about QuantPro Terminal. Click any topic to expand it.")

    # 1. Getting Started
    with st.expander("🎓 1. Getting Started (Beginner)"):
        st.markdown("""
**What is QuantPro Terminal?**
QuantPro is an automated trading engine that scans the stock market for buy and sell signals based on technical indicators. It executes trades on your behalf via Alpaca (a secure US brokerage).

**What are the 3 buckets?**
Your money is split into three buckets based on risk:
- 🟢 **Dividend Pot:** Steady income, lower risk, slow growth. Buys stocks that pay dividends.
- 🔵 **Growth Pot:** Moderate risk, faster growth, more volatility. Buys large companies without dividends.
- 🔴 **Penny Pot:** High risk, high reward potential, can lose everything. Buys stocks under $5.
- 🟡 **Withdrawal Pot:** Your profit pot. LOCKED from trading. Only you can withdraw from here.

**How does the bot decide what to buy/sell?**
The bot uses technical indicators (RSI, MACD, Bollinger Bands, Volume) to find stocks that are oversold (cheap) or overbought (expensive). When a stock hits a buy signal, it checks your risk settings before buying.

**What is paper trading vs real money?**
QuantPro starts in **Paper Trading** mode by default. This uses fake money but real market data. You cannot lose real money in paper mode. **Always start here.**

**Glossary of terms:**
- **RSI (Relative Strength Index):** Measures if a stock is overbought (too high) or oversold (too low).
- **Volume / RVOL:** How many shares are being traded. High volume = strong signal.
- **Stop Loss:** Auto-sells a stock if it drops by a certain % to prevent big losses.
- **Take Profit:** Auto-sells a stock when it goes up by a certain % to lock in gains.
- **Confidence:** How strong the buy/sell signal is (0-100%).
""")

    # 2. Understanding Risk
    with st.expander("⚠️ 2. Understanding Risk (Important)"):
        st.markdown("""
**What does each slider do?**
- **Max Positions:** How many stocks you can hold at once. More positions = higher exposure.
- **Max Position %:** The max % of your portfolio put into one stock. Higher = more concentrated risk.
- **Daily Loss Limit %:** Stops trading for the day if you lose this %. 3% is safe.
- **Stop Loss %:** Auto-sells a stock if it drops this %. Tighter (<3%) gets triggered by normal dips.
- **Take Profit %:** Auto-sells a stock when it rises this %. Higher targets may never be reached.
- **Min Confidence:** Minimum signal strength required to buy. Lower = more trades, but more false signals.
- **Min RVOL:** Minimum volume spike required. Lower than 1.0 means trading on low interest.
- **Penny % Allocation:** How much money goes to penny stocks. They are extremely high risk.

**Why defaults are set to "safe trader" levels:**
The default settings (Stop Loss 5%, Take Profit 10%, etc.) are designed to protect beginners from blowing up their accounts. They give stocks room to breathe while locking in profits reliably.

**What happens if you increase risk (with real examples):**
- **Stop Loss at 2%:** You buy a stock at $100. It drops to $98 (a normal bad day). The bot sells. It goes back up to $110 the next week. You missed the recovery because your stop was too tight.
- **Daily Loss at 10%:** The market has a bad crash. You lose 10% of your entire portfolio in one day. A 10% loss requires an 11.1% gain just to break even.
- **Penny Allocation at 50%:** Half your money is in stocks under $5. These companies frequently go bankrupt. You could lose half your account permanently.

**Why penny stocks are dangerous:**
Penny stocks (under $5) are cheap for a reason—often the companies are failing, have low liquidity, or are subject to scams. While they can double quickly, they can also go to $0 just as fast.

**The difference between confidence % and signal strength:**
A stock with 20% confidence means 4 out of 5 indicators are disagreeing. The bot is basically guessing. 25%+ means a slight majority of indicators agree. 50%+ means strong agreement.
""")

    # 3. The 3-Bucket System
    with st.expander("🪣 3. The 3-Bucket System"):
        st.markdown("""
**How your money is protected:**
Instead of putting all your money in one place, QuantPro splits it into buckets:

🟢 **Dividend Pot (Steady, Slow, Safe):**
Buys stocks that pay you just for holding them. These are large, established companies (like Coca-Cola or Johnson & Johnson). They don't grow fast, but they pay you cash regularly.

🔵 **Growth Pot (Moderate Risk, Faster Growth):**
Buys large companies that don't pay dividends but are growing fast (like Amazon or Meta). More volatile, but higher upside potential.

🔴 **Penny Pot (High Risk, High Reward):**
Buys stocks under $5. These are usually small, new, or struggling companies. They can double in a day, or go to zero. **Never put more than 30% of your money here.**

🟡 **Withdrawal Pot (LOCKED):**
Your profit pot. When the bot makes money, it skims a percentage (or all) of the profit into this pot. **The bot CANNOT trade with money in the Withdrawal Pot.** This guarantees you keep your gains.

**How profits flow:**
Penny Profits → Growth Pot → Growth Profits → Dividend Pot → Dividends → Withdrawal Pot → Your Bank Account

**Why this system protects your capital:**
If the market crashes, your Dividend pot might drop 5%, your Growth pot might drop 10%, and your Penny pot might drop 30%. But because your money is spread out, and your profits are locked in Withdrawal, a crash won't wipe you out.

**Setting allocation to 0%:**
You can completely disable any bucket by setting its allocation to 0%. The bot will skip all buy signals for that bucket. This is useful if you only want to trade 1 or 2 strategies.
""")

    # 4. How Signals Work
    with st.expander("📊 4. How Signals Work"):
        st.markdown("""
**What is RSI (Relative Strength Index)?**
RSI gives a number between 0 and 100. If RSI is below 30 (oversold), the stock has dropped a lot and might bounce back (potential BUY). If RSI is above 70 (overbought), the stock has risen a lot and might drop (potential SELL).

**What is MACD?**
Moving Average Convergence Divergence. It compares two moving averages of a stock's price. When the fast line crosses above the slow line, it's a bullish signal (price might go UP). When it crosses below, it's a bearish signal (price might go DOWN).

**What are Bollinger Bands?**
They draw a "band" around the stock's price. If the price touches the bottom band, the stock is oversold (cheap). If it touches the top band, it's overbought (expensive). When the band squeezes narrow, a big move is coming.

**What does confidence % actually mean?**
It's how many indicators agree. If RSI says buy, MACD says buy, and Bollinger says buy, confidence is high (e.g., 60-80%). If RSI says buy but MACD says sell, confidence is low (e.g., 15-20%). The bot only buys when confidence is above your minimum threshold.

**Why VIX filter blocks trades in volatile markets:**
The VIX is the "Fear Index". When VIX is above 28, the market is panicking. During panics, normal signals don't work—stocks drop together regardless of fundamentals. The VIX filter prevents the bot from buying during market crashes.

**What is ATR position sizing?**
Average True Range measures how much a stock typically moves in a day. A volatile stock might move $5 a day; a calm stock might move $0.50. ATR position sizing makes sure you buy fewer shares of volatile stocks and more shares of calm stocks, keeping your risk level consistent.

**QuantPro uses multiple indicators together:**

| Indicator | What It Detects | Weight | Tier |
|-----------|----------------|--------|------|
| 🔴 RSI | Overbought/Oversold | 1.0 | Free |
| 📊 MACD | Momentum crossovers | 1.2 | Pro |
| 📈 Bollinger Bands | Price touching extremes | 0.8 | Pro |
| ✨ MA Crossover | Trend changes (Golden/Death Cross) | 1.5 | Pro |
| 💥 Volume Spike | Unusual activity | 0.6 | Free |
| 📉 ATR | Volatility (position sizing) | 0.5 | Pro |
| 🛡️ VIX Filter | Market fear (blocks buys when VIX > 28) | N/A | Pro |
""")

    # 5. Reading the Dashboard
    with st.expander("🖥️ 5. Reading the Dashboard"):
        st.markdown("""
**What each number means:**
- **Portfolio Value:** Total value of your stocks + cash.
- **Equity:** How much you actually own (Portfolio Value minus borrowed money).
- **Cash:** How much money is sitting in your account, not invested in stocks.
- **Buying Power:** How much you can spend on new stocks today.
- **Daily P&L:** How much profit or loss you made today.

**How to read your P&L:**
🟢 Green numbers mean profit. 🔴 Red numbers mean loss. P&L updates in real-time as stock prices change throughout the day.

**What the bucket overview tells you:**
The 4 colored boxes show how much money is in each bucket. The important one is **🟡 Withdrawal**—this is money the bot CANNOT touch. It's your locked-in profit.

**How to interpret signals vs near-signals:**
- **Signal:** The stock meets all your criteria (RSI, Volume, Confidence). The bot wants to buy/sell it.
- **Near Signal:** The stock is close to a signal but not quite there (e.g., RSI is 32 but your threshold is 30). The bot is watching it but won't trade yet.
""")

    # 6. Common Mistakes
    with st.expander("❌ 6. Common Mistakes"):
        st.markdown("""
**1. Don't move sliders to risky levels without understanding**
If you set Stop Loss to 2%, you will get sold out of trades constantly on normal dips. If you set Daily Loss to 10%, one bad day can wipe out weeks of gains. The red warnings in the settings are there for a reason.

**2. Don't turn off stop losses**
Stop losses are your emergency parachute. Without them, a stock that drops 50% requires a 100% gain just to break even. Always use stops.

**3. Don't put all capital in the penny bucket**
Penny stocks can be exciting, but they are extremely risky. If you put 100% of your money in the penny bucket, you could lose it all. Keep penny allocation at 30% or below.

**4. Paper trade FIRST before real money**
Paper trading uses fake money. Use it for at least 2-4 weeks to see how the bot performs. Only switch to real money when you are comfortable with the wins AND the losses.

**5. Don't chase losses**
If the bot loses money on a trade, don't immediately crank up the risk settings to "make it back faster." This is how gamblers lose everything. Stick to the safe defaults and let the bot's statistical edge play out over time.

**6. Check the Withdrawal Pot regularly**
When profits accumulate in the Withdrawal Pot, actually withdraw them to your bank account. That's the whole point of profit skimming!
""")

    # 7. FAQ
    with st.expander("❓ 7. FAQ"):
        st.markdown("""
**How do I connect Alpaca?**
1. Go to [Alpaca Markets](https://alpaca.markets) and create a free account.
2. Go to your Paper Trading dashboard and generate API Keys.
3. Paste the Key and Secret into the Settings panel in the sidebar.
4. Click "Connect" in the Auto Trade tab.

**Paper trading vs live trading?**
Paper trading uses fake money but real market data. It's 100% free. Live trading uses real money. QuantPro starts in Paper mode by default. You must explicitly switch to live trading in your Alpaca dashboard (not in this app) to use real money.

**How do I withdraw profits?**
The bot automatically skims profits into your 🟡 Withdrawal Pot. To get this money out:
1. Click "Move from Withdrawal" or go to your Alpaca dashboard.
2. Transfer the funds from your Alpaca account to your linked bank account.

**What happens if the bot crashes?**
QuantPro runs in cycles (default: every 5 minutes). If it crashes, it will not place any new trades. Any existing stop-loss orders placed on Alpaca's servers will still execute even if the bot is offline.

**How do I cancel my subscription?**
Go to the Upgrade page in the sidebar and click "Manage Subscription" or contact support.

**Is this financial advice?**
No. QuantPro Terminal is automated trading software. It does not provide personalized financial advice. Trading involves risk, and you can lose money. Always start with paper trading.
""")

    # ==========================================
    # OPERATIONAL GUIDE SECTIONS (From original)
    # ==========================================

    with st.expander("⚡ Profit Extraction & Skimming"):
        st.markdown("""
**How profit extraction works:**
- The bot tracks your total profit relative to your original capital
- When your profit crosses a threshold, it automatically sells your most profitable positions
- The freed cash goes into your **Withdrawal Pot** (locked from trading)
- You can then withdraw this money to your bank account

**Threshold types:**
- **Percentage threshold** (default: 20%) — Extracts when your total profit exceeds 20% of your starting capital
- **Dollar threshold** (default: $20,000) — Extracts when your total profit exceeds $20,000

**Auto-extract:** When enabled, the bot checks every cycle and extracts automatically when the threshold is hit.

**Manual extract:** Click "⚡ Extract Profits Now" in the Auto Trade tab to force an extraction at any time.

**🛡️ Profit Skimming (Auto-Lock):**
- When the bot sells a profitable stock, it splits the money based on your Profit Skimming % setting.
- **100% Skim (Safest):** All profit goes to the 🟡 Withdrawal Pot. Only the original buy price goes back to the trading bucket. The bot can NEVER spend your profits.
- **50% Skim:** Half the profit goes to Withdrawal, half goes back to trading to compound.
- **0% Skim:** All money (original + profit) goes back to trading. Highest risk of giving back profits.

> 💡 **Tip:** The withdrawal pot is LOCKED from trading. The bot cannot trade with money in the Withdrawal Pot. Only you can move money out of it.
""")

    with st.expander("🛑 Sell Everything & Rebalance"):
        st.markdown("""
**🛑 Sell Everything:**
- Sells ALL open positions immediately
- All proceeds go into your 🟡 **Withdrawal Pot** (LOCKED from trading)
- The bot cannot use Withdrawal Pot money to buy stocks
- Use this when you want to exit the market completely or protect profits

**🔄 Rebalance:**
- Sells everything, then redistributes the cash across your 3 buckets
- Follows your allocation percentages (e.g., 35% Dividend, 35% Growth, 30% Penny)
- The bot will then buy new positions according to its signals

**💸 Move from Withdrawal:**
- Move money from your 🟡 Withdrawal Pot back into a specific trading bucket
- Options: Move to 🟢 Dividend, 🔵 Growth, or 🔴 Penny
- Or redistribute across all 3 buckets based on your allocation percentages
- Once money moves to a trading bucket, the bot CAN use it to buy stocks

**⚠️ Safety:** The Withdrawal Pot is always protected. The bot cannot trade with money in the Withdrawal Pot. Only you can move money out of it.
""")

    with st.expander("💎 Dividends & DRIP"):
        st.markdown("""
**How dividends work in QuantPro:**
1. When a stock you hold pays a dividend, Alpaca credits it to your account
2. Click "💎 Check Dividends" to scan for new dividend payments
3. Dividend income flows into your **Withdrawal Pot** (locked from trading)
4. You can withdraw this money to your bank account

**Ex-Dividend Dates:**
- The Dividends tab shows upcoming ex-dividend dates for stocks in your watchlist
- You must own the stock **before** the ex-dividend date to receive the dividend

**DRIP Calculator:**
- DRIP = Dividend Reinvestment Plan
- The calculator shows how much your dividend income would grow if you reinvested dividends
- Enter a stock symbol and number of shares to see a 10-year projection

**Dividend Stock Comparison:**
- Compare dividend yields and growth rates across your watchlist
- Helps you find the best dividend stocks for your Dividend Pot
""")

    with st.expander("📊 Backtesting"):
        st.markdown("""
**What is backtesting?**
- Testing your strategy against historical data to see how it would have performed
- Uses the same signals and settings as live trading, but with past data
- Does NOT guarantee future results, but helps you validate your settings

**How to use it:**
1. Go to the Backtest tab
2. Enter a list of stock symbols (or use the default list)
3. Choose a date range and strategy
4. Click "Run Backtest"
5. Review the results — equity curve, win rate, drawdown, etc.

**Key metrics:**
- **Total Return**: How much your portfolio gained or lost
- **Win Rate**: Percentage of trades that were profitable
- **Max Drawdown**: The largest peak-to-trough decline
- **Sharpe Ratio**: Risk-adjusted return (higher is better, >1 is good)
- **Profit Factor**: Total wins divided by total losses (>1 is profitable)
""")

    with st.expander("📊 Diamond Metrics"):
        st.markdown("""
**Beyond basic metrics — the professional standard:**

**Sortino Ratio** — Like Sharpe, but only penalizes downside volatility. >1 is good, >2 is excellent.

**Calmar Ratio** — Annual return divided by maximum drawdown. >1 means you're earning more than you're risking in drawdowns.

**Omega Ratio** — Probability of gains vs losses. >1 means more gains than losses.

**Best/Worst Day** — Your single best and worst day returns. Helps you understand tail risk.

These metrics are available in the Portfolio tab when you have enough trade history.
""")

    with st.expander("🔐 Privacy Mode"):
        st.markdown("""
**What Privacy Mode does:**
- When enabled, Discord alerts show **percentages only** — no dollar amounts
- Example: "🟢 **BUY** **AAPL** (Growth) | Confidence: 75% | Stop: 6% | Target: 12%"
- Without privacy mode, alerts show dollar amounts: "🟢 **BUY** 10 shares of **AAPL** at $150.00"

**How to enable:**
- Go to Settings in the sidebar
- Toggle "Privacy Mode (Discord shows % only, no $)"

**Why use it:**
- If you share your Discord channel with others, they won't see your position sizes or dollar amounts
- Your trading activity stays private while still getting alerts
""")

    with st.expander("📋 Trade Journal"):
        st.markdown("""
**Why journal your trades?**
- Professional traders review every trade to learn what works and what doesn't
- Emotions like FOMO, anxiety, or overconfidence affect decisions more than we think
- Tracking your emotional state helps you identify patterns

**How to use it:**
1. Go to the Portfolio tab
2. Find "📝 Trade Journal" and click "➕ Add Journal Entry"
3. Enter the symbol, action (buy/sell/hold), and your reasoning
4. Select your emotional state (Confident, Anxious, FOMO, etc.)
5. Write what you learned from this trade

**Review your entries:**
- Your last 5 journal entries are shown in the Portfolio tab
- Look for patterns: Do you make worse decisions when anxious? Do FOMO trades lose money?
- Over time, this helps you become a more disciplined trader
""")

    with st.expander("🤖 Auto Trade — How It Works"):
        st.markdown("""
**Starting the bot:**
1. Enter your Alpaca API keys in the sidebar Settings
2. Click "Connect" in the Auto Trade tab
3. Click "Start Bot" (you'll be asked to confirm)
4. The bot will scan for signals at the interval you set (default: 5 minutes)

**What the bot does each cycle:**
1. Checks if the market is open
2. Checks VIX filter (if enabled)
3. Scans your watchlist for signals
4. For each BUY signal, evaluates risk (position limits, sector limits, allocation, confidence)
5. If approved, places a market order
6. Checks stop losses and take profits on existing positions
7. Checks for dividends
8. Checks if profit extraction threshold is hit (if auto-extract enabled)
9. Records an equity snapshot

**Important notes:**
- The bot ONLY trades during US market hours (9:30 AM - 4:00 PM ET)
- Paper trading uses fake money — you cannot lose real money
- You can stop the bot at any time by clicking "Stop Bot"
- You can manually scan once by clicking "Scan Once"
""")

    st.caption("QuantPro Terminal — Automated trading software. Not a financial advisor. Trading involves risk.")

# ==========================================
# TAB 2: SCANNER & ANALYSIS (Merged)
# ==========================================
with tab2:
    scan_tab1, scan_tab2 = st.tabs(["📊 Global Scanner", "🤖 Deep Analysis"])

    # --- GLOBAL SCANNER SUB-TAB ---
    with scan_tab1:
        st.markdown("### 📊 Global Scanner")
        save_file = "my_custom_scan_list.txt"

        def load_custom_list():
            if os.path.exists(save_file):
                try:
                    with open(save_file, "r") as f: return f.read()
                except: return ""
            return ""

        def save_custom_list(text_data):
            try:
                with open(save_file, "w") as f: f.write(text_data)
                return True
            except: return False

        scan_mode = st.selectbox("Select Universe", ["S&P 500 (US Blue Chips)", "Tech Giants", "High Volatility", "Custom List"])
        col1, col2 = st.columns([1, 1])
        with col1: run_scan = st.button("▶️ Run Scan", type="primary")
        with col2: show_corr = st.checkbox("Generate Correlation Matrix", value=False)

        tickers = []
        if scan_mode == "S&P 500 (US Blue Chips)":
            us_list = """AAPL,MSFT,AMZN,GOOGL,GOOG,META,NVDA,TSLA,BRK.B,JPM,JNJ,V,UNH,HD,PG,MA,XOM,BAC,CVX,MRK,ABBV,LLY,WMT,PFE,KO,PEP,TMO,COST,AVGO,MCD,ABT,CSCO,DHR,ACN,CMCSA,NEE,NFLX,WFC,ADBE,PM,LIN,UPS,TXN,QCOM,BMY,LOW,RTX,HON,SBUX,AMGN,ISRG,INTC,AMD,DE,IBM,GS,MS,AXP,C,BA,CAT,GE,SYK,MDLZ,TJX,AMT,CME,INTU,SPGI,PLD,GIS,MO,ZTS,DELL,BLK,COP,NKE,AXON,MU,EOG,SLB,BDX,SCHW,SYF,ET,CL,PLTR,NEE,CVS,CNC,USB,SO,PNC,SHW,D,DUK,NSC,ITW,HES,CI,CME,F,CSX,AON,AIG,ICE,MS,MMC,NSC,HCA,MET,AFL,EL,WMB,PNC,AEP,SLB,BKR,HAL,APH,ANET,FSLR,CTAS,KMB,JCI,EQIX,PGR,DHI,MAR,MCK,EOG,ICE,CTVA,BKR,LHX,MRNA,BIIB,EA,ROST,DLTR,COST,INTU,ADSK,CSGP,FTNT,SNPS,KLAC,LRCX,MRVL,TXN,MSCI,MNK,TSLA"""
            tickers = [t.strip() for t in us_list.split(',') if t.strip()]
            st.info(f"Loaded {len(tickers)} US Blue Chip stocks.")
        elif scan_mode == "Tech Giants":
            tickers = "AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,AMD,INTC,NFLX,PYPL,ADBE,CRM,ORCL,IBM,QCOM,TXN,AVGO,INTU,SHOP,SNOW,PLTR,COIN".split(',')
            st.info(f"Loaded {len(tickers)} Tech Giants.")
        elif scan_mode == "High Volatility":
            tickers = "NIO,PLTR,AMD,MARA,RIOT,LCID,FFIE,CEI,BBAI,PROG,SOLO,IRNT,HYMC,ATXI,SAVA,INVO,DGLY".split(',')
            st.info(f"Loaded {len(tickers)} Volatile stocks.")
        elif scan_mode == "Custom List":
            default_text = load_custom_list()
            if not default_text: default_text = "AAPL, TSLA, BA"
            user_list = st.text_area("Enter Tickers (comma separated)", value=default_text, height=100)
            tickers = [t.strip().upper() for t in user_list.split(',') if t.strip()]
            st.info(f"Loaded {len(tickers)} custom tickers.")

        results = []
        rsi_dict = {}
        price_dict = {}

        if run_scan and tickers:
            if not TA_AVAILABLE:
                st.error("Library 'ta' missing. Please run: pip install ta")
            else:
                st.info(f"Scanning {len(tickers)} stocks... Using batch download for speed.")
                prog = st.progress(0)

                # ===== CHANGE 1: Batch download for speed =====
                batch_data = {}
                failed_symbols = []
                chunk_size = 50

                for c in range(0, len(tickers), chunk_size):
                    chunk = tickers[c:c + chunk_size]
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
                                    sym_df = batch_df[symbol].copy()

                                # Normalize columns
                                sym_df.columns = [str(col).lower().replace(' ', '_') for col in sym_df.columns]

                                # Drop adj_close if present
                                if 'adj_close' in sym_df.columns:
                                    sym_df = sym_df.drop(columns=['adj_close'])

                                # Drop rows with NaN close
                                if 'close' in sym_df.columns:
                                    sym_df = sym_df.dropna(subset=['close'])

                                if not sym_df.empty and len(sym_df) >= 20:
                                    batch_data[symbol] = sym_df
                            except Exception:
                                failed_symbols.append(symbol)
                    except Exception:
                        failed_symbols.extend(chunk)

                    prog.progress(min(0.8, (c + len(chunk)) / len(tickers) * 0.8))

                # Fallback for failed symbols (one-by-one)
                if failed_symbols:
                    st.caption(f"⚡ Retrying {len(failed_symbols)} symbols individually...")
                    for symbol in failed_symbols:
                        if symbol not in batch_data:
                            try:
                                df_single = yf.Ticker(symbol).history(period="3mo")
                                if df_single is not None and not df_single.empty and len(df_single) >= 20:
                                    df_single.columns = [c.lower() for c in df_single.columns]
                                    if 'adj_close' in df_single.columns:
                                        df_single = df_single.drop(columns=['adj_close'])
                                    batch_data[symbol] = df_single
                            except Exception:
                                pass

                prog.progress(0.85)

                # Process all downloaded data
                for i, symbol in enumerate(tickers):
                    if symbol not in batch_data:
                        continue

                    df = batch_data[symbol]
                    source = "⚡ BATCH"

                    try:
                        rsi_series = ta.momentum.RSIIndicator(df['close']).rsi()
                        rsi_val = rsi_series.iloc[-1]
                        price = df['close'].iloc[-1]
                        avg_vol = df['volume'].rolling(20).mean().iloc[-1]
                        curr_vol = df['volume'].iloc[-1]
                        rvol = curr_vol / avg_vol if avg_vol > 0 else 0

                        if not np.isnan(rsi_val):
                            rsi_dict[symbol] = rsi_val
                        if np.isnan(rsi_val):
                            rsi_val = 50.0

                        rvol_icon = "💥" if rvol > 2.0 else ""

                        if rsi_val < 30:
                            status = f"🟢 BUY {rvol_icon}"
                        elif rsi_val > 70:
                            status = f"🔴 SELL {rvol_icon}"
                        elif rsi_val < 40:
                            status = "🌱 BUY ZONE"
                        elif rsi_val > 60:
                            status = "🍂 SELL ZONE"
                        else:
                            status = "⚪ NEUTRAL"

                        bucket = engine.assign_bucket(symbol)
                        bucket_icon = BUCKET_ICONS.get(bucket, "⚪")
                        div_icon = "💎" if symbol in DIVIDEND_STOCKS else ""

                        results.append({
                            "Ticker": symbol, "Price": f"${price:.2f}", "RVOL": f"{rvol:.1f}",
                            "RSI": f"{rsi_val:.0f}", "Bucket": f"{bucket_icon} {bucket.title()}",
                            "Status": status
                        })
                    except Exception as e:
                        pass

                prog.progress(1.0)

                if results:
                    df_res = pd.DataFrame(results)

                    def color_rsi(val):
                        try:
                            v = float(val)
                            if v < 30: return 'background-color: #d4edda; color: black'
                            elif v > 70: return 'background-color: #f8d7da; color: black'
                            else: return ''
                        except: return ''

                    def color_rvol(val):
                        try:
                            v = float(val)
                            if v > 2.0: return 'background-color: #fff3cd; color: black'
                            else: return ''
                        except: return ''

                    styled_df = df_res.style.map(color_rsi, subset=['RSI']).map(color_rvol, subset=['RVOL'])
                    st.dataframe(styled_df, use_container_width=True)

                st.caption("QuantPro Terminal — Automated trading software. Not a financial advisor. Trading involves risk.")

    # --- DEEP ANALYSIS SUB-TAB ---
    with scan_tab2:
        st.markdown("### 🤖 Deep Analysis")
        st.markdown("Select a stock for ML Prediction and AI News Sentiment.")

        # Tier check for AI Sentiment
        if TIERS_AVAILABLE and not has_feature(st.session_state.username, "ai_sentiment"):
            st.warning("🔒 **AI News Sentiment requires Pro or Fund tier.** Upgrade to unlock OpenAI-powered news analysis.")
            deep_ticker = st.text_input("Enter Ticker Symbol", value="AAPL", key="deep_ticker")
            analyze_btn = st.button("🔬 Analyze (Basic)", type="primary")
            ai_sentiment_enabled = False
        else:
            deep_ticker = st.text_input("Enter Ticker Symbol", value="AAPL", key="deep_ticker").upper()
            analyze_btn = st.button("🔬 Analyze", type="primary")
            ai_sentiment_enabled = True

        if analyze_btn and deep_ticker:
            if not ML_AVAILABLE:
                st.error("Missing ML libraries.")
            else:
                with st.spinner("Fetching deep data..."):
                    stock_data = yf.Ticker(deep_ticker)
                    df = stock_data.history(period="2y")
                    if df.empty:
                        st.error("No data found.")
                    else:
                        df.columns = [c.lower() for c in df.columns]
                        st.markdown("##### 📈 Chart & Patterns")
                        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
                        fig.update_layout(xaxis_rangeslider_visible=False, height=400, template="plotly_dark")
                        st.plotly_chart(fig, use_container_width=True)

                        # Bucket classification
                        bucket = engine.classify_stock(deep_ticker)
                        bucket_icon = BUCKET_ICONS.get(bucket, "⚪")
                        penny_threshold = engine.settings.get("penny_price_threshold", 5.0)
                        min_div = engine.settings.get("min_dividend_yield", 0.03)

                        price = df['close'].iloc[-1]
                        try:
                            info = stock_data.info or {}
                            div_yield = info.get('dividendYield', 0)
                            div_yield_pct = f"{div_yield * 100:.2f}%" if div_yield else "0.00%"
                        except Exception:
                            div_yield = 0
                            div_yield_pct = "N/A"

                        st.markdown(f"##### 🪣 Bucket Classification: {bucket_icon} **{bucket.title()}**")
                        st.markdown(f"- **Price:** ${price:.2f} (Penny threshold: ${penny_threshold:.2f})")
                        st.markdown(f"- **Dividend Yield:** {div_yield_pct} (Minimum: {min_div * 100:.1f}%)")

                        # Multi-timeframe check (Pro feature)
                        if TIERS_AVAILABLE and has_feature(st.session_state.username, "multi_timeframe") and engine.settings.get("use_multi_timeframe", False) and ADVANCED_SIGNALS_AVAILABLE:
                            st.markdown("---")
                            st.markdown("##### 🔭 Multi-Timeframe Confirmation")
                            from core.signals import multi_timeframe_check
                            mtf = multi_timeframe_check(deep_ticker)
                            combined = mtf.get("combined", {})
                            weekly = mtf.get("weekly", {})
                            daily = mtf.get("daily", {})
                            wt = "🟢 BUY" if weekly.get("signal") == "BUY" else "🔴 SELL" if weekly.get("signal") == "SELL" else "⚪ HOLD"
                            dt = "🟢 BUY" if daily.get("signal") == "BUY" else "🔴 SELL" if daily.get("signal") == "SELL" else "⚪ HOLD"
                            st.write(f"**Weekly:** {wt} | **Daily:** {dt}")
                            if combined.get("signal") != "HOLD":
                                conf = combined.get("confidence", 0)
                                st.success(f"**Combined Signal:** {combined.get('signal', 'HOLD')} (Confidence: {conf:.0%})")
                                st.caption(combined.get("reason", ""))
                            else:
                                st.info("No clear signal across timeframes.")
                        elif TIERS_AVAILABLE and not has_feature(st.session_state.username, "multi_timeframe"):
                            st.markdown("---")
                            st.caption("🔭 Multi-Timeframe Confirmation — 🔒 Pro feature")

                        st.markdown("---")
                        # ===== CHANGES 2, 3, 4, 5: ML Prediction (Enhanced) =====
                        st.markdown("##### 🧠 ML Prediction (Ensemble)")
                        try:
                            df_ml = df[['close']].copy()
                            df_ml['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi()
                            df_ml['sma_50'] = df['close'].rolling(50).mean()
                            df_ml['sma_200'] = df['close'].rolling(200).mean()

                            # Advanced features (Change 3)
                            macd = ta.trend.MACD(df['close'])
                            df_ml['macd'] = macd.macd()
                            df_ml['macd_signal'] = macd.macd_signal()

                            bb = ta.volatility.BollingerBands(df['close'])
                            df_ml['bb_high'] = bb.bollinger_hband()
                            df_ml['bb_low'] = bb.bollinger_lband()

                            df_ml['atr'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close']).average_true_range()
                            df_ml['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
                            df_ml['return_5d'] = df['close'].pct_change(5)
                            df_ml['return_20d'] = df['close'].pct_change(20)
                            df_ml['volatility'] = df['close'].pct_change().rolling(20).std()

                            df_ml.dropna(inplace=True)
                            df_ml['prediction'] = df_ml['close'].shift(-1)
                            df_ml.dropna(inplace=True)

                            feature_cols = ['close', 'rsi', 'sma_50', 'sma_200', 'macd', 'macd_signal',
                                            'bb_high', 'bb_low', 'atr', 'volume_ratio',
                                            'return_5d', 'return_20d', 'volatility']
                            X = df_ml[feature_cols]
                            y = df_ml['prediction']

                            # Walk-forward validation (Change 4)
                            split_idx = int(len(X) * 0.8)
                            X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
                            y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

                            # Ensemble model (Change 5)
                            models = []
                            predictions_test = []
                            final_predictions = []

                            # Always have Random Forest as baseline
                            rf_model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
                            rf_model.fit(X_train, y_train)
                            models.append(("Random Forest", rf_model))
                            predictions_test.append(rf_model.predict(X_test))
                            final_predictions.append(rf_model.predict(X.iloc[[-1]])[0])

                            # XGBoost (if available)
                            if XGBOOST_AVAILABLE:
                                try:
                                    xgb_model = XGBRegressor(n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42, verbosity=0)
                                    xgb_model.fit(X_train, y_train)
                                    models.append(("XGBoost", xgb_model))
                                    predictions_test.append(xgb_model.predict(X_test))
                                    final_predictions.append(xgb_model.predict(X.iloc[[-1]])[0])
                                except Exception as e:
                                    st.caption(f"XGBoost training error: {str(e)[:50]}")

                            # LightGBM (if available)
                            if LIGHTGBM_AVAILABLE:
                                try:
                                    lgb_model = LGBMRegressor(n_estimators=200, max_depth=6, learning_rate=0.1, random_state=42, verbose=-1)
                                    lgb_model.fit(X_train, y_train)
                                    models.append(("LightGBM", lgb_model))
                                    predictions_test.append(lgb_model.predict(X_test))
                                    final_predictions.append(lgb_model.predict(X.iloc[[-1]])[0])
                                except Exception as e:
                                    st.caption(f"LightGBM training error: {str(e)[:50]}")

                            # Average ensemble predictions
                            avg_test_predictions = np.mean(predictions_test, axis=0)
                            prediction = np.mean(final_predictions)

                            # Calculate score from averaged predictions
                            if len(y_test) > 0:
                                ss_res = np.sum((y_test.values - avg_test_predictions) ** 2)
                                ss_tot = np.sum((y_test.values - np.mean(y_test.values)) ** 2)
                                score = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
                            else:
                                score = 0

                            # Use cleaned data for current price (Change 2 - NaN fix)
                            current_price = float(df_ml['close'].iloc[-1])

                            # Fallback: use price from bucket classification section
                            if np.isnan(current_price) or current_price <= 0:
                                current_price = price

                            # Final fallback: yfinance info
                            if np.isnan(current_price) or current_price <= 0:
                                try:
                                    info2 = stock_data.info or {}
                                    current_price = float(info2.get('currentPrice') or info2.get('regularMarketPrice') or info2.get('previousClose') or 0)
                                except Exception:
                                    current_price = 0

                            diff = prediction - current_price
                            col1, col2 = st.columns(2)
                            if current_price > 0:
                                col1.metric("Current", f"${current_price:.2f}")
                                col2.metric("AI Prediction", f"${prediction:.2f}", f"{diff:+.2f}")
                            else:
                                col1.metric("Current", "N/A")
                                col2.metric("AI Prediction", f"${prediction:.2f}", "N/A")

                            # Show model details
                            model_names = ", ".join([m[0] for m in models])
                            st.caption(f"Ensemble: {model_names} ({len(models)} models, {len(feature_cols)} features)")

                            if score < 0.5:
                                st.warning(f"Model Confidence: {score*100:.1f}% (Low)")
                            else:
                                st.success(f"Model Confidence: {score*100:.1f}%")

                            # Feature importance (from RF)
                            if len(models) > 0:
                                with st.expander("📊 Feature Importance"):
                                    importances = models[0][1].feature_importances_
                                    feat_imp = pd.DataFrame({
                                        'Feature': feature_cols,
                                        'Importance': importances
                                    }).sort_values('Importance', ascending=False)
                                    st.dataframe(feat_imp, use_container_width=True, hide_index=True)

                        except Exception as e:
                            st.error(f"AI Error: {e}")

                        # --- OPENAI NEWS SENTIMENT ---
                        if ai_sentiment_enabled:
                            st.markdown("---")
                            st.markdown("##### 📰 AI News Sentiment (OpenAI)")

                            db = SessionLocal()
                            current_user = db.query(User).filter(User.username == st.session_state.username).first()
                            openai_key = current_user.openai_api_key if current_user else ""
                            db.close()

                            if not openai_key:
                                st.warning("Please add your OpenAI API key in the Settings sidebar to use this feature.")
                            else:
                                try:
                                    news = stock_data.news
                                    news_count = len(news) if news else 0
                                    news_text = ""

                                    if news and news_count > 0:
                                        for item in news[:8]:
                                            content = item.get('content', {})
                                            title = content.get('title') or item.get('title') or 'No Title'
                                            publisher = content.get('provider', {}).get('displayName') or item.get('publisher') or 'Unknown'
                                            summary = content.get('summary') or item.get('summary') or ''
                                            if summary and len(summary) > 10:
                                                summary_text = f" — {summary[:200]}"
                                            else:
                                                summary_text = ""
                                            news_text += f"- {title} ({publisher}){summary_text}\n"

                                    if not news_text:
                                        st.caption("No news headlines found. Using company fundamentals instead...")
                                        try:
                                            info2 = stock_data.info or {}
                                            sector = info2.get('sector', 'Unknown')
                                            industry = info2.get('industry', 'Unknown')
                                            market_cap = info2.get('marketCap', 0)
                                            pe_ratio = info2.get('trailingPE', 0)
                                            div_yield_val = info2.get('dividendYield', 0)
                                            news_text = f"No recent news headlines available for {deep_ticker}.\n\n"
                                            news_text += f"Company context:\n"
                                            news_text += f"- Sector: {sector}, Industry: {industry}\n"
                                            news_text += f"- Market Cap: ${market_cap:,.0f}\n"
                                            news_text += f"- P/E Ratio: {pe_ratio}\n"
                                            if div_yield_val:
                                                news_text += f"- Dividend Yield: {div_yield_val * 100:.2f}%\n"
                                            else:
                                                news_text += "- Dividend Yield: None\n"
                                        except Exception:
                                            news_text = f"No news or company data available for {deep_ticker}."

                                    with st.spinner("OpenAI is reading the news..."):
                                        try:
                                            from openai import OpenAI
                                            client = OpenAI(api_key=openai_key)

                                            if news and news_count > 0:
                                                system_prompt = (
                                                    "You are a professional stock market analyst. "
                                                    "Based on the provided news headlines, give a brief 2-3 sentence analysis "
                                                    "of the overall sentiment for the stock. Focus on what the headlines "
                                                    "SUGGEST about the stock's near-term direction. "
                                                    "End with a sentiment score from -10 (Extremely Bearish) to 10 (Extremely Bullish), "
                                                    "where 0 is Neutral. Format: Sentiment Score: X (Bearish/Neutral/Bullish)"
                                                )
                                                user_prompt = f"Analyze the sentiment for {deep_ticker} based on these recent news headlines:\n\n{news_text}"
                                            else:
                                                system_prompt = (
                                                    "You are a professional stock market analyst. "
                                                    "Based on the limited company data provided, give a brief 2-3 sentence "
                                                    "assessment of the stock's current positioning. "
                                                    "End with a sentiment score from -10 (Extremely Bearish) to 10 (Extremely Bullish), "
                                                    "where 0 is Neutral. Format: Sentiment Score: X (Bearish/Neutral/Bullish) "
                                                    "Note: This assessment is based on limited data, not recent news."
                                                )
                                                user_prompt = f"Assess {deep_ticker} based on this information:\n\n{news_text}"

                                            response = client.chat.completions.create(
                                                model="gpt-4o-mini",
                                                messages=[
                                                    {"role": "system", "content": system_prompt},
                                                    {"role": "user", "content": user_prompt}
                                                ],
                                                temperature=0.3,
                                                max_tokens=200
                                            )

                                            ai_sentiment = response.choices[0].message.content

                                            if news and news_count > 0:
                                                with st.expander(f"📰 Sources ({news_count} headlines)", expanded=False):
                                                    for item in news[:8]:
                                                        content = item.get('content', {})
                                                        title = content.get('title') or item.get('title') or 'No Title'
                                                        publisher = content.get('provider', {}).get('displayName') or item.get('publisher') or 'Unknown'
                                                        pub_date = content.get('pubDate', '')[:10]
                                                        st.write(f"• {title} — *{publisher}* {pub_date}")
                                            else:
                                                st.caption("⚠️ No recent news found. Analysis based on company fundamentals only.")

                                            with st.container(border=True):
                                                st.markdown(ai_sentiment)
                                        except Exception as e:
                                            st.error(f"OpenAI Error: {e}")
                                except Exception as e:
                                    st.error(f"Error fetching data: {e}")
                        else:
                            st.markdown("---")
                            st.info("🔒 **AI News Sentiment** — Upgrade to Pro to unlock OpenAI-powered news analysis.")
                            if st.button("⚡ Learn More About Pro"):
                                st.markdown("Pro includes: AI sentiment analysis, advanced signals, multi-timeframe confirmation, live trading, and more.")

# ==========================================
# TAB 3: AUTO TRADE (Restructured with Sell Everything & Rebalance)
# ==========================================
with tab3:
    engine = st.session_state.trading_engine

    col_refresh1, col_refresh2 = st.columns([3, 1])
    with col_refresh2:
        if st.button("🔄 Refresh Dashboard"):
            st.rerun()

    # --- CONNECTION (Compact) ---
    st.markdown("##### 🔌 Connection")
    with st.container(border=True):
        col_c1, col_c2 = st.columns([3, 1])
        with col_c1:
            if not engine.connected:
                st.warning("Not connected to Alpaca. Enter keys in sidebar and click Connect.")
            else:
                account = engine.get_account_info()
                if "error" not in account:
                    mc1, mc2, mc3, mc4 = st.columns(4)
                    mc1.metric("Portfolio", f"${account['portfolio_value']:,.2f}")
                    mc2.metric("Cash", f"${account['cash']:,.2f}")
                    mc3.metric("Buying Power", f"${account['buying_power']:,.2f}")
                    mc4.metric("Equity", f"${account['equity']:,.2f}")
                else:
                    st.error(f"Account error: {account['error']}")

        with col_c2:
            if st.button("🔌 Connect" if not engine.connected else "🔄 Reconnect", use_container_width=True):
                db = SessionLocal()
                current_user = db.query(User).filter(User.username == st.session_state.username).first()
                api_key = current_user.alpaca_api_key if current_user else ""
                secret_key = current_user.alpaca_secret_key if current_user else ""
                db.close()

                if not api_key or not secret_key:
                    st.error("Please enter your Alpaca API keys in the Settings sidebar.")
                else:
                    with st.spinner("Connecting to Alpaca..."):
                        try:
                            import alpaca_trade_api as tradeapi
                            alpaca_api = tradeapi.REST(api_key, secret_key, base_url='https://paper-api.alpaca.markets', api_version='v2')
                            success = engine.connect(alpaca_api)
                            if success:
                                st.success("Connected to Alpaca Paper Trading!")
                            else:
                                st.error(f"Connection failed: {engine.status_message}")
                        except Exception as e:
                            st.error(f"Error initializing Alpaca: {e}")
                    st.rerun()

    # --- BOT CONTROL ---
    st.markdown("##### 🎮 Bot Control")
    with st.container(border=True):
        col_ctrl1, col_ctrl2 = st.columns(2)

        with col_ctrl1:
            if engine.running:
                if st.button("⏹️ Stop Bot", type="primary", use_container_width=True):
                    engine.stop()
                    st.success("Bot stopped.")
                    st.rerun()
            else:
                if st.session_state.confirm_start_bot:
                    st.warning("⚠️ Are you sure you want to start auto-trading? The bot will execute trades automatically based on your settings.")
                    col_yes, col_cancel = st.columns(2)
                    with col_yes:
                        if st.button("✅ Yes, Start Bot", type="primary", use_container_width=True):
                            st.session_state.confirm_start_bot = False
                            engine.start()
                            market = engine.is_market_open()
                            if not market.get("is_open", True):
                                st.warning("Market is closed. Bot will trade when it opens.")
                            else:
                                st.success("Bot started!")
                            st.rerun()
                    with col_cancel:
                        if st.button("❌ Cancel", use_container_width=True):
                            st.session_state.confirm_start_bot = False
                            st.rerun()
                else:
                    if st.button("▶️ Start Bot", type="primary", use_container_width=True):
                        if not engine.connected:
                            st.error("Connect to Alpaca first!")
                        else:
                            st.session_state.confirm_start_bot = True
                            st.rerun()

        with col_ctrl2:
            if st.button("🔍 Scan Once", use_container_width=True):
                if not engine.connected:
                    st.error("Connect to Alpaca first!")
                else:
                    with st.spinner("Scanning for signals..."):
                        signals = engine.scan_signals()
                        if signals:
                            buy_count = sum(1 for s in signals if s["signal"] == "BUY")
                            sell_count = sum(1 for s in signals if s["signal"] == "SELL")
                            st.success(f"Found {len(signals)} signals: 🟢 {buy_count} buys | 🔴 {sell_count} sells")
                            st.caption("See ⚡ Active Signals below for details.")
                        else:
                            st.info("No signals found this scan.")

    status = engine.get_status()
    st.caption(f"Status: {status['status_message']} | Cycles: {status['cycle_count']} | P&L: ${status['daily_pnl']:+,.2f}")

    # --- BUCKET OVERVIEW ---
    st.markdown("##### 💰 Bucket Overview")
    bucket_ov = engine.get_bucket_overview()

    all_positions = engine.get_positions() if engine.connected else []
    div_symbols = [p["symbol"] for p in all_positions if engine.assign_bucket(p["symbol"]) == "dividend"]
    gro_symbols = [p["symbol"] for p in all_positions if engine.assign_bucket(p["symbol"]) == "growth"]
    pen_symbols = [p["symbol"] for p in all_positions if engine.assign_bucket(p["symbol"]) == "penny"]

    div_label = f"{bucket_ov['dividend']['positions']} positions"
    if div_symbols: div_label += f" ({', '.join(div_symbols[:5])})"
    gro_label = f"{bucket_ov['growth']['positions']} positions"
    if gro_symbols: gro_label += f" ({', '.join(gro_symbols[:5])})"
    pen_label = f"{bucket_ov['penny']['positions']} positions"
    if pen_symbols: pen_label += f" ({', '.join(pen_symbols[:5])})"

    b1, b2, b3, b4, b5 = st.columns(5)
    with b1:
        st.metric("🟢 Dividend Pot", f"${bucket_ov['dividend']['value']:,.2f}", div_label)
    with b2:
        st.metric("🔵 Growth Pot", f"${bucket_ov['growth']['value']:,.2f}", gro_label)
    with b3:
        st.metric("🔴 Penny Pot", f"${bucket_ov['penny']['value']:,.2f}", pen_label)
    with b4:
        st.metric("🟡 Withdrawal", f"${bucket_ov['withdrawal']['available']:,.2f}", "🔒 LOCKED")
    with b5:
        profit_color = "🟢" if bucket_ov['total_profit'] >= 0 else "🔴"
        st.metric(f"{profit_color} Total Profit", f"${bucket_ov['total_profit']:,.2f}", f"{bucket_ov.get('profit_pct', 0):.1f}% from ${bucket_ov['original_capital']:,.0f}")

    # ==========================================
    # SELL EVERYTHING & REBALANCE (NEW)
    # ==========================================
    st.markdown("---")
    st.markdown("##### 🛑 Sell Everything & Rebalance")
    st.caption("Sell all positions and move proceeds to the 🟡 Withdrawal Pot (locked from trading). Then redistribute back to buckets when ready.")

    col_sell, col_rebalance = st.columns(2)

    with col_sell:
        if st.button("🛑 Sell Everything", type="primary", use_container_width=True):
            if not engine.connected:
                st.error("Connect to Alpaca first!")
            else:
                st.session_state.confirm_sell_everything = True
                st.rerun()

        if st.session_state.confirm_sell_everything:
            st.warning("⚠️ **This will sell ALL open positions and move proceeds to the Withdrawal Pot (🔒 locked from trading).**")
            st.warning("The bot will NOT be able to trade with this money until you manually move it back to a trading bucket.")
            positions_count = len(all_positions)
            total_value = sum(float(p.get("market_value", 0)) for p in all_positions)
            st.info(f"You have **{positions_count} positions** worth **${total_value:,.2f}**.")
            col_confirm_se, col_cancel_se = st.columns(2)
            with col_confirm_se:
                if st.button("⚠️ CONFIRM: Sell All Positions", type="primary", use_container_width=True):
                    with st.spinner("Selling all positions..."):
                        result = engine.sell_everything()
                        st.session_state.confirm_sell_everything = False
                        if result["status"] == "sold":
                            st.success(result["message"])
                            for pos in result.get("positions_sold", []):
                                bucket_icon = BUCKET_ICONS.get(pos.get("bucket", "growth"), "⚪")
                                pl_str = f" ({pos.get('pl_pct', 0):+.1f}%)" if pos.get("pl_pct", 0) != 0 else ""
                                st.write(f"  {bucket_icon} Sold **{pos['symbol']}**: ${pos['market_value']:,.2f}{pl_str}")
                            st.rerun()
                        elif result["status"] == "no_positions":
                            st.info(result["message"])
                            st.rerun()
                        else:
                            st.error(result.get("message", "Unknown error"))
                            st.rerun()
            with col_cancel_se:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state.confirm_sell_everything = False
                    st.rerun()

    with col_rebalance:
        if st.button("🔄 Rebalance (Sell All → Redistribute)", use_container_width=True):
            if not engine.connected:
                st.error("Connect to Alpaca first!")
            else:
                st.session_state.confirm_rebalance = True
                st.rerun()

        if st.session_state.confirm_rebalance:
            st.warning("⚠️ **This will sell ALL positions, move proceeds to the Withdrawal Pot, then redistribute across your 3 trading buckets based on your allocation percentages.**")
            div_pct = int(engine.settings.get("dividend_pct", 0.35) * 100)
            gro_pct = int(engine.settings.get("growth_pct", 0.35) * 100)
            pen_pct = int(engine.settings.get("penny_pct", 0.30) * 100)
            st.info(f"Allocation: 🟢 Dividend {div_pct}% | 🔵 Growth {gro_pct}% | 🔴 Penny {pen_pct}%")
            col_confirm_rb, col_cancel_rb = st.columns(2)
            with col_confirm_rb:
                if st.button("⚠️ CONFIRM: Rebalance", type="primary", use_container_width=True):
                    with st.spinner("Selling all positions and redistributing..."):
                        sell_result = engine.sell_everything()
                        if sell_result["status"] in ["sold", "no_positions"]:
                            redis_result = engine.redistribute_from_withdrawal()
                            st.session_state.confirm_rebalance = False
                            if redis_result["status"] == "success":
                                st.success(redis_result["message"])
                                st.rerun()
                            elif redis_result["status"] == "error":
                                if "No money" in redis_result.get("message", ""):
                                    if sell_result["status"] == "no_positions":
                                        st.info("No positions to sell and no money in Withdrawal Pot to redistribute.")
                                    else:
                                        st.warning("Sold positions but redistribution failed. Money is safe in Withdrawal Pot.")
                                        st.rerun()
                                else:
                                    st.error(redis_result.get("message", "Redistribution error"))
                                    st.rerun()
                            else:
                                st.info(redis_result.get("message", "No money to redistribute."))
                                st.rerun()
                        else:
                            st.session_state.confirm_rebalance = False
                            st.error(sell_result.get("message", "Error selling positions"))
                            st.rerun()
            with col_cancel_rb:
                if st.button("❌ Cancel Rebalance", use_container_width=True):
                    st.session_state.confirm_rebalance = False
                    st.rerun()

    # ==========================================
    # MOVE FROM WITHDRAWAL POT (NEW)
    # ==========================================
    st.markdown("---")
    st.markdown("##### 💸 Move from Withdrawal Pot")
    withdrawal_available = bucket_ov["withdrawal"]["available"]

    if withdrawal_available > 0:
        # Round to 2 decimal places to avoid StreamlitValueAboveMaxError
        withdrawal_rounded = round(float(withdrawal_available), 2)

        st.success(f"🟡 Available in Withdrawal Pot: **${withdrawal_rounded:,.2f}** (🔒 Locked from trading)")

        move_col1, move_col2 = st.columns([1, 3])
        with move_col1:
            move_amount = st.number_input(
                "Amount to move ($)",
                min_value=1.0,
                max_value=withdrawal_rounded,
                value=withdrawal_rounded,
                step=100.0,
                key="move_withdrawal_amount"
            )

        with move_col2:
            st.caption("Move money from the Withdrawal Pot back into a trading bucket. The bot will then be able to use it for trading.")
            btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)

            with btn_col1:
                if st.button("🟢→ Dividend", use_container_width=True, help=f"Move ${move_amount:,.2f} to Dividend Pot"):
                    result = engine.move_from_withdrawal(move_amount, "dividend")
                    if result["status"] == "success":
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["message"])

            with btn_col2:
                if st.button("🔵→ Growth", use_container_width=True, help=f"Move ${move_amount:,.2f} to Growth Pot"):
                    result = engine.move_from_withdrawal(move_amount, "growth")
                    if result["status"] == "success":
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["message"])

            with btn_col3:
                if st.button("🔴→ Penny", use_container_width=True, help=f"Move ${move_amount:,.2f} to Penny Pot"):
                    result = engine.move_from_withdrawal(move_amount, "penny")
                    if result["status"] == "success":
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["message"])

            with btn_col4:
                if st.button("🔄 Redistribute All", use_container_width=True, help=f"Distribute entire Withdrawal Pot across all 3 buckets based on your allocation %"):
                    result = engine.redistribute_from_withdrawal()
                    if result["status"] == "success":
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["message"])
    else:
        st.info("🟡 Withdrawal Pot is empty. Use **Sell Everything** or **Extract Profits** to add money to the Withdrawal Pot.")

    # --- ACCOUNT & ALLOCATION ---
    st.markdown("---")
    st.markdown("##### 💰 Account & Allocation")

    account = engine.get_account_info()
    if "error" not in account:
        col_a1, col_a2, col_a3, col_a4 = st.columns(4)
        with col_a1:
            st.metric("Portfolio", f"${account['portfolio_value']:,.2f}")
        with col_a2:
            st.metric("Cash", f"${account['cash']:,.2f}")
        with col_a3:
            st.metric("Buying Power", f"${account['buying_power']:,.2f}")
        with col_a4:
            st.metric("Equity", f"${account['equity']:,.2f}")
    else:
        st.warning("Connect to Alpaca to see account info.")

    # Display current allocation
    div_pct_val = int(engine.settings.get("dividend_pct", 0.35) * 100)
    gro_pct_val = int(engine.settings.get("growth_pct", 0.35) * 100)
    pen_pct_val = int(engine.settings.get("penny_pct", 0.30) * 100)
    total_pct = div_pct_val + gro_pct_val + pen_pct_val

    if total_pct != 100:
        st.warning(f"⚠️ Allocations add up to **{total_pct}%** (should be 100%). Adjust in bucket settings below.")

    # Allocation progress bars
    col_bar1, col_bar2, col_bar3 = st.columns(3)
    with col_bar1:
        st.progress(div_pct_val / 100)
        st.caption(f"🟢 Dividend: **{div_pct_val}%**")
    with col_bar2:
        st.progress(gro_pct_val / 100)
        st.caption(f"🔵 Growth: **{gro_pct_val}%**")
    with col_bar3:
        st.progress(pen_pct_val / 100)
        st.caption(f"🔴 Penny: **{pen_pct_val}%**")

    if "error" not in account:
        total_equity = float(account.get("equity", 0))
        st.caption(f"💰 **${total_equity:,.2f}** total → 🟢 ${total_equity * div_pct_val / 100:,.2f} Dividend | 🔵 ${total_equity * gro_pct_val / 100:,.2f} Growth | 🔴 ${total_equity * pen_pct_val / 100:,.2f} Penny")

    # --- PROFIT EXTRACTION ---
    st.markdown("---")
    st.markdown("##### ⚡ Profit Extraction")
    with st.container(border=True):
            # --- PROFIT SKIMMING (NEW) ---
        st.markdown("##### 🛡️ Profit Skimming (Auto-Lock)")
        skim_pct_current = int(engine.settings.get("profit_skim_pct", 1.0) * 100)
        profit_skim = st.slider(
            "Profit Skimming %", 
            min_value=0, max_value=100, value=skim_pct_current, step=5,
            help="When the bot sells a profitable stock, this % of the PROFIT goes directly to your 🟡 Withdrawal Pot (locked from trading). The original buy price returns to the trading bucket. 100% = Lock all profits safely."
        )
        engine.settings["profit_skim_pct"] = profit_skim / 100
        
        if profit_skim == 100:
            st.success("🛡️ 100% Skimming: ALL profits are locked in your Withdrawal Pot. The bot will only ever trade with its original capital.")
        elif profit_skim == 0:
            st.warning("⚠️ 0% Skimming: All profits are reinvested. Higher potential gains, but higher risk of giving profits back to the market.")
        else:
            st.info(f"🛡️ {profit_skim}% Skimming: {profit_skim}% of profits go to Withdrawal Pot, {100-profit_skim}% gets reinvested.")
        st.markdown("---")    
        use_pct = st.checkbox("Use % threshold instead of $ amount", value=engine.settings.get("use_pct_threshold", False))
        if use_pct:
            threshold_pct = st.number_input("Profit Threshold (%)", min_value=5.0, max_value=100.0, value=float(engine.settings.get("profit_threshold_pct", 0.20) * 100), step=1.0, format="%.1f")
            engine.settings["profit_threshold_pct"] = threshold_pct / 100
        else:
            threshold_amount = st.number_input("Profit Threshold ($)", value=float(engine.settings.get("profit_threshold_amount", 20000)), min_value=0.0, step=1000.0, format="%.2f")
            engine.settings["profit_threshold_amount"] = threshold_amount

        engine.settings["use_pct_threshold"] = use_pct
        auto_extract = st.checkbox("Auto-extract when threshold hit", value=engine.settings.get("auto_extract_profits", True))
        engine.settings["auto_extract_profits"] = auto_extract
        engine.save_settings()

        if st.button("⚡ Extract Profits Now", type="primary", use_container_width=True):
            with st.spinner("Extracting profits..."):
                result = engine.extract_profits()
                if result["status"] == "extracted":
                    st.success(f"✅ {result['message']}")
                    st.rerun()
                elif result["status"] == "below_threshold":
                    st.warning(result["message"])

    # --- WATCHLIST ---
    st.markdown("---")
    st.markdown("##### 📋 Watchlist")
    wl_mode = st.radio("Choose:", ["Manual (type yourself)", "Auto (Alpaca Universe - scan best stocks)"], index=1 if engine.settings.get("watchlist_auto") else 0, horizontal=True)

    if "Auto" in wl_mode:
        col_auto1, col_auto2 = st.columns(2)
        with col_auto1:
            top_n = st.slider("How many stocks to scan", 20, 300, engine.settings.get("watchlist_auto_count", 100))
            engine.settings["watchlist_auto_count"] = top_n
        with col_auto2:
            min_p = st.number_input("Min Price $", value=5.0, step=1.0)
            max_p = st.number_input("Max Price $", value=500.0, step=10.0)

        if st.button("🔄 Build Auto Watchlist"):
            if not engine.connected:
                st.error("Connect to Alpaca first.")
            else:
                with st.spinner(f"Scanning Alpaca universe for top {top_n} stocks..."):
                    wl = engine.auto_build_watchlist(top_n=top_n, min_price=min_p, max_price=max_p)
                    st.success(f"✅ Built watchlist: {len(wl)} stocks")
    else:
        watchlist_str = ", ".join(engine.settings["watchlist"])
        new_watchlist = st.text_area("Watchlist (comma separated)", value=watchlist_str, height=68)
        if new_watchlist != watchlist_str:
            engine.settings["watchlist"] = [t.strip().upper() for t in new_watchlist.split(",") if t.strip()]

    # --- TRADING SETTINGS ---
    st.markdown("---")
    st.markdown("##### ⚙️ Trading Settings (Risk Management)")
    
    if st.button("🔒 Reset to Safe Defaults", type="primary"):
        engine.reset_settings()
        st.success("Settings reset to safe defaults!")
        st.rerun()

        # === GLOBAL SETTINGS (always visible) ===
        st.markdown("**🌐 Global Settings**")
        st.caption("🟢 = Safe | 🟡 = Moderate | 🔴 = Risky. Hover over sliders for explanations.")

        # --- TIER LOCK LOGIC ---
        is_locked = user_tier == "starter"
        if is_locked:
            st.warning("🔒 **Starter Plan:** Risk settings are locked to safe defaults. Upgrade to Pro to unlock advanced risk controls.")
        
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            # MAX POSITIONS (with Tier Limits preserved)
            tier_limits = get_tier_limits(st.session_state.username) if TIERS_AVAILABLE else TIER_FEATURES.get("starter", {})
            max_pos_limit = tier_limits.get("max_positions", 10)
            max_pos = st.slider(
                "📊 Max Positions", 1, max_pos_limit, engine.settings["max_positions"], 
                help=f"Maximum number of stocks you can hold at once. Your tier allows up to {max_pos_limit}.",
                disabled=is_locked
            )
            engine.settings["max_positions"] = max_pos
            if max_pos > 20:
                st.error("🔴 **Risk:** More than 20 positions increases exposure & margin risk significantly.")
            elif max_pos > 10:
                st.warning("🟡 **Moderate:** Holding 11-20 positions requires more capital.")
            else:
                st.success("🟢 **Safe:** Holding 10 or fewer positions.")

            # MAX POSITION %
            max_pos_pct = st.slider(
                "💰 Max Position %", 2, 25, int(engine.settings["max_position_pct"] * 100), step=1, format="%d%%",
                help="Max % of your total portfolio value put into a single stock. 8% is safe.",
                disabled=is_locked
            )
            engine.settings["max_position_pct"] = max_pos_pct / 100
            if max_pos_pct > 15:
                st.error("🔴 **Risk:** Concentrated positions (>15%) can cause large losses if the stock drops.")
            elif max_pos_pct > 8:
                st.warning("🟡 **Moderate:** Positions 9-15% are concentrated. One bad trade hurts more.")
            else:
                st.success("🟢 **Safe:** Positions 8% or less protect your capital.")

            # DAILY LOSS LIMIT %
            daily_loss = st.slider(
                "🛑 Daily Loss Limit %", 1, 10, int(engine.settings["daily_loss_limit_pct"] * 100), step=1, format="%d%%",
                help="Stops trading for the day if your daily losses exceed this %. 3% is recommended.",
                disabled=is_locked
            )
            engine.settings["daily_loss_limit_pct"] = daily_loss / 100
            if daily_loss > 5:
                st.error("🔴 **Risk:** Higher loss limits (>5%) risk larger drawdowns and can wipe out weeks of gains.")
            elif daily_loss > 3:
                st.warning("🟡 **Moderate:** A 4-5% daily loss is tough to recover from.")
            else:
                st.success("🟢 **Safe:** A 3% daily loss limit protects your capital.")

        with col_g2:
            # STOP LOSS %
            stop_loss = st.slider(
                "🛡️ Stop Loss %", 1, 20, int(engine.settings["stop_loss_pct"] * 100), step=1, format="%d%%",
                help="Auto-sells a stock if it drops this %. Tight stops (<3%) get triggered by normal volatility.",
                disabled=is_locked
            )
            engine.settings["stop_loss_pct"] = stop_loss / 100
            if stop_loss < 3:
                st.error("🔴 **Risk:** Tight stops (<3%) get triggered by normal market volatility, causing frequent stop-outs.")
            elif stop_loss < 5:
                st.warning("🟡 **Moderate:** 3-4% stops are tight. You may get sold out on normal dips.")
            else:
                st.success("🟢 **Safe:** 5%+ stops give stocks room to breathe.")

            # TAKE PROFIT %
            take_profit = st.slider(
                "🎯 Take Profit %", 5, 50, int(engine.settings["take_profit_pct"] * 100), step=1, format="%d%%",
                help="Auto-sells a stock when it reaches this % profit. Higher targets may never be reached.",
                disabled=is_locked
            )
            engine.settings["take_profit_pct"] = take_profit / 100
            if take_profit > 20:
                st.error("🔴 **Risk:** Very high targets (>20%) may never be reached, causing you to hold losers longer.")
            elif take_profit > 10:
                st.warning("🟡 **Moderate:** 11-20% targets take longer to hit. Greed can be risky.")
            else:
                st.success("🟢 **Safe:** 10% targets lock in profits reliably.")

            # MIN CONFIDENCE
            min_conf = st.slider(
                "🎯 Min Confidence", 0.05, 0.95, engine.settings["min_confidence"], step=0.05, format="%.2f",
                help="Minimum signal confidence required to buy. Lower % = more trades, but more false signals.",
                disabled=is_locked
            )
            engine.settings["min_confidence"] = min_conf
            if min_conf < 0.15:
                st.error("🔴 **Risk:** Lower than 15% confidence means buying on very weak signals (essentially guessing).")
            elif min_conf < 0.25:
                st.warning("🟡 **Moderate:** 15-24% confidence accepts weaker signals. More trades, less accuracy.")
            else:
                st.success("🟢 **Safe:** 25%+ ensures only decent signals trigger buys.")

        # Row for remaining global settings
        st.markdown("---")
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            engine.settings["max_same_sector"] = st.slider(
                "🏢 Max Same Sector", 1, 5, engine.settings.get("max_same_sector", 3), 
                help="Limits how many stocks from the same industry you can hold.",
                disabled=is_locked
            )
        with col_r2:
            min_rvol = st.slider(
                "💥 Min RVOL", 0.0, 5.0, engine.settings.get("min_rvol", 1.5), step=0.1, format="%.1f",
                help="Minimum volume spike required for a buy signal. Lower = more trades, but less reliable.",
                disabled=is_locked
            )
            engine.settings["min_rvol"] = min_rvol
            if min_rvol < 1.0:
                st.error("🔴 Low volume signals are unreliable.")
            elif min_rvol < 1.5:
                st.warning("🟡 Moderate volume backing.")
            else:
                st.success("🟢 Strong volume backing.")
        with col_r3:
            scan_interval = st.slider(
                "⏱️ Scan Interval (min)", 1, 30, engine.settings["scan_interval_min"], 
                help="Minutes between scans. Lower = faster but uses more API calls.",
                disabled=is_locked
            )
            engine.settings["scan_interval_min"] = scan_interval

    st.markdown("---")

    # === BUCKET-SPECIFIC SETTINGS (expandable) ===
    with st.expander("🔴 Penny Stock Settings", expanded=False):
        penny_alloc = st.slider("💰 Capital Allocation %", 0, 100, int(engine.settings.get("penny_pct", 0.30) * 100), step=1, format="%d%%", key="penny_alloc_slider", help="What percentage of your capital goes to penny stocks. Set to 0% to disable penny trading.")
        engine.settings["penny_pct"] = penny_alloc / 100

        st.caption("Higher risk, tighter stops, faster profits. Stocks under ${:.0f}.".format(engine.settings.get("penny_price_threshold", 5.0)))
        penny = engine.settings.get("penny_settings", {})
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            penny_sl = st.slider("🛑 Stop Loss %", 1, 20, int(penny.get("stop_loss_pct", 0.03) * 100), step=1, format="%d%%", key="penny_sl")
            penny["stop_loss_pct"] = penny_sl / 100
            penny_ts = st.slider("📈 Trailing Stop %", 1, 10, int(penny.get("trailing_stop_pct", 0.02) * 100), step=1, format="%d%%", key="penny_ts")
            penny["trailing_stop_pct"] = penny_ts / 100
        with col_p2:
            penny_tp = st.slider("💰 Take Profit %", 5, 50, int(penny.get("take_profit_pct", 0.08) * 100), step=1, format="%d%%", key="penny_tp")
            penny["take_profit_pct"] = penny_tp / 100
            penny_mp = st.slider("📊 Max Position %", 2, 20, int(penny.get("max_position_pct", 0.04) * 100), step=1, format="%d%%", key="penny_mp", help="Max % of portfolio per penny trade")
            penny["max_position_pct"] = penny_mp / 100
        with col_p3:
            penny_rsi_o = st.slider("📉 RSI Oversold", 15, 45, penny.get("rsi_oversold", 25), key="penny_rsi_o", help="Buy signal when RSI drops below this")
            penny["rsi_oversold"] = penny_rsi_o
            penny_rsi_ob = st.slider("📈 RSI Overbought", 55, 90, penny.get("rsi_overbought", 60), key="penny_rsi_ob", help="Sell signal when RSI goes above this")
            penny["rsi_overbought"] = penny_rsi_ob
            penny_conf = st.slider("🎯 Min Confidence", 0.10, 0.95, penny.get("min_confidence", 0.30), step=0.05, format="%.2f", key="penny_conf")
            penny["min_confidence"] = penny_conf
            penny["penny_price_threshold"] = st.slider("💲 Penny Price Threshold $", 1.0, 20.0, float(penny.get("penny_price_threshold", 5.0)), step=0.5, format="$%.1f", key="penny_price_thresh", help="Stocks priced below this are classified as Penny")
        engine.settings["penny_settings"] = penny

    with st.expander("🔵 Growth Stock Settings", expanded=False):
        growth_alloc = st.slider("💰 Capital Allocation %", 0, 100, int(engine.settings.get("growth_pct", 0.35) * 100), step=1, format="%d%%", key="growth_alloc_slider", help="What percentage of your capital goes to growth stocks. Set to 0% to disable growth trading.")
        engine.settings["growth_pct"] = growth_alloc / 100

        st.caption("Medium risk, balanced stops and targets. Most large-cap stocks.")
        growth = engine.settings.get("growth_settings", {})
        col_gr1, col_gr2, col_gr3 = st.columns(3)
        with col_gr1:
            growth_sl = st.slider("🛑 Stop Loss %", 1, 20, int(growth.get("stop_loss_pct", 0.06) * 100), step=1, format="%d%%", key="growth_sl")
            growth["stop_loss_pct"] = growth_sl / 100
            growth_ts = st.slider("📈 Trailing Stop %", 1, 10, int(growth.get("trailing_stop_pct", 0.04) * 100), step=1, format="%d%%", key="growth_ts")
            growth["trailing_stop_pct"] = growth_ts / 100
        with col_gr2:
            growth_tp = st.slider("💰 Take Profit %", 5, 50, int(growth.get("take_profit_pct", 0.12) * 100), step=1, format="%d%%", key="growth_tp")
            growth["take_profit_pct"] = growth_tp / 100
            growth_mp = st.slider("📊 Max Position %", 2, 20, int(growth.get("max_position_pct", 0.08) * 100), step=1, format="%d%%", key="growth_mp", help="Max % of portfolio per growth trade")
            growth["max_position_pct"] = growth_mp / 100
        with col_gr3:
            growth_rsi_o = st.slider("📉 RSI Oversold", 15, 45, growth.get("rsi_oversold", 30), key="growth_rsi_o", help="Buy signal when RSI drops below this")
            growth["rsi_oversold"] = growth_rsi_o
            growth_rsi_ob = st.slider("📈 RSI Overbought", 55, 90, growth.get("rsi_overbought", 65), key="growth_rsi_ob", help="Sell signal when RSI goes above this")
            growth["rsi_overbought"] = growth_rsi_ob
            growth_conf = st.slider("🎯 Min Confidence", 0.10, 0.95, growth.get("min_confidence", 0.25), step=0.05, format="%.2f", key="growth_conf")
            growth["min_confidence"] = growth_conf
        engine.settings["growth_settings"] = growth

    with st.expander("🟢 Dividend Stock Settings", expanded=False):
        dividend_alloc = st.slider("💰 Capital Allocation %", 0, 100, int(engine.settings.get("dividend_pct", 0.35) * 100), step=1, format="%d%%", key="dividend_alloc_slider", help="What percentage of your capital goes to dividend stocks. Set to 0% to disable dividend trading.")
        engine.settings["dividend_pct"] = dividend_alloc / 100

        st.caption("Lower risk, wider stops, longer holds. Dividend-paying stocks.")
        dividend = engine.settings.get("dividend_settings", {})
        col_d1, col_d2, col_d3 = st.columns(3)
        with col_d1:
            dividend_sl = st.slider("🛑 Stop Loss %", 1, 20, int(dividend.get("stop_loss_pct", 0.08) * 100), step=1, format="%d%%", key="dividend_sl")
            dividend["stop_loss_pct"] = dividend_sl / 100
            dividend_ts = st.slider("📈 Trailing Stop %", 1, 10, int(dividend.get("trailing_stop_pct", 0.05) * 100), step=1, format="%d%%", key="dividend_ts")
            dividend["trailing_stop_pct"] = dividend_ts / 100
        with col_d2:
            dividend_tp = st.slider("💰 Take Profit %", 5, 50, int(dividend.get("take_profit_pct", 0.15) * 100), step=1, format="%d%%", key="dividend_tp")
            dividend["take_profit_pct"] = dividend_tp / 100
            dividend_mp = st.slider("📊 Max Position %", 2, 20, int(dividend.get("max_position_pct", 0.08) * 100), step=1, format="%d%%", key="dividend_mp", help="Max % of portfolio per dividend trade")
            dividend["max_position_pct"] = dividend_mp / 100
        with col_d3:
            dividend_rsi_o = st.slider("📉 RSI Oversold", 15, 45, dividend.get("rsi_oversold", 35), key="dividend_rsi_o", help="Buy signal when RSI drops below this")
            dividend["rsi_oversold"] = dividend_rsi_o
            dividend_rsi_ob = st.slider("📈 RSI Overbought", 55, 90, dividend.get("rsi_overbought", 70), key="dividend_rsi_ob", help="Sell signal when RSI goes above this")
            dividend["rsi_overbought"] = dividend_rsi_ob
            dividend_conf = st.slider("🎯 Min Confidence", 0.10, 0.95, dividend.get("min_confidence", 0.20), step=0.05, format="%.2f", key="dividend_conf")
            dividend["min_confidence"] = dividend_conf
            dividend["min_dividend_yield"] = st.slider("💰 Min Dividend Yield %", 0.0, 15.0, float(dividend.get("min_dividend_yield", 0.03) * 100), step=0.5, format="%.1f%%", key="div_min_yield", help="Stocks with dividend yield above this are classified as Dividend") / 100
        engine.settings["dividend_settings"] = dividend

    with st.expander("🔬 Advanced Signals", expanded=False):
        st.caption("MACD, Bollinger, VIX filter, ATR position sizing.")

        # Tier check for advanced signals
        if TIERS_AVAILABLE and not has_feature(st.session_state.username, "advanced_signals"):
            st.warning("🔒 **Advanced Signals require Pro or Fund tier.** Upgrade to unlock Bollinger Bands, MA Crossover, and VIX Filter.")
            use_advanced = st.checkbox("Enable Advanced Signals", value=False, key="use_advanced_signals_expander", disabled=True)
            st.caption("Advanced signals include MACD crossovers, Bollinger Band touches, and MA crossover patterns.")
        else:
            use_advanced = st.checkbox("Enable Advanced Signals", value=engine.settings.get("use_advanced_signals", True), key="use_advanced_signals_expander")
            engine.settings["use_advanced_signals"] = use_advanced

        use_vix = st.checkbox("🛡️ VIX Filter (Block buys when VIX > 28)", value=engine.settings.get("use_vix_filter", True), key="vix_filter_exp")
        engine.settings["use_vix_filter"] = use_vix

        use_atr = st.checkbox("📐 ATR Position Sizing", value=engine.settings.get("use_atr_position_sizing", True), key="atr_exp")
        engine.settings["use_atr_position_sizing"] = use_atr

        # Tier check for multi-timeframe
        if TIERS_AVAILABLE and not has_feature(st.session_state.username, "multi_timeframe"):
            st.warning("🔭 Multi-Timeframe Confirmation — 🔒 Pro feature")
            use_multi = False
        else:
            use_multi = st.checkbox("🔭 Multi-Timeframe Confirmation", value=engine.settings.get("use_multi_timeframe", False), key="multi_timeframe_exp")

        engine.settings["use_multi_timeframe"] = use_multi

        engine.save_settings()

    # --- CURRENT POSITIONS ---
    st.markdown("---")
    st.markdown("##### 📋 Current Positions")
    if engine.connected:
        positions = engine.get_positions()
        if positions:
            pos_data = []
            for p in positions:
                pl_color = "🟢" if float(p["unrealized_plpc"]) > 0 else "🔴"
                bucket = p.get("bucket") or engine.assign_bucket(p["symbol"]) or "penny"
                bucket_icon = BUCKET_ICONS.get(bucket, "⚪")
                div_icon = "💎" if p["symbol"] in DIVIDEND_STOCKS else ""

                pos_data.append({
                    "Symbol": f"{bucket_icon}{div_icon} {p['symbol']}",
                    "Bucket": bucket.title(), "Qty": p["qty"], "Entry": f"${p['avg_entry_price']:.2f}",
                    "Current": f"${p['current_price']:.2f}", "Value": f"${p['market_value']:,.2f}",
                    "P&L": f"{pl_color} ${p['unrealized_pl']:+,.2f} ({p['unrealized_plpc']:+.2%})",
                })
            st.dataframe(pos_data, use_container_width=True)
        else:
            st.info("No open positions.")
    else:
        st.info("Connect to Alpaca to see positions.")

    # --- ACTIVE SIGNALS ---
    st.markdown("---")
    st.markdown("##### ⚡ Active Signals")
    if engine.signals_found:
        sig_data = []
        for s in engine.signals_found:
            icon = "🟢" if s["signal"] == "BUY" else "🔴"
            bucket = s.get("bucket") or engine.assign_bucket(s["symbol"]) or "penny"
            bucket_icon = BUCKET_ICONS.get(bucket, "⚪")
            sig_data.append({
                "Signal": f"{icon} {s['signal']}", "Symbol": f"{bucket_icon} {s['symbol']}",
                "Bucket": bucket.title(), "Price": f"${s['price']:.2f}",
                "RSI": s["rsi"], "RVOL": s["rvol"], "Confidence": f"{s['confidence']:.0%}", "Reason": s["reason"],
            })
        st.dataframe(sig_data, use_container_width=True)
    else:
        st.info("No active signals.")

    # --- TRADE LOG ---
    st.markdown("---")
    st.markdown("##### 📜 Trade Log")
    if engine.trade_log:
        recent_trades = engine.trade_log[-20:]
        trade_data = []
        for t in reversed(recent_trades):
            icon = "🟢" if t.get("side") == "buy" else "🔴" if t.get("side") == "sell" else "🔵"
            bucket = t.get("bucket") or engine.assign_bucket(t.get("symbol", "")) or "penny"
            if bucket == "long_term": bucket = "dividend"
            bucket_icon = BUCKET_ICONS.get(bucket, "⚪")
            trade_data.append({
                "Time": t.get("timestamp", "")[:19],
                "Symbol": f"{bucket_icon} {t.get('symbol', '')}",
                "Action": f"{icon} {t.get('side', t.get('action', '')).title()}",
                "Qty": t.get("qty", ""),
                "Price": f"${t.get('price', 0):.2f}" if t.get("price") else "",
                "Bucket": bucket.title(),
                "Confidence": f"{(t.get('confidence') or 0):.0%}",
                "Reason": t.get("reason", "")[:50],
            })
        st.dataframe(trade_data, use_container_width=True)
    else:
        st.info("No trades yet.")

    st.caption("QuantPro Terminal — Automated trading software. Not a financial advisor. Trading involves risk.")

    # --- BUCKET DEBUG (in expander) ---
    with st.expander("🔍 Bucket Debug Tool", expanded=False):
        debug_symbol = st.text_input("Enter symbol to debug bucket classification", value="KO", key="debug_bucket_symbol")
        if st.button("🔍 Debug Bucket", key="debug_bucket_btn"):
            result = engine.debug_bucket(debug_symbol)
            st.json(result)
            bucket_icon = BUCKET_ICONS.get(result["final_bucket"], "⚪")
            st.success(f"**{debug_symbol}** classified as: {bucket_icon} **{result['final_bucket'].title()}**")

# ==========================================
# TAB 4: PORTFOLIO (Combined Performance + Profile)
# ==========================================
with tab4:
    st.markdown("### 📊 Portfolio & Performance")
    st.caption("Your complete portfolio overview, performance metrics, trade history, and exports — all in one place.")
    engine = st.session_state.trading_engine

    if not engine.connected:
        st.warning("Connect to Alpaca in the Auto Trade tab to see live portfolio data.")

    # --- ACCOUNT SUMMARY ---
    st.markdown("##### 💰 Account Summary")
    account = engine.get_account_info()
    if "error" not in account:
        col_a1, col_a2, col_a3, col_a4 = st.columns(4)
        col_a1.metric("Portfolio Value", f"${account.get('portfolio_value', 0):,.2f}")
        col_a2.metric("Cash", f"${account.get('cash', 0):,.2f}")
        col_a3.metric("Buying Power", f"${account.get('buying_power', 0):,.2f}")
        col_a4.metric("Equity", f"${account.get('equity', 0):,.2f}")

    # --- BUCKET OVERVIEW ---
    st.markdown("---")
    st.markdown("##### 🪣 Bucket Overview")
    bucket_ov = engine.get_bucket_overview()

    div_val = bucket_ov["dividend"]["value"]
    gro_val = bucket_ov["growth"]["value"]
    pen_val = bucket_ov["penny"]["value"]
    wit_val = bucket_ov["withdrawal"]["available"]

    if div_val + gro_val + pen_val + wit_val > 0:
        fig_pie = go.Figure(data=[go.Pie(
            labels=["🟢 Dividend", "🔵 Growth", "🔴 Penny", "🟡 Withdrawal"],
            values=[div_val, gro_val, pen_val, wit_val],
            marker=dict(colors=["#4CAF50", "#2196F3", "#f44336", "#FFC107"]),
            hole=0.4,
        )])
        fig_pie.update_layout(title="Capital Allocation", template="plotly_dark", height=350)
        st.plotly_chart(fig_pie, use_container_width=True)

    b1, b2, b3, b4, b5 = st.columns(5)
    with b1:
        div_deposited = bucket_ov["dividend"]["total_deposited"]
        div_return = ((div_val - div_deposited) / div_deposited * 100) if div_deposited > 0 else 0
        st.metric("🟢 Dividend Pot", f"${div_val:,.2f}", f"{div_return:+.1f}% return")
        st.caption(f"Deposited: ${div_deposited:,.2f} | Dividends earned: ${bucket_ov['dividend']['dividends_earned']:,.2f}")
    with b2:
        gro_deposited = bucket_ov["growth"]["total_deposited"]
        gro_return = ((gro_val - gro_deposited) / gro_deposited * 100) if gro_deposited > 0 else 0
        st.metric("🔵 Growth Pot", f"${gro_val:,.2f}", f"{gro_return:+.1f}% return")
        st.caption(f"Deposited: ${gro_deposited:,.2f} | Profits moved in: ${bucket_ov['growth']['profits_moved_in']:,.2f}")
    with b3:
        pen_deposited = bucket_ov["penny"]["total_deposited"]
        pen_return = ((pen_val - pen_deposited) / pen_deposited * 100) if pen_deposited > 0 else 0
        st.metric("🔴 Penny Pot", f"${pen_val:,.2f}", f"{pen_return:+.1f}% return")
        st.caption(f"Deposited: ${pen_deposited:,.2f} | Profits moved out: ${bucket_ov['penny']['profits_to_growth']:,.2f}")
    with b4:
        st.metric("🟡 Withdrawal", f"${wit_val:,.2f}", "🔒 LOCKED")
    with b5:
        profit_color = "🟢" if bucket_ov['total_profit'] >= 0 else "🔴"
        st.metric(f"{profit_color} Total P&L", f"${bucket_ov['total_profit']:,.2f}", f"{bucket_ov.get('profit_pct', 0):.1f}%")

    # --- KEY METRICS ---
    st.markdown("---")
    with st.spinner("Calculating performance metrics..."):
        perf = engine.calculate_performance()

    st.markdown("##### 📊 Performance Metrics")
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    col_p1.metric("Total Return", f"{perf.get('total_return_pct', 0):+.2f}%")
    col_p2.metric("SPY Return", f"{perf.get('spy_return_pct', 0):+.2f}%")
    col_p3.metric("Outperformance", f"{perf.get('outperformance_pct', 0):+.2f}%")
    col_p4.metric("Max Drawdown", f"{perf.get('max_drawdown_pct', 0):.2f}%")

    col_p5, col_p6, col_p7, col_p8 = st.columns(4)
    col_p5.metric("Win Rate", f"{perf.get('win_rate', 0)}%")
    col_p6.metric("Profit Factor", f"{perf.get('profit_factor', 0)}")
    col_p7.metric("Sharpe Ratio", f"{perf.get('sharpe_ratio', 0)}")
    col_p8.metric("Total Trades", f"{perf.get('total_trades', 0)}")

    # --- DIAMOND STANDARD METRICS ---
    st.markdown("---")
    st.markdown("##### 💎 Diamond Standard Metrics")
    col_d1, col_d2, col_d3, col_d4 = st.columns(4)
    col_d1.metric("Sortino Ratio", f"{perf.get('sortino_ratio', 0):.3f}", help="Downside risk only. >1 is good, >2 is excellent")
    col_d2.metric("Calmar Ratio", f"{perf.get('calmar_ratio', 0):.3f}", help="Return vs max drawdown. >1 is good")
    col_d3.metric("Omega Ratio", f"{perf.get('omega_ratio', 0):.3f}", help="Gains vs losses. >1 means more gains than losses")
    col_d4.metric("Best/Worst Day", f"+{perf.get('best_day_pct', 0):.2f}% / {perf.get('worst_day_pct', 0):.2f}%")

    # --- BUCKET BREAKDOWN ---
    st.markdown("---")
    st.markdown("##### 🪣 Bucket Breakdown")
    by_bucket = perf.get("by_bucket", {})
    if by_bucket:
        bucket_data = []
        for bucket_name, bucket_stats in by_bucket.items():
            bucket_icon = BUCKET_ICONS.get(bucket_name, "⚪")
            bucket_data.append({
                "Bucket": f"{bucket_icon} {bucket_name.title()}",
                "Trades": bucket_stats.get("trades", 0),
                "Wins": bucket_stats.get("wins", 0),
                "Win Rate": f"{bucket_stats.get('wins', 0) / max(bucket_stats.get('trades', 1), 1) * 100:.1f}%" if bucket_stats.get("trades", 0) > 0 else "N/A",
                "Return %": f"{bucket_stats.get('return_pct', 0):.2f}%",
            })
        st.dataframe(bucket_data, use_container_width=True)

    # --- EQUITY CURVE ---
    st.markdown("---")
    st.markdown("##### 📈 Equity Curve vs SPY")

    if engine.equity_snapshots and len(engine.equity_snapshots) > 1:
        eq_data = []
        for snap in engine.equity_snapshots:
            row = {
                "Date": snap.get("date", ""),
                "Portfolio Value": snap.get("portfolio_value", 0),
                "Portfolio Return %": snap.get("portfolio_return_pct", 0),
                "SPY Return %": snap.get("spy_return_pct", 0),
            }
            if "dividend_value" in snap:
                row["Dividend"] = snap.get("dividend_value", 0)
            elif "long_term_value" in snap:
                row["Dividend"] = snap.pop("long_term_value", 0)
            row["Growth"] = snap.get("growth_value", 0)
            row["Penny"] = snap.get("penny_value", 0)
            row["Withdrawal"] = snap.get("withdrawal_value", snap.get("withdrawal_available", 0))
            row["Total Profit"] = snap.get("total_profit", 0)
            eq_data.append(row)

        if eq_data:
            eq_df = pd.DataFrame(eq_data)
            fig_equity = go.Figure()
            fig_equity.add_trace(go.Scatter(x=eq_df["Date"], y=eq_df["Portfolio Value"], mode="lines+markers", name="Portfolio Value", line=dict(color="#00d4aa", width=2)))
            fig_equity.update_layout(title="Portfolio Value Over Time", xaxis_title="Date", yaxis_title="Value ($)", height=400, template="plotly_dark")
            st.plotly_chart(fig_equity, use_container_width=True)

            fig_compare = go.Figure()
            fig_compare.add_trace(go.Scatter(x=eq_df["Date"], y=eq_df["Portfolio Return %"], mode="lines+markers", name="Bot Return %", line=dict(color="#00d4aa", width=2)))
            fig_compare.add_trace(go.Scatter(x=eq_df["Date"], y=eq_df["SPY Return %"], mode="lines+markers", name="SPY Return %", line=dict(color="#ff6b6b", width=2)))
            fig_compare.update_layout(title="Bot vs SPY Benchmark", xaxis_title="Date", yaxis_title="Return %", height=400, template="plotly_dark")
            st.plotly_chart(fig_compare, use_container_width=True)

            if "Dividend" in eq_df.columns or "Growth" in eq_df.columns:
                fig_buckets = go.Figure()
                for col, color, name in [
                    ("Dividend", "#4CAF50", "🟢 Dividend"),
                    ("Growth", "#2196F3", "🔵 Growth"),
                    ("Penny", "#f44336", "🔴 Penny"),
                ]:
                    if col in eq_df.columns:
                        fig_buckets.add_trace(go.Scatter(x=eq_df["Date"], y=eq_df[col], mode="lines+markers", name=name, line=dict(color=color, width=2)))
                fig_buckets.update_layout(title="Bucket Values Over Time", xaxis_title="Date", yaxis_title="Value ($)", height=350, template="plotly_dark")
                st.plotly_chart(fig_buckets, use_container_width=True)
    else:
        st.info("No equity data yet. The curve builds up over time. Click '📊 Record Snapshot' below.")

    if st.button("📊 Record Snapshot Now", key="snap_btn_1"):
        with st.spinner("Recording equity snapshot..."):
            engine.record_equity_snapshot()
            st.success("Snapshot recorded!")
            st.rerun()

    # --- DIVIDEND INCOME ---
    st.markdown("---")
    st.markdown("##### 💎 Dividend Income")
    div_history = engine.get_dividend_history()
    if div_history:
        div_df_data = []
        total_dividends = 0
        for d in div_history[-20:]:
            bucket_icon = BUCKET_ICONS.get(d.get("bucket", ""), "⚪")
            moved = "→ 🟡 Withdrawal" if d.get("moved_to_withdrawal") else ""
            div_df_data.append({
                "Date": d.get("date", "N/A"),
                "Symbol": f"{bucket_icon} {d.get('symbol', '?')}",
                "Amount": f"${d.get('amount', 0):.2f}",
                "Bucket": d.get("bucket", "").title(),
                "Status": "✅ Moved to Withdrawal" if d.get("moved_to_withdrawal") else "📊 Received",
            })
            total_dividends += d.get("amount", 0)

        st.dataframe(div_df_data, use_container_width=True)
        st.success(f"💎 **Total Dividend Income: ${total_dividends:,.2f}**")
    else:
        st.info("No dividend payments recorded yet. Click 'Check Dividends' in the Dividends tab to scan for dividends.")

    # --- TRADE HISTORY ---
    st.markdown("---")
    st.markdown("##### 📜 Trade History")

    if engine.trade_log:
        hist_col1, hist_col2 = st.columns(2)
        with hist_col1:
            filter_bucket = st.selectbox("Filter by Bucket", ["All", "Dividend", "Growth", "Penny"], key="hist_bucket_filter")
        with hist_col2:
            filter_side = st.selectbox("Filter by Action", ["All", "Buy", "Sell"], key="hist_side_filter")

        filtered_trades = engine.trade_log.copy()
        if filter_bucket != "All":
            bucket_map = {"Dividend": "dividend", "Growth": "growth", "Penny": "penny"}
            filtered_trades = [t for t in filtered_trades if t.get("bucket", "") == bucket_map.get(filter_bucket, "") or (t.get("bucket") == "long_term" and filter_bucket == "Dividend")]
        if filter_side != "All":
            side_map = {"Buy": "buy", "Sell": "sell"}
            filtered_trades = [t for t in filtered_trades if t.get("side", "") == side_map.get(filter_side, "")]

        trade_data_full = []
        for t in reversed(filtered_trades):
            icon = "🟢" if t.get("side") == "buy" else "🔴" if t.get("side") == "sell" else "🔵"
            bucket = t.get("bucket") or engine.assign_bucket(t.get("symbol", "")) or "penny"
            if bucket == "long_term": bucket = "dividend"
            bucket_icon = BUCKET_ICONS.get(bucket, "⚪")
            trade_data_full.append({
                "Time": t.get("timestamp", "")[:19],
                "Symbol": f"{bucket_icon} {t.get('symbol', '')}",
                "Action": f"{icon} {t.get('side', t.get('action', '')).title()}",
                "Qty": t.get("qty", ""),
                "Price": f"${t.get('price', 0):.2f}" if t.get("price") else "",
                "Bucket": bucket.title(),
                "Confidence": f"{(t.get('confidence') or 0):.0%}",
                "Reason": t.get("reason", ""),
            })

        st.dataframe(trade_data_full, use_container_width=True)
        st.caption(f"Showing {len(trade_data_full)} of {len(engine.trade_log)} trades")
    else:
        st.info("No trades yet.")

    # --- TRADE JOURNAL ---
    if AUDIT_AVAILABLE:
        st.markdown("---")
        st.markdown("##### 📝 Trade Journal")
        st.caption("Record why you entered each trade. This helps you learn and improve over time.")

        journal_entries = get_journal_entries(st.session_state.username)
        if journal_entries:
            for entry in journal_entries[:5]:
                with st.expander(f"📝 {entry.get('symbol', '?')} - {entry.get('action', '')} ({entry.get('timestamp', '')[:10]})"):
                    st.write(f"**Entry Reason:** {entry.get('entry_reason', 'Not recorded')}")
                    st.write(f"**Emotion:** {entry.get('emotion', 'Not recorded')}")
                    st.write(f"**Lesson Learned:** {entry.get('lesson_learned', 'Not recorded')}")
                    st.write(f"**Bucket:** {entry.get('bucket', 'N/A')}")
        else:
            st.info("No journal entries yet. Add notes to your trades below.")

        with st.expander("➕ Add Journal Entry"):
            j_symbol = st.text_input("Symbol", value="", key="journal_symbol")
            j_action = st.selectbox("Action", ["buy", "sell", "hold"], key="journal_action")
            j_reason = st.text_area("Why did you enter this trade?", height=100, key="journal_reason")
            j_emotion = st.selectbox("How did you feel?", ["Confident", "Anxious", "FOMO", "Disciplined", "Uncertain", "Excited"], key="journal_emotion")
            j_lesson = st.text_area("What did you learn?", height=80, key="journal_lesson")

            if st.button("💾 Save Journal Entry"):
                if j_symbol:
                    success = engine.save_trade_note(
                        username=st.session_state.username,
                        symbol=j_symbol,
                        action=j_action,
                        entry_reason=j_reason,
                        emotion=j_emotion,
                        lesson_learned=j_lesson,
                    )
                    if success:
                        st.success("Journal entry saved!")
                    else:
                        st.error("Failed to save. Make sure core/audit.py is installed.")
                else:
                    st.warning("Please enter a symbol.")

    # --- EXPORT & SHARE ---
    st.markdown("---")
    st.markdown("##### 📥 Export & Share")

    today_str = datetime.now().strftime("%Y-%m-%d")

    trade_data = []
    trade_csv = None
    if engine.trade_log:
        for t in engine.trade_log:
            bucket = t.get("bucket", "")
            if bucket == "long_term": bucket = "dividend"
            trade_data.append({
                "Time": t.get("timestamp", "")[:19],
                "Symbol": t.get("symbol", ""),
                "Action": t.get("side", t.get("action", "")),
                "Qty": t.get("qty", ""),
                "Price": f"${t.get('price', 0):.2f}" if t.get("price") else "",
                "Bucket": bucket.title(),
                "Confidence": f"{(t.get('confidence') or 0):.0%}",
                "Reason": t.get("reason", "")[:50],
                "Source": "QuantPro Terminal",
            })
        if trade_data:
            csv_string = pd.DataFrame(trade_data).to_csv(index=False)
            csv_string = watermark_csv(csv_string)
            trade_csv = csv_string.encode('utf-8')

    daily_data = []
    daily_csv = None
    if engine.trade_log:
        for t in engine.trade_log:
            trade_date = t.get("timestamp", "")[:10]
            if trade_date == today_str:
                bucket = t.get("bucket", "")
                if bucket == "long_term": bucket = "dividend"
                daily_data.append({
                    "Time": t.get("timestamp", "")[:19],
                    "Symbol": t.get("symbol", ""),
                    "Action": t.get("side", t.get("action", "")),
                    "Qty": t.get("qty", ""),
                    "Price": f"${t.get('price', 0):.2f}" if t.get("price") else "",
                    "Bucket": bucket.title(),
                    "Confidence": f"{(t.get('confidence') or 0):.0%}",
                    "Reason": t.get("reason", "")[:50],
                    "Source": "QuantPro Terminal",
                })
        if daily_data:
            csv_string = pd.DataFrame(daily_data).to_csv(index=False)
            csv_string = watermark_csv(csv_string)
            daily_csv = csv_string.encode('utf-8')

    col_ex1, col_ex2, col_ex3 = st.columns(3)

    with col_ex1:
        if st.button("📦 Generate CSVs", use_container_width=True):
            with st.spinner("Generating CSV files..."):
                engine.export_to_csv()
                st.success("CSVs generated! (Watermarked with 'Source: QuantPro Terminal')")

        if trade_csv:
            st.download_button(label="📥 Download FULL Trade Log", data=trade_csv, file_name='quantpro_full_trades.csv', mime='text/csv', use_container_width=True)

    with col_ex2:
        if st.button("🔄 Recalculate", use_container_width=True):
            with st.spinner("Calculating..."):
                perf = engine.calculate_performance()
                st.success("Metrics recalculated!")
                st.rerun()

        if st.button("📊 Record Snapshot", use_container_width=True, key="snap_btn_export"):
            with st.spinner("Recording..."):
                engine.record_equity_snapshot()
                st.success("Snapshot recorded!")
                st.rerun()

    with col_ex3:
        if st.button("📡 Post Summary", use_container_width=True):
            db = SessionLocal()
            current_user = db.query(User).filter(User.username == st.session_state.username).first()
            db.close()
            webhook_url = current_user.discord_webhook_url if current_user else ""

            if not webhook_url:
                st.error("Add your Discord Webhook URL in Settings.")
            else:
                with st.spinner("Sending summary..."):
                    try:
                        from core.alerts import send_discord_alert
                        bucket_ov = engine.get_bucket_overview()
                        original_capital = bucket_ov["original_capital"]
                        total_profit = bucket_ov["total_profit"]
                        profit_pct = bucket_ov.get("profit_pct", 0)

                        div_deposited = bucket_ov["dividend"]["total_deposited"]
                        div_value = bucket_ov["dividend"]["value"]
                        div_return_pct = ((div_value - div_deposited) / div_deposited * 100) if div_deposited > 0 else 0

                        gro_deposited = bucket_ov["growth"]["total_deposited"]
                        gro_value = bucket_ov["growth"]["value"]
                        gro_return_pct = ((gro_value - gro_deposited) / gro_deposited * 100) if gro_deposited > 0 else 0

                        pen_deposited = bucket_ov["penny"]["total_deposited"]
                        pen_value = bucket_ov["penny"]["value"]
                        pen_return_pct = ((pen_value - pen_deposited) / pen_deposited * 100) if pen_deposited > 0 else 0

                        if engine.settings.get("discord_privacy_mode", True):
                            msg = (
                                f"📊 **Daily P&L Update** - {today_str}\n\n"
                                f"🟢 Dividend Pot: {div_return_pct:+.1f}% ({bucket_ov['dividend']['positions']} pos)\n"
                                f"🔵 Growth Pot: {gro_return_pct:+.1f}% ({bucket_ov['growth']['positions']} pos)\n"
                                f"🔴 Penny Pot: {pen_return_pct:+.1f}% ({bucket_ov['penny']['positions']} pos)\n"
                                f"🟡 Withdrawal: 🔒 Locked\n\n"
                                f"💰 **Total Return: {profit_pct:+.1f}%**"
                            )
                        else:
                            msg = (
                                f"📊 **Daily P&L Update** - {today_str}\n\n"
                                f"🟢 Dividend Pot: ${div_value:,.2f} ({div_return_pct:+.1f}%, {bucket_ov['dividend']['positions']} pos)\n"
                                f"🔵 Growth Pot: ${gro_value:,.2f} ({gro_return_pct:+.1f}%, {bucket_ov['growth']['positions']} pos)\n"
                                f"🔴 Penny Pot: ${pen_value:,.2f} ({pen_return_pct:+.1f}%, {bucket_ov['penny']['positions']} pos)\n"
                                f"🟡 Withdrawal: ${bucket_ov['withdrawal']['available']:,.2f} 🔒\n\n"
                                f"💰 **Total Profit: ${total_profit:,.2f}** ({profit_pct:+.1f}%)"
                            )

                        if send_discord_alert(webhook_url, msg):
                            st.success("Summary posted to Daily P&L!")
                        else:
                            st.error("Failed. Check your webhook URL.")
                    except Exception as e:
                        st.error(f"Error: {e}")

        if st.button("📄 Upload Daily Log", use_container_width=True):
            db = SessionLocal()
            current_user = db.query(User).filter(User.username == st.session_state.username).first()
            db.close()
            webhook_url = current_user.discord_webhook_url_daily if current_user else ""

            if not webhook_url:
                st.error("Add your Daily P&L Webhook URL in Settings.")
            elif not daily_csv:
                st.warning("No trades today to upload.")
            else:
                with st.spinner("Uploading daily trade log..."):
                    try:
                        from core.alerts import send_discord_file, send_discord_alert
                        filename = f"quantpro_daily_trades_{today_str}.csv"
                        upload_success = send_discord_file(webhook_url, daily_csv, filename, f"📄 **Daily Trade Activity** - {today_str}")
                        if upload_success:
                            st.success("Daily log file uploaded to Discord!")
                        else:
                            st.warning("File upload failed. Posting as text instead...")
                            csv_text = pd.DataFrame(daily_data).to_csv(index=False)
                            csv_text = watermark_csv(csv_text)
                            if len(csv_text) > 1900:
                                msg = f"📄 **Daily Trade Activity** - {today_str}\n\n(Log too large to post as text. Please download CSV from app.)"
                                send_discord_alert(webhook_url, msg)
                                st.warning("File upload failed, and log is too large for text.")
                            else:
                                msg = f"📄 **Daily Trade Activity** - {today_str}\n```csv\n{csv_text}\n```"
                                send_discord_alert(webhook_url, msg)
                                st.success("Daily log posted as text to Discord!")
                    except Exception as e:
                        st.error(f"Error: {e}")

    # --- PRIVATE EXPORT ---
    st.markdown("---")
    st.markdown("##### 🔒 Private Export")
    st.caption("All CSV exports are watermarked with 'Source: QuantPro Terminal' to protect your IP.")

    if engine.trade_log:
        export_data = []
        for t in engine.trade_log:
            bucket = t.get("bucket", "")
            if bucket == "long_term": bucket = "dividend"
            export_data.append({
                "Time": t.get("timestamp", "")[:19],
                "Symbol": t.get("symbol", ""),
                "Action": t.get("side", t.get("action", "")),
                "Qty": t.get("qty", ""),
                "Price": f"${t.get('price', 0):.2f}" if t.get("price") else "",
                "Bucket": bucket.title(),
                "Confidence": f"{(t.get('confidence') or 0):.0%}",
                "Reason": t.get("reason", ""),
                "Sector": t.get("sector", ""),
                "Source": "QuantPro Terminal",
            })

        csv_string = pd.DataFrame(export_data).to_csv(index=False)
        csv_string = watermark_csv(csv_string)

        st.download_button(
            label="📥 Download Private Trade History (Watermarked)",
            data=csv_string.encode('utf-8'),
            file_name=f'quantpro_private_trades_{today_str}.csv',
            mime='text/csv',
            use_container_width=True
        )

    if div_history:
        div_export = []
        for d in div_history:
            div_export.append({
                "Date": d.get("date", ""),
                "Symbol": d.get("symbol", ""),
                "Amount": d.get("amount", 0),
                "Bucket": d.get("bucket", ""),
                "Status": d.get("status", ""),
                "Source": "QuantPro Terminal",
            })
        div_csv = pd.DataFrame(div_export).to_csv(index=False)
        div_csv = watermark_csv(div_csv)

        st.download_button(
            label="📥 Download Dividend History (Watermarked)",
            data=div_csv.encode('utf-8'),
            file_name=f'quantpro_dividends_{today_str}.csv',
            mime='text/csv',
            use_container_width=True
        )

    bucket_export = [{
        "Bucket": "Dividend",
        "Value": bucket_ov["dividend"]["value"],
        "Positions": bucket_ov["dividend"]["positions"],
        "Deposited": bucket_ov["dividend"]["total_deposited"],
        "Return": f"{div_return:+.1f}%",
        "Dividends_Earned": bucket_ov["dividend"]["dividends_earned"],
        "Source": "QuantPro Terminal",
    }, {
        "Bucket": "Growth",
        "Value": bucket_ov["growth"]["value"],
        "Positions": bucket_ov["growth"]["positions"],
        "Deposited": bucket_ov["growth"]["total_deposited"],
        "Return": f"{gro_return:+.1f}%",
        "Profits_Moved_In": bucket_ov["growth"]["profits_moved_in"],
        "Source": "QuantPro Terminal",
    }, {
        "Bucket": "Penny",
        "Value": bucket_ov["penny"]["value"],
        "Positions": bucket_ov["penny"]["positions"],
        "Deposited": bucket_ov["penny"]["total_deposited"],
        "Return": f"{pen_return:+.1f}%",
        "Profits_Moved_Out": bucket_ov["penny"]["profits_to_growth"],
        "Source": "QuantPro Terminal",
    }, {
        "Bucket": "Withdrawal",
        "Available": bucket_ov["withdrawal"]["available"],
        "Dividends_Received": bucket_ov["withdrawal"]["dividends_received"],
        "Profits_Extracted": bucket_ov["withdrawal"]["profits_extracted"],
        "Source": "QuantPro Terminal",
    }]
    bucket_csv = pd.DataFrame(bucket_export).to_csv(index=False)
    bucket_csv = watermark_csv(bucket_csv)

    st.download_button(
        label="📥 Download Bucket Summary (Watermarked)",
        data=bucket_csv.encode('utf-8'),
        file_name=f'quantpro_buckets_{today_str}.csv',
        mime='text/csv',
        use_container_width=True
    )

# ==========================================
# TAB 5: BACKTEST (Unchanged)
# ==========================================
with tab5:
    st.markdown("### 🔬 Backtesting Engine")
    st.caption("Test your strategy against historical data before risking real money.")

    if not BACKTEST_AVAILABLE:
        st.error("⚠️ Backtest module not available. Make sure `core/backtest.py` is installed.")
    else:
        st.markdown("##### ⚙️ Backtest Configuration")

        bt_col1, bt_col2 = st.columns(2)
        with bt_col1:
            bt_symbols = st.text_area(
                "Symbols to Test (comma separated)",
                value="AAPL,MSFT,GOOGL,AMZN,JNJ,PG,KO,XOM,PLTR,NIO",
                height=100,
                key="bt_symbols"
            )
            bt_symbols_list = [s.strip().upper() for s in bt_symbols.split(",") if s.strip()]
            st.info(f"📋 Testing {len(bt_symbols_list)} stocks")

        with bt_col2:
            bt_start = st.date_input("Start Date", value=datetime(2023, 1, 1), key="bt_start")
            bt_end = st.date_input("End Date", value=datetime.now(), key="bt_end")
            bt_strategy = st.selectbox("Strategy", ["combined", "rsi", "macd", "bollinger", "ma_cross"], key="bt_strategy")
            bt_capital = st.number_input("Starting Capital ($)", value=100000, min_value=1000, step=1000, key="bt_capital")

        st.markdown("---")
        st.markdown("##### ▶️ Run Backtest")

        if st.button("🚀 Run Backtest", type="primary", use_container_width=True):
            if len(bt_symbols_list) < 2:
                st.warning("Please enter at least 2 symbols.")
            else:
                with st.spinner(f"Running backtest on {len(bt_symbols_list)} stocks. This may take several minutes..."):
                    bt_result = engine.run_backtest(
                        symbols=bt_symbols_list,
                        start_date=bt_start.strftime("%Y-%m-%d"),
                        end_date=bt_end.strftime("%Y-%m-%d"),
                        strategy=bt_strategy,
                    )

                    if bt_result.get("status") == "complete":
                        st.success(f"✅ Backtest complete! Tested {bt_result.get('symbols_tested', 0)} stocks.")

                        metrics = bt_result.get("metrics", {})
                        st.markdown("##### 📊 Results Summary")

                        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
                        m_col1.metric("Total Return", f"{metrics.get('total_return_pct', 0):+.2f}%")
                        m_col2.metric("Win Rate", f"{metrics.get('win_rate', 0)}%")
                        m_col3.metric("Max Drawdown", f"{metrics.get('max_drawdown_pct', 0):.2f}%")
                        m_col4.metric("Profit Factor", f"{metrics.get('profit_factor', 0)}")

                        st.markdown("---")
                        dm_col1, dm_col2, dm_col3, dm_col4 = st.columns(4)
                        dm_col1.metric("Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0):.3f}")
                        dm_col2.metric("Sortino Ratio", f"{metrics.get('sortino_ratio', 0):.3f}")
                        dm_col3.metric("Calmar Ratio", f"{metrics.get('calmar_ratio', 0):.3f}")
                        dm_col4.metric("Omega Ratio", f"{metrics.get('omega_ratio', 0):.3f}")

                        trades = bt_result.get("trades", [])
                        if trades:
                            st.markdown("---")
                            st.markdown("##### 📜 Trade Breakdown")
                            trade_df = pd.DataFrame(trades)
                            display_cols = ["symbol", "bucket", "entry_date", "exit_date", "entry_price", "exit_price", "pnl_pct", "reason"]
                            available_cols = [c for c in display_cols if c in trade_df.columns]
                            st.dataframe(trade_df[available_cols].head(50), use_container_width=True)
                            st.caption(f"Showing {min(50, len(trades))} of {len(trades)} trades")

                        bucket_pnl = bt_result.get("bucket_pnl", {})
                        if bucket_pnl:
                            st.markdown("---")
                            st.markdown("##### 🪣 Bucket P&L")
                            for bucket, pnl in bucket_pnl.items():
                                icon = BUCKET_ICONS.get(bucket, "⚪")
                                st.write(f"{icon} **{bucket.title()}**: ${pnl:,.2f}")

                        equity_curve = bt_result.get("equity_curve", [])
                        if equity_curve and len(equity_curve) > 1:
                            st.markdown("---")
                            st.markdown("##### 📈 Equity Curve")
                            eq_df = pd.DataFrame(equity_curve)

                            fig_bt = go.Figure()
                            fig_bt.add_trace(go.Scatter(x=eq_df["date"], y=eq_df["equity"], mode="lines", name="Portfolio Value", line=dict(color="#00d4aa", width=2)))

                            if "cash" in eq_df.columns:
                                fig_bt.add_trace(go.Scatter(x=eq_df["date"], y=eq_df["cash"], mode="lines", name="Cash", line=dict(color="#FFC107", width=1, dash="dot")))

                            if "positions_value" in eq_df.columns:
                                fig_bt.add_trace(go.Scatter(x=eq_df["date"], y=eq_df["positions_value"], mode="lines", name="Positions Value", line=dict(color="#42A5F5", width=1, dash="dash")))

                            fig_bt.update_layout(title="Backtest Equity Curve", xaxis_title="Date", yaxis_title="Value ($)", height=400, template="plotly_dark", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                            st.plotly_chart(fig_bt, use_container_width=True)

                            if len(eq_df) > 1:
                                starting = eq_df["equity"].iloc[0]
                                ending = eq_df["equity"].iloc[-1]
                                peak = eq_df["equity"].max()
                                low = eq_df["equity"].min()
                                eq_col1, eq_col2, eq_col3, eq_col4 = st.columns(4)
                                eq_col1.metric("Starting Capital", f"${starting:,.0f}")
                                eq_col2.metric("Ending Value", f"${ending:,.0f}")
                                eq_col3.metric("Peak Value", f"${peak:,.0f}")
                                eq_col4.metric("Lowest Value", f"${low:,.0f}")

                        if trades:
                            bt_csv = pd.DataFrame(trades).to_csv(index=False)
                            bt_csv = watermark_csv(bt_csv)
                            st.download_button(
                                label="📥 Download Backtest Results (Watermarked)",
                                data=bt_csv.encode('utf-8'),
                                file_name=f'quantpro_backtest_{today_str}.csv',
                                mime='text/csv',
                                use_container_width=True
                            )

                    elif bt_result.get("status") == "error":
                        st.error(f"❌ Backtest error: {bt_result.get('message', 'Unknown error')}")
                    else:
                        st.warning(f"⚠️ Backtest status: {bt_result.get('status', 'Unknown')}")

    st.caption("QuantPro Terminal — Automated trading software. Not a financial advisor. Trading involves risk.")

# ==========================================
# TAB 6: DIVIDENDS (Now includes Check Dividends)
# ==========================================
with tab6:
    st.markdown("### 💎 Dividend Intelligence")
    st.caption("Forward-looking dividend data, payment checking, and DRIP analysis.")

    engine = st.session_state.trading_engine

    # --- CHECK FOR DIVIDEND PAYMENTS (moved from Auto Trade) ---
    st.markdown("##### 💰 Check for Dividend Payments")
    div_check_col1, div_check_col2 = st.columns(2)
    with div_check_col1:
        if st.button("💎 Check Dividends", use_container_width=True, type="primary"):
            if not engine.connected:
                st.error("Connect to Alpaca in the Auto Trade tab first!")
            else:
                with st.spinner("Checking for dividend payments..."):
                    div_result = engine.check_dividends()
                    if div_result["status"] == "success":
                        if div_result["dividends_found"] > 0:
                            st.success(f"💎 Found ${div_result['dividends_found']:,.2f} in dividends!")
                            for d in div_result.get("details", []):
                                bucket_icon = BUCKET_ICONS.get(d.get("bucket", ""), "⚪")
                                moved = "→ 🟡 Withdrawal" if d.get("moved_to_withdrawal") else ""
                                st.write(f" {bucket_icon} **{d['symbol']}**: ${d['amount']:.2f} on {d['date']}")
                            try:
                                db = SessionLocal()
                                for d in div_result.get("details", []):
                                    record_dividend(db, st.session_state.username, d['symbol'], d['amount'], d['date'])
                                db.close()
                            except Exception as e:
                                st.warning(f"Could not save dividends to database: {e}")
                        else:
                            st.info("No new dividends found.")
                    else:
                        st.error(f"Dividend check error: {div_result.get('message', 'Unknown')}")
    with div_check_col2:
        div_history = engine.get_dividend_history()
        if div_history:
            with st.expander("📋 Recent Dividends"):
                for d in div_history[-10:]:
                    bucket_icon = BUCKET_ICONS.get(d.get("bucket", ""), "⚪")
                    moved = "→ 🟡 Withdrawal" if d.get("moved_to_withdrawal") else ""
                    st.write(f"{bucket_icon} **{d.get('symbol', '?')}**: ${d.get('amount', 0):.2f} on {d.get('date', 'N/A')} {moved}")
        else:
            st.info("No dividend history yet. Click 'Check Dividends' to scan.")

    st.markdown("---")

    # --- UPCOMING EX-DIVIDEND DATES ---
    st.markdown("##### 📅 Upcoming Ex-Dividend Dates")
    st.caption("Stocks in your watchlist with upcoming ex-dividend dates.")

    if st.button("🔍 Scan for Upcoming Dividends", use_container_width=True):
        with st.spinner("Scanning for upcoming ex-dividend dates... This may take a minute."):
            upcoming = engine.get_upcoming_dividends(days_ahead=60)

            if upcoming:
                st.success(f"Found {len(upcoming)} upcoming ex-dividend dates!")
                div_data = []
                for d in upcoming:
                    bucket = engine.assign_bucket(d.get("symbol", ""))
                    bucket_icon = BUCKET_ICONS.get(bucket, "⚪")
                    div_data.append({
                        "Symbol": f"{bucket_icon} {d['symbol']}",
                        "Ex-Date": d.get("ex_date", "N/A"),
                        "Days Until": d.get("days_until", "N/A"),
                        "Est. Amount": f"${d.get('estimated_amount', 0):.4f}",
                        "Yield": f"{d.get('dividend_yield', 0):.2f}%",
                        "Annual Div": f"${d.get('annual_dividend', 0):.2f}",
                        "Bucket": bucket.title(),
                    })
                st.dataframe(div_data, use_container_width=True)
            else:
                st.info("No upcoming ex-dividend dates found in the next 60 days.")

    # --- DIVIDEND STOCK COMPARISON ---
    st.markdown("---")
    st.markdown("##### 📊 Dividend Stock Comparison")
    st.caption("Compare dividend yields and growth rates across your watchlist.")

    if st.button("📊 Compare Dividend Stocks", use_container_width=True):
        with st.spinner("Fetching dividend data for your watchlist..."):
            comparison = engine.get_dividend_stock_comparison()

            if comparison:
                comp_df = pd.DataFrame(comparison)
                st.dataframe(comp_df, use_container_width=True)

                if len(comp_df) > 0:
                    fig_div = go.Figure(data=[
                        go.Bar(x=comp_df["symbol"], y=comp_df["dividend_yield_pct"], name="Yield %", marker_color="#4CAF50"),
                    ])
                    fig_div.update_layout(
                        title="Dividend Yield Comparison",
                        xaxis_title="Stock",
                        yaxis_title="Dividend Yield (%)",
                        height=400,
                        template="plotly_dark"
                    )
                    st.plotly_chart(fig_div, use_container_width=True)
            else:
                st.info("No dividend data found. Try adding more dividend stocks to your watchlist.")

    # --- DRIP CALCULATOR ---
    st.markdown("---")
    st.markdown("##### 🔄 DRIP Calculator")
    st.caption("Calculate how much your dividend income would grow with Dividend Reinvestment.")

    # Tier check for DRIP calculator
    if TIERS_AVAILABLE and not has_feature(st.session_state.username, "drip_calculator"):
        st.warning("🔒 **DRIP Calculator requires Pro or Fund tier.** Upgrade to unlock dividend reinvestment projections.")
    else:
        drip_col1, drip_col2 = st.columns(2)
        with drip_col1:
            drip_symbol = st.text_input("Stock Symbol", value="KO", key="drip_symbol")
            drip_shares = st.number_input("Number of Shares", value=100, min_value=1, step=10, key="drip_shares")

        with drip_col2:
            drip_years = st.slider("Projection Period (years)", 1, 20, value=10, key="drip_years")

        if drip_symbol and DIVIDEND_CALENDAR_AVAILABLE:
            drip_result = engine.calculate_drip_for_position(drip_symbol, drip_shares)
            if "error" not in drip_result:
                st.markdown(f"**{drip_result['symbol']}** — Dividend Yield: **{drip_result.get('dividend_yield', 0):.2f}%**")
                st.markdown(f"Initial Investment: **${drip_result.get('initial_investment', 0):,.2f}** | Final Value: **${drip_result.get('final_value', 0):,.2f}** | Total Return: **{drip_result.get('total_return_pct', 0):.2f}%**")

                projections = drip_result.get("annual_projections", [])
                if projections:
                    proj_df = pd.DataFrame(projections)
                    fig_drip = go.Figure()
                    fig_drip.add_trace(go.Scatter(x=proj_df["year"], y=proj_df["total_value"], mode="lines+markers", name="Portfolio Value", line=dict(color="#4CAF50", width=2)))
                    fig_drip.add_trace(go.Scatter(x=proj_df["year"], y=proj_df["total_dividends_received"], mode="lines+markers", name="Total Dividends", line=dict(color="#FFC107", width=2)))
                    fig_drip.add_trace(go.Scatter(x=proj_df["year"], y=proj_df["annual_dividend_income"], mode="lines+markers", name="Annual Dividend Income", line=dict(color="#42A5F5", width=2, dash="dot")))
                    fig_drip.add_trace(go.Scatter(x=proj_df["year"], y=proj_df["new_shares_from_drip"], mode="lines+markers", name="New Shares from DRIP", line=dict(color="#AB47BC", width=2, dash="dash"), yaxis="y2"))
                    fig_drip.update_layout(
                        title=f"DRIP Projection — {drip_result['symbol']}",
                        xaxis_title="Year", yaxis_title="Value ($)",
                        yaxis2=dict(title="Shares", overlaying="y", side="right", showgrid=False),
                        height=400, template="plotly_dark",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig_drip, use_container_width=True)

                    st.markdown("###### 📋 Year-by-Year Projection")
                    display_cols = ["year", "shares", "new_shares_from_drip", "annual_dividend_income", "total_dividends_received", "total_value", "total_return_pct"]
                    display_df = proj_df[display_cols].copy()
                    display_df.columns = ["Year", "Total Shares", "New DRIP Shares", "Annual Div Income ($)", "Cumul. Dividends ($)", "Portfolio Value ($)", "Return (%)"]
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                st.info(f"Could not calculate DRIP for {drip_symbol}. Try a dividend-paying stock.")

    # --- DIVIDEND GROWTH ---
    st.markdown("---")
    st.markdown("##### 📈 Dividend Growth Analysis")
    st.caption("See how a stock's dividend has grown over time.")

    growth_symbol = st.text_input("Enter Symbol for Growth Analysis", value="KO", key="growth_symbol")

    if growth_symbol and DIVIDEND_CALENDAR_AVAILABLE:
        growth_data = get_dividend_growth(growth_symbol, years=5)
        if growth_data and growth_data.get("trend") != "insufficient_data":
            st.markdown(f"**{growth_symbol}** — Growth Rate: **{growth_data.get('growth_rate', 0):.2f}% CAGR** | Trend: **{growth_data.get('trend', 'Unknown')}**")
            st.markdown(f"First Year Dividend: ${growth_data.get('first_year_dividend', 0):.2f} | Last Year Dividend: ${growth_data.get('last_year_dividend', 0):.2f}")

            annual = growth_data.get("annual_totals", {})
            if annual:
                ann_df = pd.DataFrame(list(annual.items()), columns=["Year", "Total Dividend"])
                fig_growth = go.Figure(data=[
                    go.Bar(x=ann_df["Year"], y=ann_df["Total Dividend"], marker_color="#4CAF50")
                ])
                fig_growth.update_layout(
                    title=f"Annual Dividend Payments — {growth_symbol}",
                    xaxis_title="Year",
                    yaxis_title="Total Dividend ($)",
                    height=300,
                    template="plotly_dark"
                )
                st.plotly_chart(fig_growth, use_container_width=True)
        else:
            st.info(f"No dividend growth data available for {growth_symbol}.")

    st.caption("QuantPro Terminal — Automated trading software. Not a financial advisor. Trading involves risk.")
