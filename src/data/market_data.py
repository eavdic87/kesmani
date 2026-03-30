"""
Market data fetching module for KešMani.

Fetches OHLCV data via yfinance with intelligent file-based caching
to avoid hammering the API on every run.  All public functions return
pandas DataFrames or dicts — never raw yfinance objects.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

from config.settings import ALL_TICKERS, CACHE_DIR, DATA_SETTINGS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# US market holiday list (NYSE/NASDAQ) — updated for 2025 and 2026
# ---------------------------------------------------------------------------
_US_MARKET_HOLIDAYS: frozenset[date] = frozenset(
    [
        # 2025
        date(2025, 1, 1),   # New Year's Day
        date(2025, 1, 20),  # MLK Day
        date(2025, 2, 17),  # Presidents' Day
        date(2025, 4, 18),  # Good Friday
        date(2025, 5, 26),  # Memorial Day
        date(2025, 6, 19),  # Juneteenth
        date(2025, 7, 4),   # Independence Day
        date(2025, 9, 1),   # Labor Day
        date(2025, 11, 27), # Thanksgiving
        date(2025, 12, 25), # Christmas
        # 2026
        date(2026, 1, 1),   # New Year's Day
        date(2026, 1, 19),  # MLK Day
        date(2026, 2, 16),  # Presidents' Day
        date(2026, 4, 3),   # Good Friday
        date(2026, 5, 25),  # Memorial Day
        date(2026, 6, 19),  # Juneteenth
        date(2026, 7, 3),   # Independence Day (observed)
        date(2026, 9, 7),   # Labor Day
        date(2026, 11, 26), # Thanksgiving
        date(2026, 12, 25), # Christmas
    ]
)

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
    Accounts for US market holidays for 2025–2026.
    """
    try:
        import zoneinfo
        et = zoneinfo.ZoneInfo("America/New_York")
        now_et = datetime.now(et)
        if now_et.weekday() >= 5:  # Saturday or Sunday
            return False
        if now_et.date() in _US_MARKET_HOLIDAYS:
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
    max_workers: int = 10,
) -> dict[str, pd.DataFrame]:
    """
    Fetch OHLCV data for multiple tickers in parallel.

    Parameters
    ----------
    tickers:
        List of ticker symbols.  Defaults to ALL_TICKERS.
    period:
        yfinance period string.
    max_workers:
        Number of parallel threads (default 10).

    Returns
    -------
    Dict mapping ticker → DataFrame.
    """
    tickers = tickers or ALL_TICKERS
    result: dict[str, pd.DataFrame] = {}

    def _fetch(ticker: str) -> tuple[str, pd.DataFrame]:
        return ticker, fetch_ohlcv(ticker, period)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch, t): t for t in tickers}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                t, df = future.result()
                result[t] = df
            except Exception as exc:
                logger.error("Parallel fetch failed for %s: %s", ticker, exc)
                result[ticker] = pd.DataFrame()

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
    snapshots = [get_price_summary(t) for t in benchmarks]
    return [s for s in snapshots if s]


def fetch_extended_hours(ticker: str) -> dict | None:
    """
    Fetch pre-market and after-hours price data for a ticker.

    Uses yfinance's ``prepost=True`` flag on a short 5d history call.

    Returns
    -------
    Dict with keys: pre_market_price, after_hours_price, regular_close,
    or None if data is unavailable.
    """
    try:
        ticker_obj = yf.Ticker(ticker)
        df = ticker_obj.history(period="5d", prepost=True, auto_adjust=True)
        if df.empty:
            return None

        regular_df = ticker_obj.history(period="5d", auto_adjust=True)
        regular_close = float(regular_df["Close"].iloc[-1]) if not regular_df.empty else None

        last_ts = df.index[-1]
        last_price = float(df["Close"].iloc[-1])

        result: dict = {"regular_close": regular_close, "pre_market_price": None, "after_hours_price": None}
        try:
            import zoneinfo
            et = zoneinfo.ZoneInfo("America/New_York")
            last_et = last_ts.tz_convert(et) if last_ts.tzinfo else last_ts
            hour = last_et.hour
            if 4 <= hour < 9:
                result["pre_market_price"] = last_price
            elif 16 <= hour < 20:
                result["after_hours_price"] = last_price
        except Exception:
            pass

        return result
    except Exception as exc:
        logger.error("Extended hours fetch failed for %s: %s", ticker, exc)
        return None
