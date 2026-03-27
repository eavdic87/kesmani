"""
Market data fetching module for KešMani.

Fetches OHLCV data via yfinance with intelligent file-based caching
to avoid hammering the API on every run.  All public functions return
pandas DataFrames or dicts — never raw yfinance objects.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

from config.settings import ALL_TICKERS, CACHE_DIR, DATA_SETTINGS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cache_path(ticker: str, period: str) -> Path:
    """Return the file path for a given ticker/period cache entry."""
    return CACHE_DIR / f"{ticker}_{period}.parquet"


def _cache_ttl_minutes() -> int:
    """
    Return the appropriate cache TTL in minutes.

    Uses a shorter TTL during market hours (15 min) to keep data fresh,
    and a longer TTL outside market hours (60 min) to avoid unnecessary API calls.
    """
    if is_market_open():
        return 15
    return int(DATA_SETTINGS["cache_ttl_minutes"])


def _is_cache_fresh(path: Path) -> bool:
    """Return True if the cache file exists and is younger than the current TTL."""
    if not path.exists():
        return False
    age_minutes = (time.time() - path.stat().st_mtime) / 60
    return age_minutes < _cache_ttl_minutes()


def is_market_open() -> bool:
    """
    Return True if the US equity market is currently open (Mon–Fri, 09:30–16:00 ET).

    Requires Python 3.9+ (uses the standard library ``zoneinfo`` module).
    Note: Does not account for market holidays.
    """
    try:
        import zoneinfo
        et = zoneinfo.ZoneInfo("America/New_York")
        now_et = datetime.now(et)
        if now_et.weekday() >= 5:  # Saturday or Sunday
            return False
        open_time = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        close_time = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        return open_time <= now_et <= close_time
    except ImportError:
        logger.debug("zoneinfo not available (Python < 3.9) — market hours check skipped")
        return False
    except Exception:
        return False


def fetch_vix() -> Optional[float]:
    """
    Return the current VIX level (CBOE Volatility Index).

    Returns None if data is unavailable.
    """
    try:
        df = fetch_ohlcv("^VIX", period="5d")
        if df.empty:
            return None
        return float(df["Close"].iloc[-1])
    except Exception as exc:
        logger.error("Failed to fetch VIX: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_ohlcv(ticker: str, period: str = DATA_SETTINGS["default_period"]) -> pd.DataFrame:
    """
    Fetch daily OHLCV data for a single ticker.

    Parameters
    ----------
    ticker:
        Equity or ETF symbol (e.g. "NVDA").
    period:
        yfinance period string — "1y", "5y", etc.

    Returns
    -------
    DataFrame with columns [Open, High, Low, Close, Volume] indexed by Date.
    Returns an empty DataFrame if the fetch fails.
    """
    cache_file = _cache_path(ticker, period)
    if _is_cache_fresh(cache_file):
        try:
            df = pd.read_parquet(cache_file)
            logger.debug("Cache hit for %s (%s)", ticker, period)
            return df
        except Exception as exc:
            logger.warning("Cache read failed for %s: %s", ticker, exc)

    try:
        logger.info("Fetching OHLCV for %s (%s) from yfinance", ticker, period)
        ticker_obj = yf.Ticker(ticker)
        df = ticker_obj.history(period=period, auto_adjust=True)
        if df.empty:
            logger.warning("Empty data returned for %s", ticker)
            return pd.DataFrame()
        # Normalise index to date-only
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        df.to_parquet(cache_file)
        return df
    except Exception as exc:
        logger.error("Failed to fetch OHLCV for %s: %s", ticker, exc)
        return pd.DataFrame()


def fetch_all_ohlcv(
    tickers: list[str] | None = None,
    period: str = DATA_SETTINGS["default_period"],
) -> dict[str, pd.DataFrame]:
    """
    Fetch OHLCV data for multiple tickers.

    Parameters
    ----------
    tickers:
        List of ticker symbols.  Defaults to ALL_TICKERS.
    period:
        yfinance period string.

    Returns
    -------
    Dict mapping ticker → DataFrame.
    """
    tickers = tickers or ALL_TICKERS
    result: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        result[ticker] = fetch_ohlcv(ticker, period)
    return result


def get_current_price(ticker: str) -> Optional[float]:
    """
    Return the most recent closing price for a ticker.

    Falls back gracefully to None if data is unavailable.
    """
    df = fetch_ohlcv(ticker)
    if df.empty:
        return None
    return float(df["Close"].iloc[-1])


def get_price_summary(ticker: str) -> dict:
    """
    Return a snapshot dict with current price, day-change %, and 52-week range.

    Returns an empty dict on failure.
    """
    df = fetch_ohlcv(ticker)
    if df.empty or len(df) < 2:
        return {}
    try:
        current = float(df["Close"].iloc[-1])
        prev = float(df["Close"].iloc[-2])
        day_change_pct = ((current - prev) / prev) * 100
        week52_high = float(df["High"].tail(252).max())
        week52_low = float(df["Low"].tail(252).min())
        return {
            "ticker": ticker,
            "current_price": current,
            "day_change_pct": day_change_pct,
            "52w_high": week52_high,
            "52w_low": week52_low,
            "pct_from_52w_high": ((current - week52_high) / week52_high) * 100,
        }
    except Exception as exc:
        logger.error("Price summary failed for %s: %s", ticker, exc)
        return {}


def get_market_snapshot(benchmarks: list[str] | None = None) -> list[dict]:
    """
    Return price snapshots for benchmark ETFs (SPY, QQQ, IWM by default).

    Used for the market overview / regime detection.
    """
    from config.settings import BENCHMARK_TICKERS

    benchmarks = benchmarks or BENCHMARK_TICKERS
    return [get_price_summary(t) for t in benchmarks if get_price_summary(t)]
