"""
KešMani Data Provider — Abstraction Layer.

Currently backed by yfinance. Designed for easy swap to Alpaca or other
providers by changing the `provider` argument.

All market data fetches should go through this class so that the rest of the
codebase is insulated from the underlying API.
"""

import logging
from datetime import datetime, time as dtime, timezone
from typing import Optional

import pandas as pd
import pytz

logger = logging.getLogger(__name__)

# US Eastern timezone
_ET = pytz.timezone("America/New_York")

# US market holidays (year-agnostic month/day pairs) — fixed-date NYSE holidays only.
# Floating holidays (MLK Day, Presidents' Day, Good Friday, Memorial Day,
# Juneteenth, Labor Day, Thanksgiving) require year-aware calculation and are
# not represented here. is_market_open() is approximate for those dates.
_US_HOLIDAYS: set[tuple[int, int]] = {
    (1, 1),   # New Year's Day
    (7, 4),   # Independence Day
    (12, 25), # Christmas Day
}


class DataProvider:
    """
    Abstract interface for market data.

    Parameters
    ----------
    provider:
        Backend to use. Currently supports "yfinance".
        Future: "alpaca".
    """

    def __init__(self, provider: str = "yfinance") -> None:
        self.provider = provider
        self._price_cache: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_ohlcv(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        """
        Fetch OHLCV data for a ticker.

        Parameters
        ----------
        ticker:
            Stock symbol (e.g. "NVDA").
        period:
            Lookback period string accepted by yfinance (e.g. "1y", "6mo").

        Returns
        -------
        DataFrame with columns: Open, High, Low, Close, Volume.
        Empty DataFrame on error.
        """
        if self.provider == "yfinance":
            return self._yfinance_fetch(ticker, period)
        elif self.provider == "alpaca":
            return self._alpaca_fetch(ticker, period)
        else:
            logger.error("Unknown provider: %s", self.provider)
            return pd.DataFrame()

    def fetch_realtime_price(self, ticker: str) -> dict:
        """
        Get the latest price data for a ticker.

        Returns
        -------
        Dict with keys: price, change, change_pct, volume, timestamp.
        Empty dict on error.
        """
        if self.provider == "yfinance":
            return self._yfinance_realtime(ticker)
        return {}

    def is_data_fresh(
        self,
        ticker: str,
        max_age_minutes: int = 30,
    ) -> bool:
        """
        Check whether cached realtime price data is within the staleness threshold.

        Parameters
        ----------
        ticker:
            Stock symbol.
        max_age_minutes:
            Maximum acceptable age in minutes.

        Returns
        -------
        True if data is fresh, False if stale or absent.
        """
        entry = self._price_cache.get(ticker)
        if not entry:
            return False
        ts = entry.get("timestamp")
        if not ts:
            return False
        age_minutes = (datetime.now(timezone.utc) - ts).total_seconds() / 60
        return age_minutes < max_age_minutes

    def validate_data(
        self,
        df: pd.DataFrame,
        ticker: str,
    ) -> tuple[bool, list[str]]:
        """
        Validate OHLCV data integrity.

        Checks
        ------
        - DataFrame is not empty
        - No NaN in critical columns (Close, Volume)
        - Reasonable price range (> 0)
        - Volume > 0 on most rows
        - Dates are sequential (no duplicates)

        Returns
        -------
        (is_valid, warnings) tuple.
        """
        warnings: list[str] = []

        if df is None or df.empty:
            return False, [f"{ticker}: No data returned"]

        required_cols = {"Close", "Volume"}
        missing = required_cols - set(df.columns)
        if missing:
            return False, [f"{ticker}: Missing columns {missing}"]

        nan_close = df["Close"].isna().sum()
        if nan_close > 0:
            warnings.append(f"{ticker}: {nan_close} NaN values in Close")

        if (df["Close"] <= 0).any():
            warnings.append(f"{ticker}: Non-positive Close prices detected")

        zero_vol = (df["Volume"] == 0).sum()
        if zero_vol > len(df) * 0.05:
            warnings.append(
                f"{ticker}: {zero_vol} zero-volume rows ({zero_vol/len(df)*100:.1f}%)"
            )

        if df.index.duplicated().any():
            warnings.append(f"{ticker}: Duplicate dates in index")

        # Price sanity — flag if latest close changed >20% from prior
        if len(df) >= 2:
            latest = df["Close"].iloc[-1]
            prev = df["Close"].iloc[-2]
            if prev > 0 and abs(latest / prev - 1) > 0.20:
                warnings.append(
                    f"{ticker}: Price moved {(latest/prev - 1)*100:.1f}% — verify manually"
                )

        is_valid = bool(len(df) >= 20 and nan_close == 0 and not (df["Close"] <= 0).any())
        return is_valid, warnings

    def get_data_quality_score(
        self,
        df: pd.DataFrame,
        ticker: str,
    ) -> int:
        """
        Return a data quality score from 0–100.

        100 = perfect data, 0 = completely unusable.
        """
        if df is None or df.empty:
            return 0

        score = 100
        is_valid, warnings = self.validate_data(df, ticker)

        if not is_valid:
            score -= 50

        score -= len(warnings) * 10
        score = max(0, min(100, score))
        return score

    def is_market_open(self) -> bool:
        """
        Check whether the US equity market is currently open.

        Accounts for weekends, standard market hours (9:30–16:00 ET),
        and major US holidays (approximate).

        Returns
        -------
        True during regular market hours on trading days.
        """
        now_et = datetime.now(_ET)

        # Weekend check
        if now_et.weekday() >= 5:
            return False

        # Holiday check (approximate — month/day only)
        if (now_et.month, now_et.day) in _US_HOLIDAYS:
            return False

        # Market hours 9:30 – 16:00 ET
        market_open = dtime(9, 30)
        market_close = dtime(16, 0)
        return market_open <= now_et.time() < market_close

    # ------------------------------------------------------------------
    # Private — yfinance backend
    # ------------------------------------------------------------------

    def _yfinance_fetch(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        """Fetch OHLCV from yfinance with error handling."""
        try:
            import yfinance as yf  # type: ignore[import]

            t = yf.Ticker(ticker)
            df = t.history(period=period, auto_adjust=True)
            if df.empty:
                logger.warning("yfinance returned empty DataFrame for %s", ticker)
            return df
        except Exception as exc:
            logger.error("yfinance fetch failed for %s: %s", ticker, exc)
            return pd.DataFrame()

    def _yfinance_realtime(self, ticker: str) -> dict:
        """Fetch latest price snapshot from yfinance."""
        try:
            import yfinance as yf  # type: ignore[import]

            t = yf.Ticker(ticker)
            info = t.fast_info
            price = float(getattr(info, "last_price", 0) or 0)
            prev_close = float(getattr(info, "previous_close", price) or price)
            change = price - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0.0
            volume = int(getattr(info, "three_month_average_volume", 0) or 0)

            result = {
                "ticker": ticker,
                "price": price,
                "change": change,
                "change_pct": change_pct,
                "volume": volume,
                "timestamp": datetime.now(timezone.utc),
            }
            self._price_cache[ticker] = result
            return result
        except Exception as exc:
            logger.error("yfinance realtime fetch failed for %s: %s", ticker, exc)
            return {}

    # ------------------------------------------------------------------
    # Private — Alpaca backend (future)
    # ------------------------------------------------------------------

    def _alpaca_fetch(self, ticker: str, period: str = "1y") -> pd.DataFrame:  # pragma: no cover
        """
        Placeholder for Alpaca Markets data fetch.

        Swap provider="yfinance" → provider="alpaca" to use this path.
        Requires ALPACA_API_KEY and ALPACA_SECRET_KEY in environment.
        """
        raise NotImplementedError(
            "Alpaca provider not yet implemented. Set provider='yfinance'."
        )


# ---------------------------------------------------------------------------
# Module-level convenience instance (shared across imports)
# ---------------------------------------------------------------------------
_provider = DataProvider(provider="yfinance")


def get_provider() -> DataProvider:
    """Return the shared DataProvider instance."""
    return _provider
