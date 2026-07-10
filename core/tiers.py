"""
core/tiers.py
Roleigh QuanTrader — Tier Feature Definitions & Access Control

Defines what each tier can access and provides helper functions
to check feature availability for any user.
"""

# ============================================================
# TIER FEATURE DEFINITIONS
# ============================================================

TIER_FEATURES = {
    "free": {
        "name": "Free (Paper)",
        "price": "£0/month",
        "paper_trading": True,
        "live_trading": False,
        "basic_signals": True,
        "stop_losses": True,
        "vix_filter": False,
        "trailing_stops": False,
        "atr_position_sizing": False,
        "profit_skimming": False,
        "dividend_tracking": False,
        "advanced_signals": False,
        "ai_sentiment": False,
        "drip_calculator": False,
        "diamond_metrics": False,
        "multiple_accounts": False,
        "max_positions": 10,
        "scan_interval_min": 5,
        "max_watchlist": 25,
        "discord_alerts": "basic",
    },
    "live_trading": {
        "name": "Live Trading",
        "price": "£19.99/month",
        "paper_trading": True,
        "live_trading": True,
        "basic_signals": True,
        "stop_losses": True,
        "vix_filter": True,
        "trailing_stops": True,
        "atr_position_sizing": True,
        "profit_skimming": True,
        "dividend_tracking": True,
        "advanced_signals": False,
        "ai_sentiment": False,
        "drip_calculator": False,
        "diamond_metrics": False,
        "multiple_accounts": False,
        "max_positions": 20,
        "scan_interval_min": 3,
        "max_watchlist": 100,
        "discord_alerts": "full",
    },
    "pro_trader": {
        "name": "Pro Trader",
        "price": "£49.99/month",
        "paper_trading": True,
        "live_trading": True,
        "basic_signals": True,
        "stop_losses": True,
        "vix_filter": True,
        "trailing_stops": True,
        "atr_position_sizing": True,
        "profit_skimming": True,
        "dividend_tracking": True,
        "advanced_signals": True,
        "ai_sentiment": True,
        "drip_calculator": True,
        "diamond_metrics": True,
        "multiple_accounts": True,
        "max_positions": 50,
        "scan_interval_min": 1,
        "max_watchlist": 9999,  # Unlimited
        "discord_alerts": "full_profit",
        "auto_rebalancing": True,
        "weekly_reports": True,
        "priority_support": True,
    },
    "admin": {
        "name": "Roleigh QuanTrader Admin",
        "price": "Internal",
        "paper_trading": True,
        "live_trading": True,
        "basic_signals": True,
        "stop_losses": True,
        "vix_filter": True,
        "trailing_stops": True,
        "atr_position_sizing": True,
        "profit_skimming": True,
        "dividend_tracking": True,
        "advanced_signals": True,
        "ai_sentiment": True,
        "drip_calculator": True,
        "diamond_metrics": True,
        "multiple_accounts": True,
        "max_positions": 999,
        "scan_interval_min": 1,
        "max_watchlist": 999,
        "discord_alerts": "full_profit",
        "admin_panel": True,
        "can_change_tiers": True,
    },
}

# ============================================================
# TIER DISPLAY INFO (for UI)
# ============================================================

TIER_DISPLAY = {
    "free": {
        "icon": "🆓",
        "label": "Free (Paper)",
        "color": "#a0a0a0",
    },
    "live_trading": {
        "icon": "⚡",
        "label": "Live Trading",
        "color": "#00d4aa",
    },
    "pro_trader": {
        "icon": "💎",
        "label": "Pro Trader",
        "color": "#ffd700",
    },
    "admin": {
        "icon": "🔧",
        "label": "Roleigh QuanTrader Admin",
        "color": "#ff6b6b",
    },
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_user_tier(username: str) -> str:
    """Get the effective tier for a user.
    Delegates to database.get_user_tier() which checks both the
    legacy tier column and Stripe subscription status/expiry.
    Returns 'free' on any error or if not set.
    """
    try:
        from core.database import SessionLocal, get_user_tier as db_get_user_tier
        db = SessionLocal()
        try:
            tier = db_get_user_tier(db, username)
            return tier
        finally:
            db.close()
    except Exception:
        pass
    return "free"


def has_feature(username: str, feature: str) -> bool:
    """Check if a user has access to a specific feature."""
    tier = get_user_tier(username)
    features = TIER_FEATURES.get(tier, TIER_FEATURES["free"])
    return features.get(feature, False)


def get_tier_limits(username: str) -> dict:
    """Get the limits for a user's tier (max_positions, scan_interval, etc.)."""
    tier = get_user_tier(username)
    return TIER_FEATURES.get(tier, TIER_FEATURES["free"])


def get_tier_display(username: str) -> dict:
    """Get the display info for a user's tier (icon, label, color)."""
    tier = get_user_tier(username)
    return TIER_DISPLAY.get(tier, TIER_DISPLAY["free"])


def set_user_tier(username: str, tier: str) -> bool:
    """Set a user's tier. Used by admin panel or payment webhook.
    Delegates to database.set_user_tier() which also handles
    subscription field syncing when appropriate.
    """
    if tier not in TIER_FEATURES:
        return False
    try:
        from core.database import SessionLocal, set_user_tier as db_set_user_tier
        db = SessionLocal()
        try:
            result = db_set_user_tier(db, username, tier)
            return result
        finally:
            db.close()
    except Exception:
        pass
    return False


def get_all_users():
    """Get all users with their tier info. Admin only."""
    try:
        from core.database import SessionLocal, get_all_users_with_tiers
        db = SessionLocal()
        try:
            return get_all_users_with_tiers(db)
        finally:
            db.close()
    except Exception:
        return []


def get_upgrade_message(feature: str) -> str:
    """Get an upgrade prompt message for a locked feature."""
    messages = {
        "live_trading": "💸 Live Trading with Real Money",
        "vix_filter": "🛡️ VIX Fear Filter",
        "trailing_stops": "📈 Trailing Stops",
        "atr_position_sizing": "📐 ATR Position Sizing",
        "profit_skimming": "⚡ Profit Skimming",
        "dividend_tracking": "💎 Dividend Tracking & Capture",
        "advanced_signals": "🔬 Advanced Signals (Bollinger, MA Cross)",
        "ai_sentiment": "🤖 AI News Sentiment (OpenAI)",
        "drip_calculator": "🔄 DRIP Calculator",
        "diamond_metrics": "💎 Diamond Metrics (Sortino, Calmar, Omega)",
        "multiple_accounts": "👥 Multiple Accounts",
        "auto_rebalancing": "⚖️ Auto-Rebalancing",
        "weekly_reports": "📊 Weekly Reports",
    }
    return messages.get(feature, f"🔒 {feature.replace('_', ' ').title()}")
