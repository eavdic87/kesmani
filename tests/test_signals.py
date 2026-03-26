"""
Unit tests for the signal generation module.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from src.analysis.signals import (
    generate_signal,
    generate_all_signals,
    _classify_signal,
    _calculate_levels,
    _build_reasoning,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_strong_buy_result(ticker: str = "NVDA") -> dict:
    return {
        "ticker": ticker,
        "composite_score": 85.0,
        "indicators": {
            "current_price": 150.0,
            "rsi": 55.0,
            "macd_crossover": "bullish_crossover",
            "trend": "BULLISH",
            "sma_50": 140.0,
            "sma_200": 120.0,
            "atr": 4.0,
            "support": 142.0,
            "volume_ratio": 1.8,
        },
        "fundamentals": {},
    }


def make_avoid_result(ticker: str = "BAD") -> dict:
    return {
        "ticker": ticker,
        "composite_score": 30.0,
        "indicators": {
            "current_price": 50.0,
            "rsi": 22.0,
            "macd_crossover": "bearish_crossover",
            "trend": "BEARISH",
            "sma_50": 55.0,
            "sma_200": 60.0,
            "atr": 2.0,
            "support": 48.0,
            "volume_ratio": 0.6,
        },
        "fundamentals": {},
    }


# ---------------------------------------------------------------------------
# classify_signal tests
# ---------------------------------------------------------------------------

class TestClassifySignal:
    def test_strong_buy_all_conditions(self):
        sig = _classify_signal(
            composite=85,
            rsi=55,
            macd_cross="bullish_crossover",
            trend="BULLISH",
            price=150,
            sma50=140,
            sma200=120,
            vol_ratio=1.5,
            thresholds={
                "strong_buy_min_score": 80,
                "buy_min_score": 65,
                "avoid_max_score": 40,
                "strong_buy_max_rsi": 60,
                "sell_rsi": 75,
            },
        )
        assert sig == "STRONG BUY"

    def test_buy_signal(self):
        sig = _classify_signal(
            composite=70,
            rsi=58,
            macd_cross="none",
            trend="BULLISH",
            price=100,
            sma50=95,
            sma200=85,
            vol_ratio=1.0,
            thresholds={
                "strong_buy_min_score": 80,
                "buy_min_score": 65,
                "avoid_max_score": 40,
                "strong_buy_max_rsi": 60,
                "sell_rsi": 75,
            },
        )
        assert sig == "BUY"

    def test_avoid_low_score(self):
        sig = _classify_signal(
            composite=35,
            rsi=45,
            macd_cross="none",
            trend="BEARISH",
            price=50,
            sma50=55,
            sma200=60,
            vol_ratio=0.8,
            thresholds={
                "strong_buy_min_score": 80,
                "buy_min_score": 65,
                "avoid_max_score": 40,
                "strong_buy_max_rsi": 60,
                "sell_rsi": 75,
            },
        )
        assert sig == "AVOID"

    def test_hold_middle_case(self):
        sig = _classify_signal(
            composite=55,
            rsi=50,
            macd_cross="none",
            trend="NEUTRAL",
            price=100,
            sma50=98,
            sma200=90,
            vol_ratio=1.0,
            thresholds={
                "strong_buy_min_score": 80,
                "buy_min_score": 65,
                "avoid_max_score": 40,
                "strong_buy_max_rsi": 60,
                "sell_rsi": 75,
            },
        )
        assert sig == "HOLD"

    def test_overbought_does_not_trigger_strong_buy(self):
        sig = _classify_signal(
            composite=85,
            rsi=72,  # overbought — above strong_buy_max_rsi
            macd_cross="bullish_crossover",
            trend="BULLISH",
            price=150,
            sma50=140,
            sma200=120,
            vol_ratio=1.5,
            thresholds={
                "strong_buy_min_score": 80,
                "buy_min_score": 65,
                "avoid_max_score": 40,
                "strong_buy_max_rsi": 60,
                "sell_rsi": 75,
            },
        )
        assert sig != "STRONG BUY"


# ---------------------------------------------------------------------------
# calculate_levels tests
# ---------------------------------------------------------------------------

class TestCalculateLevels:
    def test_entry_is_current_price(self):
        entry, stop, t1, t2 = _calculate_levels("BUY", 100.0, 3.0, 92.0, 2.0)
        assert entry == pytest.approx(100.0)

    def test_stop_below_entry(self):
        entry, stop, t1, t2 = _calculate_levels("BUY", 100.0, 3.0, 92.0, 2.0)
        assert stop < entry

    def test_targets_above_entry(self):
        entry, stop, t1, t2 = _calculate_levels("BUY", 100.0, 3.0, 92.0, 2.0)
        assert t1 > entry
        assert t2 > t1

    def test_target2_further_than_target1(self):
        entry, stop, t1, t2 = _calculate_levels("BUY", 100.0, 3.0, 92.0, 2.0)
        assert t2 > t1

    def test_no_atr_fallback_stop(self):
        entry, stop, t1, t2 = _calculate_levels("BUY", 100.0, None, None, 2.0)
        assert stop == pytest.approx(95.0, abs=0.1)  # 5% fallback

    def test_zero_price_returns_none(self):
        entry, stop, t1, t2 = _calculate_levels("BUY", 0.0, None, None, 2.0)
        assert entry is None


# ---------------------------------------------------------------------------
# generate_signal integration tests
# ---------------------------------------------------------------------------

class TestGenerateSignal:
    def test_strong_buy_result(self):
        result = generate_signal(make_strong_buy_result(), account_size=1000)
        assert result["signal"] == "STRONG BUY"
        assert result["entry"] is not None
        assert result["stop_loss"] is not None
        assert result["target_1"] is not None
        assert result["rr_ratio"] is not None
        assert result["rr_ratio"] > 0

    def test_avoid_result(self):
        result = generate_signal(make_avoid_result(), account_size=1000)
        assert result["signal"] == "AVOID"

    def test_position_shares_positive(self):
        result = generate_signal(make_strong_buy_result(), account_size=1000)
        assert result["position_shares"] >= 0

    def test_risk_amount_is_two_percent(self):
        result = generate_signal(make_strong_buy_result(), account_size=1000)
        assert result["risk_amount"] == pytest.approx(20.0, abs=0.01)  # 2% of $1000

    def test_reasoning_non_empty(self):
        result = generate_signal(make_strong_buy_result(), account_size=1000)
        assert len(result.get("reasoning", "")) > 0

    def test_ticker_preserved(self):
        result = generate_signal(make_strong_buy_result("AAPL"), account_size=1000)
        assert result["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# generate_all_signals tests
# ---------------------------------------------------------------------------

class TestGenerateAllSignals:
    def test_sorted_by_score(self):
        results = [
            make_strong_buy_result("A"),   # score 85
            make_avoid_result("B"),         # score 30
        ]
        results[0]["composite_score"] = 85.0
        results[1]["composite_score"] = 30.0
        signals = generate_all_signals(results, 1000)
        assert signals[0]["composite_score"] >= signals[1]["composite_score"]

    def test_all_tickers_present(self):
        results = [make_strong_buy_result("X"), make_avoid_result("Y")]
        signals = generate_all_signals(results, 1000)
        tickers = {s["ticker"] for s in signals}
        assert "X" in tickers
        assert "Y" in tickers
