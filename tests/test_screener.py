"""
Unit tests for the stock screener module.

Uses mock data to avoid network calls.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from src.analysis.screener import (
    _trend_score,
    _momentum_score,
    _volume_score,
    run_screener,
    _empty_score,
    score_ticker,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_trending_up_indicators() -> dict:
    return {
        "current_price": 200.0,
        "sma_20": 190.0,
        "sma_50": 180.0,
        "sma_100": 170.0,
        "sma_200": 150.0,
        "ema_9": 195.0,
        "ema_21": 185.0,
        "rsi": 55.0,
        "rsi_overbought": False,
        "rsi_oversold": False,
        "macd": 1.5,
        "macd_signal": 1.0,
        "macd_histogram": 0.5,
        "macd_crossover": "bullish_crossover",
        "bb_upper": 210.0,
        "bb_lower": 185.0,
        "bb_percent_b": 0.6,
        "bb_squeeze": False,
        "atr": 3.5,
        "volume_ratio": 1.8,
        "support": 185.0,
        "resistance": 215.0,
        "trend": "BULLISH",
    }


def make_trending_down_indicators() -> dict:
    ind = make_trending_up_indicators()
    ind.update(
        {
            "current_price": 100.0,
            "sma_20": 110.0,
            "sma_50": 120.0,
            "sma_200": 140.0,
            "rsi": 25.0,
            "rsi_oversold": True,
            "macd_crossover": "bearish_crossover",
            "volume_ratio": 0.6,
            "trend": "BEARISH",
        }
    )
    return ind


# ---------------------------------------------------------------------------
# Trend score tests
# ---------------------------------------------------------------------------

class TestTrendScore:
    def test_bullish_trend_high_score(self):
        score = _trend_score(make_trending_up_indicators())
        assert score >= 70.0

    def test_bearish_trend_low_score(self):
        score = _trend_score(make_trending_down_indicators())
        assert score <= 40.0

    def test_empty_indicators_returns_neutral(self):
        score = _trend_score({})
        assert score == 50.0

    def test_score_within_bounds(self):
        for _ in range(50):
            indicators = make_trending_up_indicators()
            indicators["sma_50"] = np.random.uniform(80, 220)
            score = _trend_score(indicators)
            assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# Momentum score tests
# ---------------------------------------------------------------------------

class TestMomentumScore:
    def test_ideal_rsi_high_momentum(self):
        ind = make_trending_up_indicators()
        ind["rsi"] = 55.0  # ideal range 40-65
        score = _momentum_score(ind)
        assert score >= 70.0

    def test_overbought_rsi_lower_score(self):
        ind = make_trending_up_indicators()
        ind["rsi"] = 80.0
        score = _momentum_score(ind)
        assert score < _momentum_score({**ind, "rsi": 55.0})

    def test_bearish_crossover_penalises(self):
        ind = make_trending_up_indicators()
        ind["macd_crossover"] = "bearish_crossover"
        bearish_score = _momentum_score(ind)
        ind["macd_crossover"] = "bullish_crossover"
        bullish_score = _momentum_score(ind)
        assert bullish_score > bearish_score

    def test_score_within_bounds(self):
        for _ in range(30):
            ind = make_trending_up_indicators()
            ind["rsi"] = np.random.uniform(0, 100)
            score = _momentum_score(ind)
            assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# Volume score tests
# ---------------------------------------------------------------------------

class TestVolumeScore:
    def test_high_volume_ratio_raises_score(self):
        ind = make_trending_up_indicators()
        ind["volume_ratio"] = 2.5
        high_vol_score = _volume_score(ind)
        ind["volume_ratio"] = 0.8
        low_vol_score = _volume_score(ind)
        assert high_vol_score > low_vol_score

    def test_bb_squeeze_bonus(self):
        ind = make_trending_up_indicators()
        ind["bb_squeeze"] = True
        squeezed_score = _volume_score(ind)
        ind["bb_squeeze"] = False
        no_squeeze_score = _volume_score(ind)
        assert squeezed_score >= no_squeeze_score

    def test_score_within_bounds(self):
        for _ in range(30):
            ind = make_trending_up_indicators()
            ind["volume_ratio"] = np.random.uniform(0, 5)
            score = _volume_score(ind)
            assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# Empty score test
# ---------------------------------------------------------------------------

class TestEmptyScore:
    def test_returns_zeros(self):
        result = _empty_score("TEST")
        assert result["ticker"] == "TEST"
        assert result["composite_score"] == 0.0
        assert result["indicators"] == {}


# ---------------------------------------------------------------------------
# run_screener integration (mocked)
# ---------------------------------------------------------------------------

class TestRunScreener:
    @patch("src.analysis.screener.fetch_ohlcv")
    @patch("src.analysis.screener.fetch_fundamentals")
    def test_screener_returns_sorted_list(self, mock_fund, mock_ohlcv):
        """run_screener should return tickers sorted by composite_score desc."""
        n = 300
        np.random.seed(0)
        prices = 100 + np.cumsum(np.random.normal(0.3, 1.5, n))
        df = pd.DataFrame(
            {
                "Open": prices * 0.99,
                "High": prices * 1.02,
                "Low": prices * 0.98,
                "Close": prices,
                "Volume": np.random.randint(1_000_000, 5_000_000, n).astype(float),
            },
            index=pd.date_range("2023-01-01", periods=n, freq="D"),
        )
        mock_ohlcv.return_value = df
        mock_fund.return_value = {
            "ticker": "X",
            "pe_ratio": 20,
            "forward_pe": 18,
            "peg_ratio": 1.2,
            "eps_growth_yoy": 0.25,
            "revenue_growth": 0.20,
            "profit_margin": 0.15,
        }

        results = run_screener(["AAPL", "MSFT", "NVDA"])
        assert len(results) == 3
        # Sorted descending
        scores = [r["composite_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    @patch("src.analysis.screener.fetch_ohlcv")
    def test_screener_handles_empty_data(self, mock_ohlcv):
        """Screener should not crash when data is missing."""
        mock_ohlcv.return_value = pd.DataFrame()
        results = run_screener(["BAD_TICKER"])
        assert len(results) == 1
        assert results[0]["composite_score"] == 0.0
