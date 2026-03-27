"""
Unit tests for the KešMani DataProvider abstraction layer.
"""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import pytest

from src.data.data_provider import DataProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_df(rows: int = 100, zero_vol_rows: int = 0) -> pd.DataFrame:
    """Build a synthetic OHLCV DataFrame."""
    idx = pd.date_range("2024-01-01", periods=rows, freq="B")
    df = pd.DataFrame(
        {
            "Open": [100.0] * rows,
            "High": [105.0] * rows,
            "Low": [95.0] * rows,
            "Close": [102.0] * rows,
            "Volume": [1_000_000] * rows,
        },
        index=idx,
    )
    if zero_vol_rows:
        df.loc[df.index[:zero_vol_rows], "Volume"] = 0
    return df


# ---------------------------------------------------------------------------
# Tests: validate_data
# ---------------------------------------------------------------------------

class TestValidateData:
    def setup_method(self):
        self.dp = DataProvider()

    def test_valid_df_returns_true(self):
        df = _make_df(100)
        is_valid, warnings = self.dp.validate_data(df, "AAPL")
        assert is_valid is True
        assert warnings == []

    def test_empty_df_returns_false(self):
        is_valid, warnings = self.dp.validate_data(pd.DataFrame(), "AAPL")
        assert is_valid is False
        assert len(warnings) > 0

    def test_none_returns_false(self):
        is_valid, warnings = self.dp.validate_data(None, "AAPL")
        assert is_valid is False

    def test_missing_close_column_returns_false(self):
        df = _make_df(100).drop(columns=["Close"])
        is_valid, warnings = self.dp.validate_data(df, "AAPL")
        assert is_valid is False

    def test_nan_close_produces_warning(self):
        df = _make_df(100)
        df.loc[df.index[0], "Close"] = float("nan")
        is_valid, warnings = self.dp.validate_data(df, "AAPL")
        assert is_valid is False  # NaN in Close → invalid
        assert any("NaN" in w for w in warnings)

    def test_excessive_zero_volume_produces_warning(self):
        df = _make_df(100, zero_vol_rows=10)  # 10% zero vol
        _, warnings = self.dp.validate_data(df, "AAPL")
        assert any("zero-volume" in w for w in warnings)

    def test_duplicate_dates_produces_warning(self):
        df = _make_df(100)
        # Manually duplicate first two index entries
        df2 = pd.concat([df.iloc[:1], df])
        _, warnings = self.dp.validate_data(df2, "AAPL")
        assert any("Duplicate" in w for w in warnings)

    def test_large_price_move_produces_warning(self):
        df = _make_df(50)
        # Set last price to 2x the previous
        df.iloc[-1, df.columns.get_loc("Close")] = 204.0  # 100% jump
        _, warnings = self.dp.validate_data(df, "AAPL")
        assert any("Price moved" in w for w in warnings)


# ---------------------------------------------------------------------------
# Tests: get_data_quality_score
# ---------------------------------------------------------------------------

class TestGetDataQualityScore:
    def setup_method(self):
        self.dp = DataProvider()

    def test_perfect_data_scores_100(self):
        df = _make_df(100)
        score = self.dp.get_data_quality_score(df, "AAPL")
        assert score == 100

    def test_empty_df_scores_0(self):
        score = self.dp.get_data_quality_score(pd.DataFrame(), "AAPL")
        assert score == 0

    def test_score_is_bounded(self):
        df = _make_df(100)
        score = self.dp.get_data_quality_score(df, "AAPL")
        assert 0 <= score <= 100


# ---------------------------------------------------------------------------
# Tests: is_data_fresh
# ---------------------------------------------------------------------------

class TestIsDataFresh:
    def setup_method(self):
        self.dp = DataProvider()

    def test_no_cache_returns_false(self):
        assert self.dp.is_data_fresh("AAPL") is False

    def test_fresh_entry_returns_true(self):
        self.dp._price_cache["AAPL"] = {
            "price": 150.0,
            "timestamp": datetime.now(timezone.utc),
        }
        assert self.dp.is_data_fresh("AAPL", max_age_minutes=30) is True

    def test_stale_entry_returns_false(self):
        old_ts = datetime.now(timezone.utc) - timedelta(minutes=60)
        self.dp._price_cache["MSFT"] = {"price": 300.0, "timestamp": old_ts}
        assert self.dp.is_data_fresh("MSFT", max_age_minutes=30) is False


# ---------------------------------------------------------------------------
# Tests: is_market_open
# ---------------------------------------------------------------------------

class TestIsMarketOpen:
    def setup_method(self):
        self.dp = DataProvider()

    def test_weekday_market_hours_returns_true(self):
        """Mock a Tuesday 10:00 AM ET — should return True."""
        import pytz
        import datetime as _dt
        et = pytz.timezone("America/New_York")
        mock_now = MagicMock()
        mock_now.weekday.return_value = 1  # Tuesday
        mock_now.time.return_value = _dt.time(10, 0)
        mock_now.month = 6
        mock_now.day = 15
        with patch("src.data.data_provider.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            result = self.dp.is_market_open()
        assert result is True

    def test_returns_bool(self):
        result = self.dp.is_market_open()
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Tests: fetch_ohlcv (mocked)
# ---------------------------------------------------------------------------

class TestFetchOhlcv:
    def setup_method(self):
        self.dp = DataProvider()

    @patch("src.data.data_provider.DataProvider._yfinance_fetch")
    def test_routes_to_yfinance(self, mock_fetch):
        mock_fetch.return_value = _make_df(100)
        result = self.dp.fetch_ohlcv("AAPL")
        mock_fetch.assert_called_once_with("AAPL", "1y")
        assert not result.empty

    def test_unknown_provider_returns_empty(self):
        dp = DataProvider(provider="unknown_provider")
        result = dp.fetch_ohlcv("AAPL")
        assert result.empty


# ---------------------------------------------------------------------------
# Tests: get_provider
# ---------------------------------------------------------------------------

class TestGetProvider:
    def test_returns_data_provider_instance(self):
        from src.data.data_provider import get_provider
        p = get_provider()
        assert isinstance(p, DataProvider)
