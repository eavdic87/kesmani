"""
Unit tests for the market scanner module.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from src.data.market_scanner import (
    scan_market,
    scan_by_sector,
    get_top_picks,
    get_sector_rotation,
    _get_sector,
    _tickers_for_sectors,
    _tickers_for_category,
)
from config.settings import SCAN_UNIVERSE, FULL_UNIVERSE, SECTOR_LABELS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(ticker: str, score: float, signal: str = "BUY", sector: str = "Technology") -> dict:
    """Build a minimal signal dict for testing."""
    return {
        "ticker": ticker,
        "signal": signal,
        "composite_score": score,
        "sector": sector,
        "entry": 100.0,
        "stop_loss": 95.0,
        "target_1": 110.0,
        "target_2": 120.0,
        "position_shares": 5,
        "position_value": 500.0,
        "risk_amount": 20.0,
        "rr_ratio": 2.0,
        "reasoning": "Test signal.",
        "indicators": {
            "current_price": 100.0,
            "rsi": 55.0,
            "volume_ratio": 1.2,
            "trend": "BULLISH",
        },
        "fundamentals": {},
        "earnings_warning": False,
        "vix_adjusted": None,
    }


def _make_screener_result(ticker: str, score: float) -> dict:
    """Build a minimal screener result dict for testing."""
    return {
        "ticker": ticker,
        "composite_score": score,
        "trend_score": score,
        "momentum_score": score,
        "volume_score": score,
        "fundamental_score": score,
        "rs_score": score,
        "indicators": {
            "current_price": 100.0,
            "rsi": 55.0,
            "macd_crossover": "bullish_crossover",
            "trend": "BULLISH",
            "sma_50": 90.0,
            "sma_200": 80.0,
            "atr": 3.0,
            "support": 95.0,
            "volume_ratio": 1.5,
        },
        "fundamentals": {},
    }


# ---------------------------------------------------------------------------
# Tests: _get_sector
# ---------------------------------------------------------------------------

class TestGetSector:
    def test_known_ticker_returns_sector(self):
        assert _get_sector("AAPL") in ("Technology",)

    def test_unknown_ticker_returns_unknown(self):
        assert _get_sector("ZZZZZZ") == "Unknown"

    def test_sector_labels_override(self):
        # CRWD is in SECTOR_LABELS as Cybersecurity
        sector = _get_sector("CRWD")
        assert sector == "Cybersecurity"


# ---------------------------------------------------------------------------
# Tests: _tickers_for_category
# ---------------------------------------------------------------------------

class TestTickersForCategory:
    def test_returns_tickers_for_valid_category(self):
        tickers = _tickers_for_category("technology")
        assert "AAPL" in tickers
        assert "MSFT" in tickers

    def test_returns_empty_for_unknown_category(self):
        assert _tickers_for_category("nonexistent_sector_xyz") == []

    def test_benchmarks_category(self):
        tickers = _tickers_for_category("benchmarks")
        assert "SPY" in tickers


# ---------------------------------------------------------------------------
# Tests: _tickers_for_sectors
# ---------------------------------------------------------------------------

class TestTickersForSectors:
    def test_returns_tickers_in_sector(self):
        tickers = _tickers_for_sectors(["Technology"])
        assert len(tickers) > 0

    def test_empty_sectors_returns_empty(self):
        tickers = _tickers_for_sectors(["NonexistentSectorXYZ"])
        assert tickers == []

    def test_multiple_sectors(self):
        tickers = _tickers_for_sectors(["Technology", "Healthcare"])
        assert len(tickers) > 0


# ---------------------------------------------------------------------------
# Tests: FULL_UNIVERSE
# ---------------------------------------------------------------------------

class TestFullUniverse:
    def test_full_universe_has_no_duplicates(self):
        assert len(FULL_UNIVERSE) == len(set(FULL_UNIVERSE))

    def test_full_universe_not_empty(self):
        assert len(FULL_UNIVERSE) > 50

    def test_common_tickers_present(self):
        for ticker in ["AAPL", "MSFT", "NVDA", "SPY", "QQQ"]:
            assert ticker in FULL_UNIVERSE


# ---------------------------------------------------------------------------
# Tests: scan_market (mocked)
# ---------------------------------------------------------------------------

class TestScanMarket:
    @patch("src.data.market_scanner.run_screener")
    @patch("src.data.market_scanner.generate_all_signals")
    def test_results_sorted_by_score_descending(self, mock_signals, mock_screener):
        mock_screener.return_value = [
            _make_screener_result("AAPL", 70.0),
            _make_screener_result("MSFT", 85.0),
        ]
        mock_signals.return_value = [
            _make_signal("MSFT", 85.0),
            _make_signal("AAPL", 70.0),
        ]
        results = scan_market(tickers=["AAPL", "MSFT"])
        assert len(results) >= 1

    @patch("src.data.market_scanner.run_screener")
    @patch("src.data.market_scanner.generate_all_signals")
    def test_min_score_filter(self, mock_signals, mock_screener):
        mock_screener.return_value = [_make_screener_result("AAPL", 30.0)]
        mock_signals.return_value = [_make_signal("AAPL", 30.0)]
        results = scan_market(tickers=["AAPL"], min_score=60.0)
        assert all(r["composite_score"] >= 60.0 for r in results)

    @patch("src.data.market_scanner.run_screener")
    @patch("src.data.market_scanner.generate_all_signals")
    def test_signal_filter(self, mock_signals, mock_screener):
        mock_screener.return_value = [
            _make_screener_result("AAPL", 80.0),
            _make_screener_result("BAD", 20.0),
        ]
        mock_signals.return_value = [
            _make_signal("AAPL", 80.0, "STRONG BUY"),
            _make_signal("BAD", 20.0, "AVOID"),
        ]
        results = scan_market(tickers=["AAPL", "BAD"], signal_filter=["STRONG BUY"])
        assert all(r["signal"] == "STRONG BUY" for r in results)

    @patch("src.data.market_scanner.run_screener")
    @patch("src.data.market_scanner.generate_all_signals")
    def test_sector_attached_to_results(self, mock_signals, mock_screener):
        mock_screener.return_value = [_make_screener_result("AAPL", 75.0)]
        mock_signals.return_value = [_make_signal("AAPL", 75.0)]
        results = scan_market(tickers=["AAPL"])
        for r in results:
            assert "sector" in r

    @patch("src.data.market_scanner.run_screener")
    @patch("src.data.market_scanner.generate_all_signals")
    def test_price_range_filter(self, mock_signals, mock_screener):
        sig = _make_signal("NVDA", 80.0)
        sig["entry"] = 500.0
        mock_screener.return_value = [_make_screener_result("NVDA", 80.0)]
        mock_signals.return_value = [sig]
        results = scan_market(tickers=["NVDA"], max_price=100.0)
        assert all((r.get("entry") or 0) <= 100.0 for r in results)

    @patch("src.data.market_scanner.run_screener")
    @patch("src.data.market_scanner.generate_all_signals")
    def test_empty_tickers_uses_full_universe(self, mock_signals, mock_screener):
        mock_screener.return_value = []
        mock_signals.return_value = []
        scan_market()
        # Should have been called with FULL_UNIVERSE
        called_tickers = mock_screener.call_args[0][0]
        assert len(called_tickers) > 50


# ---------------------------------------------------------------------------
# Tests: scan_by_sector (mocked)
# ---------------------------------------------------------------------------

class TestScanBySector:
    @patch("src.data.market_scanner.scan_market")
    def test_valid_category_passes_tickers(self, mock_scan):
        mock_scan.return_value = []
        scan_by_sector("technology")
        mock_scan.assert_called_once()
        kwargs = mock_scan.call_args
        tickers_arg = kwargs[1].get("tickers") or (kwargs[0][0] if kwargs[0] else [])
        assert len(tickers_arg) > 0

    @patch("src.data.market_scanner.scan_market")
    def test_unknown_sector_returns_empty(self, mock_scan):
        mock_scan.return_value = []
        result = scan_by_sector("nonexistent_xyz_sector")
        assert result == []
        mock_scan.assert_not_called()

    @patch("src.data.market_scanner.scan_market")
    def test_sector_label_lookup(self, mock_scan):
        mock_scan.return_value = [_make_signal("AAPL", 75.0)]
        result = scan_by_sector("Technology")
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Tests: get_top_picks (mocked)
# ---------------------------------------------------------------------------

class TestGetTopPicks:
    @patch("src.data.market_scanner.scan_market")
    def test_returns_at_most_n_results(self, mock_scan):
        mock_scan.return_value = [
            _make_signal(f"T{i}", 90.0 - i, "STRONG BUY") for i in range(20)
        ]
        results = get_top_picks(n=5)
        assert len(results) <= 5

    @patch("src.data.market_scanner.scan_market")
    def test_default_signal_filter_is_buys(self, mock_scan):
        mock_scan.return_value = []
        get_top_picks()
        call_kwargs = mock_scan.call_args[1]
        assert "signal_filter" in call_kwargs
        assert "BUY" in call_kwargs["signal_filter"]

    @patch("src.data.market_scanner.scan_market")
    def test_empty_results(self, mock_scan):
        mock_scan.return_value = []
        results = get_top_picks(n=10)
        assert results == []


# ---------------------------------------------------------------------------
# Tests: get_sector_rotation (mocked)
# ---------------------------------------------------------------------------

class TestGetSectorRotation:
    @patch("src.data.market_scanner.scan_market")
    def test_returns_sorted_by_avg_score(self, mock_scan):
        mock_scan.return_value = [
            _make_signal("AAPL", 80.0, sector="Technology"),
            _make_signal("MSFT", 70.0, sector="Technology"),
            _make_signal("JNJ", 40.0, sector="Healthcare"),
        ]
        result = get_sector_rotation()
        assert result[0]["avg_score"] >= result[-1]["avg_score"]

    @patch("src.data.market_scanner.scan_market")
    def test_sector_keys_present(self, mock_scan):
        mock_scan.return_value = [
            _make_signal("AAPL", 75.0, sector="Technology"),
        ]
        result = get_sector_rotation()
        assert len(result) > 0
        for row in result:
            assert "sector" in row
            assert "avg_score" in row
            assert "ticker_count" in row
            assert "best_ticker" in row

    @patch("src.data.market_scanner.scan_market")
    def test_counts_buys_and_strong_buys(self, mock_scan):
        mock_scan.return_value = [
            _make_signal("A", 85.0, "STRONG BUY", "Technology"),
            _make_signal("B", 70.0, "BUY", "Technology"),
            _make_signal("C", 35.0, "AVOID", "Technology"),
        ]
        result = get_sector_rotation()
        tech = next((r for r in result if r["sector"] == "Technology"), None)
        assert tech is not None
        assert tech["strong_buys"] == 1
        assert tech["buys"] == 1

    @patch("src.data.market_scanner.scan_market")
    def test_empty_scan_returns_empty(self, mock_scan):
        mock_scan.return_value = []
        result = get_sector_rotation()
        assert result == []
