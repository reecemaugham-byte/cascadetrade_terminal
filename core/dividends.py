"""
core/dividends.py
Forward-looking dividend calendar, yield tracking, growth analysis,
and DRIP (Dividend Reinvestment) calculator.
"""

import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False


def get_upcoming_ex_dividends(symbols: List[str], days_ahead: int = 30) -> List[Dict]:
    """Get upcoming ex-dividend dates for a list of symbols.
    Returns a list of dicts with symbol, ex_date, dividend_amount, yield.
    """
    if not YF_AVAILABLE:
        return []

    upcoming = []
    today = datetime.now()
    future = today + timedelta(days=days_ahead)

    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info or {}

            # Get dividend rate
            div_rate = info.get('dividendRate', 0) or 0
            div_yield = info.get('dividendYield', 0) or 0
            ex_date_str = info.get('exDividendDate', None)

            if div_yield > 1:
                div_yield = div_yield / 100

            if div_rate > 0:
                # Calculate approximate next ex-date
                if ex_date_str:
                    try:
                        if isinstance(ex_date_str, (int, float)):
                            from datetime import datetime as dt
                            ex_date = dt.fromtimestamp(ex_date_str)
                        else:
                            ex_date = pd.to_datetime(ex_date_str)

                        # If ex-date is in the past, estimate next one
                        if ex_date < today:
                            # Most stocks pay quarterly, so add ~3 months
                            ex_date = ex_date + timedelta(days=91)
                            # Keep adding until it's in the future
                            while ex_date < today:
                                ex_date += timedelta(days=91)

                        if today <= ex_date <= future:
                            upcoming.append({
                                "symbol": symbol,
                                "ex_date": ex_date.strftime("%Y-%m-%d"),
                                "days_until": (ex_date - today).days,
                                "estimated_amount": round(div_rate / 4, 4),
                                "dividend_yield": round(div_yield * 100, 2) if div_yield else 0,
                                "annual_dividend": div_rate,
                                "source": "yfinance",
                            })
                    except Exception:
                        pass

        except Exception:
            continue

    # Sort by days until ex-date
    upcoming.sort(key=lambda x: x.get("days_until", 999))
    return upcoming


def get_dividend_yield(symbol: str) -> Optional[float]:
    """Get current dividend yield for a stock (as a decimal, e.g., 0.03 = 3%)."""
    if not YF_AVAILABLE:
        return None
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        div_yield = info.get('dividendYield')
        return div_yield if div_yield and div_yield > 0 else None
    except Exception:
        return None


def get_dividend_history(symbol: str, years: int = 5) -> List[Dict]:
    """Get dividend payment history for a stock."""
    if not YF_AVAILABLE:
        return []
    try:
        ticker = yf.Ticker(symbol)
        divs = ticker.dividends
        if divs is None or divs.empty:
            return []

        cutoff = datetime.now() - timedelta(days=years * 365)
        result = []
        for date, amount in divs.items():
            date_dt = pd.to_datetime(date)
            if date_dt >= pd.Timestamp(cutoff):
                result.append({
                    "symbol": symbol,
                    "date": date_dt.strftime("%Y-%m-%d"),
                    "amount": round(float(amount), 4),
                })

        return sorted(result, key=lambda x: x["date"], reverse=True)
    except Exception:
        return []


def get_dividend_growth(symbol: str, years: int = 5) -> Dict:
    """Calculate dividend growth rate over time."""
    history = get_dividend_history(symbol, years)
    if len(history) < 2:
        return {"symbol": symbol, "growth_rate": 0, "years_of_data": len(history),
                "trend": "insufficient_data"}

    # Calculate annual totals
    annual = {}
    for d in history:
        year = d["date"][:4]
        annual[year] = annual.get(year, 0) + d["amount"]

    if len(annual) < 2:
        return {"symbol": symbol, "growth_rate": 0, "years_of_data": len(annual),
                "trend": "insufficient_data"}

    years_sorted = sorted(annual.keys())
    first_year = annual[years_sorted[0]]
    last_year = annual[years_sorted[-1]]
    num_years = int(years_sorted[-1]) - int(years_sorted[0])

    if first_year > 0 and num_years > 0:
        cagr = ((last_year / first_year) ** (1 / num_years) - 1) * 100
    else:
        cagr = 0

    if last_year > first_year:
        trend = "increasing"
    elif last_year < first_year:
        trend = "decreasing"
    else:
        trend = "stable"

    return {
        "symbol": symbol,
        "growth_rate": round(cagr, 2),
        "first_year_dividend": round(first_year, 4),
        "last_year_dividend": round(last_year, 4),
        "years_of_data": num_years,
        "trend": trend,
        "annual_totals": {k: round(v, 4) for k, v in sorted(annual.items())},
    }


def calculate_drip(symbol: str, shares: int, current_price: float,
                    div_yield: float, years: int = 10) -> Dict:
    """Calculate Dividend Reinvestment Plan (DRIP) projections.
    Shows how many shares you'd accumulate over time with dividends reinvested.
    """
    if div_yield <= 0 or current_price <= 0 or shares <= 0:
        return {"symbol": symbol, "error": "Invalid inputs"}

    # Fix: yfinance sometimes returns yield as percentage (2.7) instead of decimal (0.027)
    if div_yield > 1:
        div_yield = div_yield / 100
        
    quarterly_div = (div_yield * current_price) / 4  # Approximate quarterly dividend per share
    annual_projections = []
    total_shares = shares
    total_invested = shares * current_price
    total_dividends_received = 0

    for year in range(1, years + 1):
        annual_div = total_shares * (div_yield * current_price)
        total_dividends_received += annual_div
        new_shares = annual_div / current_price  # Shares bought with reinvested dividends
        total_shares += new_shares
        total_value = total_shares * current_price

        annual_projections.append({
            "year": year,
            "shares": round(total_shares, 2),
            "new_shares_from_drip": round(new_shares, 4),
            "annual_dividend_income": round(annual_div, 2),
            "total_dividends_received": round(total_dividends_received, 2),
            "total_value": round(total_value, 2),
            "total_return_pct": round((total_value - total_invested) / total_invested * 100, 2),
        })

    return {
        "symbol": symbol,
        "initial_shares": shares,
        "initial_investment": round(total_invested, 2),
        "dividend_yield": round(div_yield * 100, 2),
        "current_price": current_price,
        "final_shares": round(total_shares, 2),
        "final_value": round(total_shares * current_price, 2),
        "total_dividends": round(total_dividends_received, 2),
        "total_return_pct": round(((total_shares * current_price - total_invested) / total_invested) * 100, 2),
        "years": years,
        "annual_projections": annual_projections,
    }


def get_dividend_comparison(symbols: List[str]) -> List[Dict]:
    """Compare dividend yields and growth across multiple stocks.
    Useful for the Dividend Pot selection.
    """
    results = []
    for symbol in symbols:
        try:
            div_yield = get_dividend_yield(symbol)
            if div_yield and div_yield > 0:
                growth = get_dividend_growth(symbol, years=3)
                upcoming = get_upcoming_ex_dividends([symbol], days_ahead=90)

                results.append({
                    "symbol": symbol,
                    "dividend_yield_pct": round(div_yield * 100, 2),
                    "dividend_growth_rate": growth.get("growth_rate", 0),
                    "dividend_trend": growth.get("trend", "unknown"),
                    "next_ex_date": upcoming[0]["ex_date"] if upcoming else "Unknown",
                    "days_until_ex": upcoming[0]["days_until"] if upcoming else None,
                    "annual_dividend": upcoming[0].get("annual_dividend", 0) if upcoming else 0,
                })
        except Exception:
            continue

    results.sort(key=lambda x: x.get("dividend_yield_pct", 0), reverse=True)
    return results
