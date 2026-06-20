"""
core/tiers.py
QuantPro Terminal — Tier Feature Definitions & Access Control

Defines what each tier can access and provides helper functions
to check feature availability for any user.
"""

# ============================================================
# TIER FEATURE DEFINITIONS
# ============================================================

TIER_FEATURES = {
    "starter": {
        "name": "Starter",
        "price": "Free",
        "paper_trading": True,
        "basic_signals": True,
        "advanced_signals": False,
        "ai_sentiment": False,
        "multi_timeframe": False,
        "live_trading": False,
        "drip_calculator": False,
        "diamond_metrics": False,
        "auto_profit_extraction": False,
        "backtesting": True,
        "discord_alerts": True,
        "dividend_calendar": True,
        "trade_journal": True,
        "max_positions": 10,
        "scan_interval_min": 5,
        "max_watchlist": 50,
    },
    "pro": {
        "name": "Pro",
        "price": "$29/month",
        "paper_trading": True,
        "basic_signals": True,
        "advanced_signals": True,
        "ai_sentiment": True,
        "multi_timeframe": True,
        "live_trading": True,
        "drip_calculator": True,
        "diamond_metrics": True,
        "auto_profit_extraction": True,
        "backtesting": True,
        "discord_alerts": True,
        "dividend_calendar": True,
        "trade_journal": True,
        "max_positions": 20,
        "scan_interval_min": 1,
        "max_watchlist": 200,
    },
    "fund": {
        "name": "Fund",
        "price": "$99/month",
        "paper_trading": True,
        "basic_signals": True,
        "advanced_signals": True,
        "ai_sentiment": True,
        "multi_timeframe": True,
        "live_trading": True,
        "drip_calculator": True,
        "diamond_metrics": True,
        "auto_profit_extraction": True,
        "backtesting": True,
        "discord_alerts": True,
        "dividend_calendar": True,
        "trade_journal": True,
        "max_positions": 50,
        "scan_interval_min": 1,
        "max_watchlist": 500,
        "multiple_accounts": True,
        "auto_rebalancing": True,
        "weekly_reports": True,
        "priority_support": True,
    },
    "admin": {
        "name": "Admin",
        "price": "Internal",
        "paper_trading": True,
        "basic_signals": True,
        "advanced_signals": True,
        "ai_sentiment": True,
        "multi_timeframe": True,
        "live_trading": True,
        "drip_calculator": True,
        "diamond_metrics": True,
        "auto_profit_extraction": True,
        "backtesting": True,
        "discord_alerts": True,
        "dividend_calendar": True,
        "trade_journal": True,
        "max_positions": 999,
        "scan_interval_min": 1,
        "max_watchlist": 999,
        "multiple_accounts": True,
        "auto_rebalancing": True,
        "weekly_reports": True,
        "priority_support": True,
        "admin_panel": True,
        "can_change_tiers": True,
    },
}

# ============================================================
# TIER DISPLAY INFO (for UI)
# ============================================================

TIER_DISPLAY = {
    "starter": {
        "icon": "🆓",
        "label": "Starter (Free)",
        "color": "#a0a0a0",
    },
    "pro": {
        "icon": "⚡",
        "label": "Pro",
        "color": "#00d4aa",
    },
    "fund": {
        "icon": "💎",
        "label": "Fund",
        "color": "#ffd700",
    },
    "admin": {
        "icon": "🔧",
        "label": "Admin",
        "color": "#ff6b6b",
    },
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_user_tier(username: str) -> str:
    """Get the tier for a user. Returns 'starter' if not set or error."""
    try:
        from core.database import SessionLocal, User
        db = SessionLocal()
        user = db.query(User).filter(User.username == username).first()
        db.close()
        if user and hasattr(user, 'tier') and user.tier:
            return user.tier
    except Exception:
        pass
    return "starter"


def has_feature(username: str, feature: str) -> bool:
    """Check if a user has access to a specific feature."""
    tier = get_user_tier(username)
    features = TIER_FEATURES.get(tier, TIER_FEATURES["starter"])
    return features.get(feature, False)


def get_tier_limits(username: str) -> dict:
    """Get the limits for a user's tier (max_positions, scan_interval, etc.)."""
    tier = get_user_tier(username)
    return TIER_FEATURES.get(tier, TIER_FEATURES["starter"])


def get_tier_display(username: str) -> dict:
    """Get the display info for a user's tier (icon, label, color)."""
    tier = get_user_tier(username)
    return TIER_DISPLAY.get(tier, TIER_DISPLAY["starter"])


def set_user_tier(username: str, tier: str) -> bool:
    """Set a user's tier. Used by admin panel or payment webhook."""
    if tier not in TIER_FEATURES:
        return False
    try:
        from core.database import SessionLocal, User
        db = SessionLocal()
        user = db.query(User).filter(User.username == username).first()
        if user:
            user.tier = tier
            db.commit()
            db.close()
            return True
        db.close()
    except Exception:
        pass
    return False


def get_all_users():
    """Get all users with their tier info. Admin only."""
    try:
        from core.database import SessionLocal, User
        db = SessionLocal()
        users = db.query(User).all()
        result = []
        for u in users:
            result.append({
                "username": u.username,
                "tier": getattr(u, 'tier', 'starter') or 'starter',
                "created_at": str(getattr(u, 'created_at', 'N/A')),
                "last_login": str(getattr(u, 'last_login', 'N/A')),
            })
        db.close()
        return result
    except Exception:
        return []


def get_upgrade_message(feature: str) -> str:
    """Get an upgrade prompt message for a locked feature."""
    messages = {
        "advanced_signals": "🔬 Advanced Signals (Bollinger, MA Cross, VIX Filter)",
        "ai_sentiment": "🤖 AI News Sentiment (OpenAI)",
        "multi_timeframe": "🔭 Multi-Timeframe Confirmation",
        "live_trading": "💸 Live Trading with Real Money",
        "drip_calculator": "🔄 DRIP Calculator",
        "diamond_metrics": "💎 Diamond Metrics (Sortino, Calmar, Omega)",
        "auto_profit_extraction": "⚡ Auto Profit Extraction",
        "multiple_accounts": "👥 Multiple Accounts",
        "auto_rebalancing": "⚖️ Auto-Rebalancing",
        "weekly_reports": "📊 Weekly Reports",
    }
    return messages.get(feature, f"🔒 {feature.replace('_', ' ').title()}")
