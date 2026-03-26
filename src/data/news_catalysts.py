"""
News & catalyst module for Kesmani.

Fetches upcoming earnings dates for watchlist stocks via yfinance's
calendar features and maintains a static economic calendar with
high-impact macro events.  No external API keys required.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

from config.settings import DATA_SETTINGS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static economic calendar
# (Updated manually — key recurring events that move markets)
# ---------------------------------------------------------------------------

# This calendar lists event names and their *typical* monthly cadence.
# The system flags whenever one falls within the next 7 days based on
# approximate recurrence rules.
ECONOMIC_EVENTS: list[dict] = [
    {"name": "FOMC Interest Rate Decision", "description": "Federal Reserve rate decision — high volatility event"},
    {"name": "CPI (Consumer Price Index)", "description": "Inflation reading — key for rate expectations"},
    {"name": "Non-Farm Payrolls (NFP)", "description": "Jobs report — first Friday of each month"},
    {"name": "GDP (Advance Estimate)", "description": "Economic growth — quarterly release"},
    {"name": "PCE Price Index", "description": "Fed's preferred inflation gauge"},
    {"name": "ISM Manufacturing PMI", "description": "Manufacturing health indicator"},
    {"name": "Retail Sales", "description": "Consumer spending indicator"},
    {"name": "Initial Jobless Claims", "description": "Weekly labor market health"},
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_earnings_calendar(ticker: str) -> Optional[dict]:
    """
    Fetch the next earnings date for a single ticker.

    Parameters
    ----------
    ticker:
        Equity symbol (e.g. "AAPL").

    Returns
    -------
    Dict with keys: ticker, earnings_date, days_until, warning.
    Returns None if no upcoming earnings date is available.
    """
    try:
        t = yf.Ticker(ticker)
        cal = t.calendar
        if cal is None or cal.empty:
            return None

        # calendar columns: 'Earnings Date', 'Earnings Average', etc.
        if "Earnings Date" in cal.index:
            raw_date = cal.loc["Earnings Date"].iloc[0] if hasattr(cal.loc["Earnings Date"], "iloc") else cal.loc["Earnings Date"]
            earnings_date = pd.to_datetime(raw_date).to_pydatetime().replace(tzinfo=None)
        else:
            return None

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        days_until = (earnings_date - today).days
        warning = 0 <= days_until <= DATA_SETTINGS["earnings_warning_days"]

        return {
            "ticker": ticker,
            "earnings_date": earnings_date,
            "days_until": days_until,
            "warning": warning,
        }
    except Exception as exc:
        logger.debug("Earnings calendar fetch failed for %s: %s", ticker, exc)
        return None


def fetch_all_earnings(tickers: list[str]) -> list[dict]:
    """
    Fetch upcoming earnings for a list of tickers.

    Returns
    -------
    List of earnings dicts sorted by earnings_date ascending.
    Only includes tickers with known upcoming dates.
    """
    results: list[dict] = []
    for ticker in tickers:
        entry = fetch_earnings_calendar(ticker)
        if entry and entry["days_until"] >= 0:
            results.append(entry)
    return sorted(results, key=lambda x: x["earnings_date"])


def get_upcoming_catalysts(
    tickers: list[str],
    days_ahead: int = 14,
) -> dict:
    """
    Return a combined catalyst report for the next N days.

    Parameters
    ----------
    tickers:
        List of equity symbols to check for earnings.
    days_ahead:
        Number of calendar days to look ahead.

    Returns
    -------
    Dict with keys:
        earnings  — list of earnings entries within window
        warnings  — list of tickers with earnings within 7 days (⚠️)
        economic  — static list of economic event descriptions
    """
    all_earnings = fetch_all_earnings(tickers)
    window_earnings = [e for e in all_earnings if 0 <= e["days_until"] <= days_ahead]
    warnings = [e for e in window_earnings if e["warning"]]

    return {
        "earnings": window_earnings,
        "warnings": warnings,
        "economic": ECONOMIC_EVENTS,
        "as_of": datetime.now(),
    }
