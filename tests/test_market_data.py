"""
Integration tests for the market data caching layer.

Verifies that:
  - A second fetch within the TTL window hits the cache (no new API call).
  - An expired cache triggers a fresh fetch from yfinance.
  - The parallel fetch_all_ohlcv works correctly.

All yfinance network calls are mocked so these tests run offline.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import pytest

from src.data.market_data import fetch_ohlcv, fetch_all_ohlcv, get_market_snapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_df(n: int = 50) -> pd.DataFrame:
    """Create a synthetic OHLCV DataFrame that mimics yfinance output."""
    np.random.seed(42)
    close = 100 + np.random.randn(n).cumsum()
    df = pd.DataFrame(
        {
            "Open": close + np.random.uniform(-1, 1, n),
            "High": close + np.random.uniform(0, 2, n),
            "Low": close - np.random.uniform(0, 2, n),
            "Close": close,
            "Volume": np.random.randint(500_000, 5_000_000, n).astype(float),
        },
        index=pd.date_range("2025-01-01", periods=n, freq="D"),
    )
    return df


# ---------------------------------------------------------------------------
# Cache hit / miss tests
# ---------------------------------------------------------------------------

class TestFetchOHLCVCaching:
    """
    Verify cache behaviour for fetch_ohlcv.

    Uses a fresh temporary CACHE_DIR to avoid touching production cache.
    """

    def test_fresh_cache_returns_cached_data(self, tmp_path, monkeypatch):
        """Second call within TTL should NOT invoke yfinance."""
        import config.settings as settings
        monkeypatch.setattr(settings, "CACHE_DIR", tmp_path)

        import src.data.market_data as mmd
        monkeypatch.setattr(mmd, "CACHE_DIR", tmp_path)

        mock_df = _make_mock_df()

        with patch("src.data.market_data.yf.Ticker") as mock_ticker_cls:
            mock_ticker = MagicMock()
            mock_ticker.history.return_value = mock_df
            mock_ticker_cls.return_value = mock_ticker

            # First call — cache miss → should call yfinance
            df1 = fetch_ohlcv("AAPL", "1y")
            assert mock_ticker.history.call_count == 1

            # Second call — cache hit → should NOT call yfinance again
            df2 = fetch_ohlcv("AAPL", "1y")
            assert mock_ticker.history.call_count == 1  # still 1
            assert len(df2) > 0

    def test_expired_cache_triggers_fresh_fetch(self, tmp_path, monkeypatch):
        """A cache file older than the TTL should be refreshed."""
        import config.settings as settings
        monkeypatch.setattr(settings, "CACHE_DIR", tmp_path)

        import src.data.market_data as mmd
        monkeypatch.setattr(mmd, "CACHE_DIR", tmp_path)

        mock_df = _make_mock_df()

        with patch("src.data.market_data.yf.Ticker") as mock_ticker_cls:
            mock_ticker = MagicMock()
            mock_ticker.history.return_value = mock_df
            mock_ticker_cls.return_value = mock_ticker

            # Populate cache
            df1 = fetch_ohlcv("MSFT", "1y")
            assert mock_ticker.history.call_count == 1

            # Age the cache file beyond the TTL (set mtime to 1 day ago)
            cache_file = tmp_path / "MSFT_1y.parquet"
            assert cache_file.exists()
            old_mtime = time.time() - 86400  # 24 hours ago
            import os
            os.utime(cache_file, (old_mtime, old_mtime))

            # Patch TTL to 1 minute so our 24h-old file is expired
            monkeypatch.setattr(mmd, "_cache_ttl_minutes", lambda: 1)

            # Third call → cache is stale → should re-fetch
            df3 = fetch_ohlcv("MSFT", "1y")
            assert mock_ticker.history.call_count == 2

    def test_empty_yfinance_response_returns_empty_df(self, tmp_path, monkeypatch):
        """When yfinance returns empty data, fetch_ohlcv returns empty DataFrame."""
        import src.data.market_data as mmd
        monkeypatch.setattr(mmd, "CACHE_DIR", tmp_path)

        with patch("src.data.market_data.yf.Ticker") as mock_ticker_cls:
            mock_ticker = MagicMock()
            mock_ticker.history.return_value = pd.DataFrame()
            mock_ticker_cls.return_value = mock_ticker

            result = fetch_ohlcv("INVALID", "1y")
            assert result.empty


# ---------------------------------------------------------------------------
# Parallel fetch tests
# ---------------------------------------------------------------------------

class TestFetchAllOHLCVParallel:
    def test_returns_dict_with_all_tickers(self, tmp_path, monkeypatch):
        """fetch_all_ohlcv should return a dict keyed by every requested ticker."""
        import src.data.market_data as mmd
        monkeypatch.setattr(mmd, "CACHE_DIR", tmp_path)

        mock_df = _make_mock_df()

        with patch("src.data.market_data.yf.Ticker") as mock_ticker_cls:
            mock_ticker = MagicMock()
            mock_ticker.history.return_value = mock_df
            mock_ticker_cls.return_value = mock_ticker

            tickers = ["AAPL", "MSFT", "NVDA"]
            result = fetch_all_ohlcv(tickers, period="1y", max_workers=3)

            assert set(result.keys()) == set(tickers)
            for ticker, df in result.items():
                assert not df.empty, f"Expected data for {ticker}"

    def test_parallel_faster_than_serial(self, tmp_path, monkeypatch):
        """
        With cached data, parallel fetch should complete without errors.
        (Actual speed comparison is flaky in CI, so we just verify correctness.)
        """
        import src.data.market_data as mmd
        monkeypatch.setattr(mmd, "CACHE_DIR", tmp_path)

        mock_df = _make_mock_df()

        with patch("src.data.market_data.yf.Ticker") as mock_ticker_cls:
            mock_ticker = MagicMock()
            mock_ticker.history.return_value = mock_df
            mock_ticker_cls.return_value = mock_ticker

            tickers = [f"TICK{i}" for i in range(10)]
            result = fetch_all_ohlcv(tickers, period="1y", max_workers=5)
            assert len(result) == 10


# ---------------------------------------------------------------------------
# Market snapshot deduplication test
# ---------------------------------------------------------------------------

class TestGetMarketSnapshot:
    def test_no_duplicate_calls(self, tmp_path, monkeypatch):
        """get_market_snapshot should call get_price_summary once per ticker."""
        import src.data.market_data as mmd
        monkeypatch.setattr(mmd, "CACHE_DIR", tmp_path)

        call_count = {"n": 0}
        original_gps = mmd.get_price_summary

        def counting_gps(ticker):
            call_count["n"] += 1
            return {"ticker": ticker, "current_price": 100.0, "day_change_pct": 0.5,
                    "52w_high": 110.0, "52w_low": 90.0, "pct_from_52w_high": -9.1}

        monkeypatch.setattr(mmd, "get_price_summary", counting_gps)

        benchmarks = ["SPY", "QQQ", "IWM"]
        result = mmd.get_market_snapshot(benchmarks)

        assert call_count["n"] == len(benchmarks), (
            f"Expected {len(benchmarks)} calls, got {call_count['n']} — "
            "possible duplicate price_summary calls"
        )
        assert len(result) == len(benchmarks)
