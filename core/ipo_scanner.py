"""
core/ipo_scanner.py
QuantPro Terminal — IPO & New Listing Scanner
Detects newly tradable stocks on Alpaca and fetches upcoming IPOs from Finnhub.
"""

import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

# ==========================================
# CONFIGURATION
# ==========================================
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
KNOWN_SYMBOLS_FILE = DATA_DIR / "known_symbols.json"

FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")

# ==========================================
# SYMBOL SNAPSHOT MANAGEMENT
# ==========================================

def save_symbol_snapshot(api) -> list:
    """
    Fetch all currently tradable symbols from Alpaca and save to known_symbols.json.
    Returns the list of currently tradable symbols.
    """
    try:
        all_assets = api.list_assets(status='active')
        tradable_symbols = []
        
        for asset in all_assets:
            if not asset.tradable:
                continue
            symbol = asset.symbol
            # Filter out weird symbols (options, warrants, units, etc.)
            if len(symbol) > 5 or '.' in symbol or '-' in symbol:
                continue
            if any(p in symbol for p in ['ETF', 'ETN', 'PRN', 'U', 'W']):
                continue
                
            tradable_symbols.append(symbol)
        
        # Remove duplicates and sort
        tradable_symbols = sorted(list(set(tradable_symbols)))
        
        # Save to file
        snapshot = {
            "last_updated": datetime.now().isoformat(),
            "count": len(tradable_symbols),
            "symbols": tradable_symbols
        }
        
        with open(KNOWN_SYMBOLS_FILE, 'w') as f:
            json.dump(snapshot, f, indent=2)
            
        return tradable_symbols
        
    except Exception as e:
        print(f"Error saving symbol snapshot: {e}")
        return []


def load_known_symbols() -> list:
    """Load the previously saved list of known symbols."""
    if not KNOWN_SYMBOLS_FILE.exists():
        return []
    try:
        with open(KNOWN_SYMBOLS_FILE, 'r') as f:
            data = json.load(f)
            return data.get("symbols", [])
    except Exception:
        return []


def detect_new_symbols(api) -> list:
    """
    Compare current Alpaca tradable symbols against the known snapshot.
    Returns a list of newly tradable symbols (IPOs or new additions).
    """
    current_symbols = save_symbol_snapshot(api)
    known_symbols = load_known_symbols()
    
    # If no known symbols exist, this is the first run. Save and return empty.
    if not known_symbols:
        return []
    
    # Find symbols in current that are not in known
    new_symbols = [s for s in current_symbols if s not in known_symbols]
    
    return new_symbols


# ==========================================
# FINNHUB IPO CALENDAR
# ==========================================

def get_upcoming_ipos(days_ahead: int = 7) -> list:
    """
    Fetch upcoming IPOs from Finnhub within the next `days_ahead` days.
    Requires FINNHUB_API_KEY environment variable.
    Returns a list of IPO dictionaries.
    """
    if not FINNHUB_API_KEY:
        return []
    
    try:
        today = datetime.now().date()
        from_date = today.strftime("%Y-%m-%d")
        to_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        
        url = f"https://finnhub.io/api/v1/calendar/ipo?from={from_date}&to={to_date}&token={FINNHUB_API_KEY}"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return []
            
        data = response.json()
        ipo_list = data.get("ipoCalendar", [])
        
        formatted_ipos = []
        for ipo in ipo_list:
            formatted_ipos.append({
                "symbol": ipo.get("symbol", "N/A"),
                "name": ipo.get("name", "Unknown"),
                "date": ipo.get("date", "N/A"),
                "exchange": ipo.get("exchange", "N/A"),
                "price_range": f"${ipo.get('price', 'N/A')}",
                "status": "Upcoming"
            })
            
        return formatted_ipos
        
    except Exception as e:
        print(f"Finnhub IPO fetch error: {e}")
        return []


# ==========================================
# ALERT FORMATTING
# ==========================================

def format_ipo_alert(new_symbols: list, upcoming_ipos: list) -> str:
    """
    Format new listings and upcoming IPOs into a Discord-friendly message.
    """
    message_parts = []
    
    if new_symbols:
        message_parts.append("🆕 **Newly Tradable Stocks on Alpaca:**")
        for symbol in new_symbols[:10]:  # Limit to 10 to avoid huge messages
            message_parts.append(f"• {symbol}")
        if len(new_symbols) > 10:
            message_parts.append(f"• ... and {len(new_symbols) - 10} more")
    
    if upcoming_ipos:
        message_parts.append("\n📅 **Upcoming IPOs (Next 7 Days):**")
        for ipo in upcoming_ipos[:5]:  # Limit to 5
            symbol = ipo.get("symbol", "N/A")
            name = ipo.get("name", "Unknown")
            date = ipo.get("date", "N/A")
            price = ipo.get("price_range", "N/A")
            message_parts.append(f"• **{symbol}** - {name} | Date: {date} | Price: {price}")
    
    if not message_parts:
        return ""
        
    return "\n".join(message_parts)
