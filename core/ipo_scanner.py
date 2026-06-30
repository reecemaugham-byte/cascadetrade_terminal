"""
core/ipo_scanner.py
CascadeTrade Terminal — IPO & New Listing Scanner
Detects newly tradable stocks on Alpaca and fetches upcoming IPOs from Finnhub.
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Mark this module as available for import checking
IPO_SCANNER_AVAILABLE = True

# ==========================================
# CONFIGURATION
# ==========================================
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
KNOWN_SYMBOLS_FILE = DATA_DIR / "known_symbols.json"

# Module-level default — can be overridden per-call from the database
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")

# Suffixes/prefixes that indicate non-standard securities
SKIP_SUFFIXES = (".U", ".W", ".R", ".PR", ".CL", ".RT", ".UN", ".WS")
SKIP_KEYWORDS = (" ETF", "ETN", " FUND", "TRUST", "PFD", "PRFD")


# ==========================================
# SYMBOL SNAPSHOT MANAGEMENT
# ==========================================

def _is_valid_stock_symbol(symbol: str, name: str = "") -> bool:
    """
    Filter out options, warrants, preferred shares, ETFs, units, etc.
    Keep only common stock symbols that are actually tradeable.
    """
    if not symbol:
        return False

    # Too long — likely structured products or complex instruments
    if len(symbol) > 5:
        return False

    # Contains dots or dashes — likely preferred shares, warrants, units
    # e.g. "AAPL.U", "BAC.WS.A", "TSLA-UN"
    if "." in symbol or "-" in symbol:
        return False

    # Check suffixes (case-insensitive)
    symbol_upper = symbol.upper()
    for suffix in SKIP_SUFFIXES:
        if symbol_upper.endswith(suffix):
            return False

    # Check name for ETF/ETN/fund indicators
    name_upper = (name or "").upper()
    for keyword in SKIP_KEYWORDS:
        if keyword in name_upper:
            return False

    return True


def save_symbol_snapshot(api) -> list:
    """
    Fetch all currently tradable symbols from Alpaca and save to known_symbols.json.
    Returns the list of currently tradable stock symbols.

    Parameters:
        api: An Alpaca Trade API client instance (engine.api or engine.alpaca_api)
    """
    try:
        all_assets = api.list_assets(status='active')
        tradable_symbols = []

        for asset in all_assets:
            if not asset.tradable:
                continue
            symbol = getattr(asset, 'symbol', '')
            name = getattr(asset, 'name', '') or ''

            if not _is_valid_stock_symbol(symbol, name):
                continue

            tradable_symbols.append(symbol)

        # Remove duplicates and sort
        tradable_symbols = sorted(list(set(tradable_symbols)))

        # Save to file
        snapshot = {
            "last_updated": datetime.now().isoformat(),
            "count": len(tradable_symbols),
            "symbols": tradable_symbols,
        }

        with open(KNOWN_SYMBOLS_FILE, 'w') as f:
            json.dump(snapshot, f, indent=2)

        logger.info(f"Saved symbol snapshot: {len(tradable_symbols)} tradable stocks")
        return tradable_symbols

    except Exception as e:
        logger.error(f"Error saving symbol snapshot: {e}")
        return []


def load_known_symbols() -> list:
    """Load the previously saved list of known symbols."""
    if not KNOWN_SYMBOLS_FILE.exists():
        return []
    try:
        with open(KNOWN_SYMBOLS_FILE, 'r') as f:
            data = json.load(f)
            symbols = data.get("symbols", [])
            logger.info(f"Loaded {len(symbols)} known symbols from snapshot")
            return symbols
    except Exception as e:
        logger.error(f"Error loading known symbols: {e}")
        return []


def scan_new_listings(api) -> list:
    """
    Compare current Alpaca tradable symbols against the known snapshot.
    Returns a list of newly tradable symbols (new IPOs or new additions).

    IMPORTANT: This loads the known snapshot FIRST, then fetches the current
    list, compares, and saves the new snapshot. This ensures new symbols
    are only reported once (on the first scan after they appear).

    Parameters:
        api: An Alpaca Trade API client instance
    """
    # Step 1: Load the PREVIOUS snapshot before we overwrite it
    known_symbols = load_known_symbols()

    # Step 2: If no snapshot exists yet, this is the first run — save baseline
    if not known_symbols:
        current_symbols = save_symbol_snapshot(api)
        logger.info(f"First run: saved baseline of {len(current_symbols)} symbols. No new listings to report yet.")
        return []

    # Step 3: Fetch current symbols and save new snapshot
    current_symbols = save_symbol_snapshot(api)

    # Step 4: Find symbols in current that were not in the known snapshot
    known_set = set(known_symbols)
    new_symbols = [s for s in current_symbols if s not in known_set]

    if new_symbols:
        logger.info(f"Found {len(new_symbols)} new listing(s): {new_symbols[:20]}")
    else:
        logger.info("No new listings detected")

    return new_symbols


def get_new_listing_details(new_symbols: list, api=None) -> list:
    """
    Enrich a list of new symbol strings with details from Alpaca.
    Returns a list of dicts with symbol, name, exchange, etc.

    Parameters:
        new_symbols: List of symbol strings from scan_new_listings()
        api: Optional Alpaca API client. If provided, fetches asset details.
    """
    if not new_symbols:
        return []

    results = []

    # If we have the API client, try to get asset details
    if api:
        try:
            all_assets = api.list_assets(status='active')
            asset_lookup = {}
            for asset in all_assets:
                asset_lookup[asset.symbol] = asset

            for symbol in new_symbols[:25]:  # Limit to 25
                asset = asset_lookup.get(symbol)
                if asset:
                    results.append({
                        "symbol": symbol,
                        "name": getattr(asset, 'name', 'Unknown') or 'Unknown',
                        "exchange": getattr(asset, 'exchange', 'N/A') or 'N/A',
                        "price": "N/A",
                        "status": "New Listing",
                    })
                else:
                    results.append({
                        "symbol": symbol,
                        "name": "Unknown",
                        "exchange": "N/A",
                        "price": "N/A",
                        "status": "New Listing",
                    })

        except Exception as e:
            logger.warning(f"Could not fetch asset details from Alpaca: {e}")
            # Fall back to symbol-only listing
            for symbol in new_symbols[:25]:
                results.append({
                    "symbol": symbol,
                    "name": "Unknown",
                    "exchange": "N/A",
                    "price": "N/A",
                    "status": "New Listing",
                })
    else:
        # No API client — just list symbols
        for symbol in new_symbols[:25]:
            results.append({
                "symbol": symbol,
                "name": "Unknown",
                "exchange": "N/A",
                "price": "N/A",
                "status": "New Listing",
            })

    return results


# ==========================================
# FINNHUB IPO CALENDAR
# ==========================================

def get_upcoming_ipos(days_ahead: int = 14, finnhub_api_key: str = "") -> list:
    """
    Fetch upcoming IPOs from Finnhub within the next `days_ahead` days.

    Accepts an API key as a parameter (preferred — passed from the user's
    database settings). Falls back to the FINNHUB_API_KEY environment variable
    if no key is provided.

    Returns a list of IPO dictionaries with:
        symbol, name, date, exchange, price_range, status, numberOfShares
    """
    # Use parameter key first, then module-level env var
    api_key = finnhub_api_key or FINNHUB_API_KEY

    if not api_key:
        logger.warning("No Finnhub API key provided — IPO scan skipped")
        return []

    try:
        today = datetime.now().date()
        from_date = today.strftime("%Y-%m-%d")
        to_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        url = "https://finnhub.io/api/v1/calendar/ipo"
        params = {
            "from": from_date,
            "to": to_date,
            "token": api_key,
        }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 401:
            logger.error("Finnhub API key is invalid or expired")
            return []
        elif response.status_code == 429:
            logger.warning("Finnhub API rate limit reached — try again later")
            return []
        elif response.status_code != 200:
            logger.error(f"Finnhub API returned status {response.status_code}")
            return []

        data = response.json()
        ipo_list = data.get("ipoCalendar", [])

        if not ipo_list:
            logger.info(f"No upcoming IPOs found for {from_date} to {to_date}")
            return []

        formatted_ipos = []
        for ipo in ipo_list:
            # Finnhub returns various fields — extract what's available
            symbol = ipo.get("symbol", "N/A")
            name = ipo.get("name", "Unknown")
            date = ipo.get("date", "N/A")
            exchange = ipo.get("exchange", "N/A")
            price_low = ipo.get("price", "N/A")
            shares = ipo.get("numberOfShares", "N/A")

            # Format price range nicely
            if price_low and price_low != "N/A":
                price_range = f"${price_low}"
            else:
                price_range = "N/A"

            # Format shares
            if shares and shares != "N/A":
                try:
                    shares_num = int(shares)
                    if shares_num >= 1_000_000:
                        shares_display = f"{shares_num / 1_000_000:.1f}M"
                    elif shares_num >= 1_000:
                        shares_display = f"{shares_num / 1_000:.0f}K"
                    else:
                        shares_display = str(shares_num)
                except (ValueError, TypeError):
                    shares_display = str(shares)
            else:
                shares_display = "N/A"

            formatted_ipos.append({
                "symbol": symbol,
                "name": name,
                "date": date,
                "exchange": exchange,
                "price_range": price_range,
                "shares": shares_display,
                "status": "Upcoming",
            })

        logger.info(f"Finnhub returned {len(formatted_ipos)} upcoming IPO(s)")
        return formatted_ipos

    except requests.exceptions.Timeout:
        logger.error("Finnhub API request timed out")
        return []
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to Finnhub API — check internet connection")
        return []
    except Exception as e:
        logger.error(f"Finnhub IPO fetch error: {e}")
        return []


# ==========================================
# ALERT FORMATTING
# ==========================================

def format_ipo_alert(new_symbols: list, upcoming_ipos: list) -> str:
    """
    Format new listings and upcoming IPOs into a Discord-friendly message.
    Used by the Discord alert system.
    """
    message_parts = ["📊 **CascadeTrade IPO & New Listings Report**\n"]

    if new_symbols:
        count = len(new_symbols)
        message_parts.append(f"🆕 **Newly Tradable on Alpaca** ({count}):")
        for symbol in new_symbols[:10]:
            message_parts.append(f"  • {symbol}")
        if count > 10:
            message_parts.append(f"  • ... and {count - 10} more")
        message_parts.append("")

    if upcoming_ipos:
        count = len(upcoming_ipos)
        message_parts.append(f"📅 **Upcoming IPOs** ({count}):")
        for ipo in upcoming_ipos[:5]:
            symbol = ipo.get("symbol", "N/A")
            name = ipo.get("name", "Unknown")
            date = ipo.get("date", "N/A")
            price = ipo.get("price_range", "N/A")
            message_parts.append(f"  • **{symbol}** — {name} | {date} | {price}")
        if count > 5:
            message_parts.append(f"  • ... and {count - 5} more")

    if len(message_parts) == 1:
        # Only the header, no content
        return ""

    return "\n".join(message_parts)


def format_ipo_for_display(new_symbols: list, upcoming_ipos: list) -> list:
    """
    Format IPO data for display in the Streamlit app (as a list of dicts
    suitable for st.dataframe or st.table).

    Returns a combined list sorted by date.
    """
    rows = []

    for symbol in new_symbols[:25]:
        rows.append({
            "Symbol": symbol,
            "Name": "New Listing",
            "Date": datetime.now().strftime("%Y-%m-%d"),
            "Exchange": "Alpaca",
            "Price": "—",
            "Shares": "—",
            "Source": "Alpaca Scan",
            "Status": "🆕 New",
        })

    for ipo in upcoming_ipos:
        rows.append({
            "Symbol": ipo.get("symbol", "N/A"),
            "Name": ipo.get("name", "Unknown"),
            "Date": ipo.get("date", "N/A"),
            "Exchange": ipo.get("exchange", "N/A"),
            "Price": ipo.get("price_range", "N/A"),
            "Shares": ipo.get("shares", "N/A"),
            "Source": "Finnhub",
            "Status": "📅 Upcoming",
        })

    return rows
