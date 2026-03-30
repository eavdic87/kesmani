"""
Earnings calendar integration for KešMani.

Fetches upcoming earnings dates via yfinance and caches results for
24 hours to avoid redundant API calls.

Public functions
---------------
fetch_earnings_dates(tickers)       → dict mapping ticker → ISO date or None
get_days_to_earnings(ticker)        → int or None
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

from config.settings import CACHE_DIR

logger = logging.getLogger(__name__)

_EARNINGS_CACHE_FILE = CACHE_DIR / "earnings_dates.json"
_EARNINGS_CACHE_TTL_HOURS = 24


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _load_earnings_cache() -> dict:
    """Load cached earnings dates, returning an empty dict if expired/missing."""
    if not _EARNINGS_CACHE_FILE.exists():
        return {}
    try:
        age_hours = (time.time() - _EARNINGS_CACHE_FILE.stat().st_mtime) / 3600
        if age_hours > _EARNINGS_CACHE_TTL_HOURS:
            return {}
        with open(_EARNINGS_CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_earnings_cache(data: dict) -> None:
    """Persist earnings dates to the cache file."""
    _EARNINGS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_EARNINGS_CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_earnings_dates(tickers: list[str]) -> dict[str, Optional[str]]:
    """
    Return the next earnings date for each ticker.

    Results are cached for 24 hours.

    Parameters
    ----------
    tickers:
        List of equity symbols.

    Returns
    -------
    Dict mapping ticker → ISO date string (e.g. ``"2026-04-25"``) or ``None``
    if no upcoming earnings date is available.
    """
    cache = _load_earnings_cache()
    result: dict[str, Optional[str]] = {}
    missing: list[str] = []

    for ticker in tickers:
        if ticker in cache:
            result[ticker] = cache[ticker]
        else:
            missing.append(ticker)

    if missing:
        import yfinance as yf
        for ticker in missing:
            date_str: Optional[str] = None
            try:
                t = yf.Ticker(ticker)
                cal = t.calendar
                if cal is not None and not cal.empty:
                    # yfinance returns a DataFrame; Earnings Date is a column
                    if "Earnings Date" in cal.columns:
                        ed = cal["Earnings Date"].iloc[0]
                    elif "Earnings Date" in cal.index:
                        ed = cal.loc["Earnings Date"].iloc[0]
                    else:
                        ed = None
                    if ed is not None:
                        import pandas as pd
                        ed_ts = pd.Timestamp(ed)
                        date_str = ed_ts.strftime("%Y-%m-%d")
            except Exception as exc:
                logger.debug("Earnings date fetch failed for %s: %s", ticker, exc)
            result[ticker] = date_str
            cache[ticker] = date_str

        _save_earnings_cache(cache)

    return result


def get_days_to_earnings(ticker: str) -> Optional[int]:
    """
    Return the number of calendar days until the next earnings date.

    Returns ``None`` if no earnings date is available.
    Returns 0 if today is the earnings date.
    Returns negative numbers if earnings have already passed.
    """
    from datetime import date
    dates = fetch_earnings_dates([ticker])
    date_str = dates.get(ticker)
    if not date_str:
        return None
    try:
        earnings_date = date.fromisoformat(date_str)
        return (earnings_date - date.today()).days
    except Exception:
        return None
