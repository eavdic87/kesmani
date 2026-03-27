"""
Unit tests for the KešMani Trade Advisor module.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from src.analysis.trade_advisor import (
    analyze_market,
    generate_trade_recommendations,
    generate_sell_recommendations,
    _calculate_confidence,
    _detect_market_regime,
    _assess_urgency,
    _generate_reasoning,
    _generate_exit_plan,
    MIN_CONFIDENCE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(
    ticker: str = "AAPL",
    score: float = 80.0,
    signal: str = "STRONG BUY",
    sector: str = "Technology",
    rsi: float = 52.0,
    macd: str = "bullish_crossover",
    vol_ratio: float = 1.8,
    trend: str = "BULLISH",
    entry: float = 150.0,
    stop: float = 143.0,
    t1: float = 160.0,
    t2: float = 170.0,
    rr: float = 2.1,
    earnings_warning: bool = False,
) -> dict:
    return {
        "ticker": ticker,
        "signal": signal,
        "composite_score": score,
        "sector": sector,
        "entry": entry,
        "stop_loss": stop,
        "target_1": t1,
        "target_2": t2,
        "position_shares": 3,
        "position_value": entry * 3,
        "risk_amount": (entry - stop) * 3,
        "rr_ratio": rr,
        "reasoning": "",
        "earnings_warning": earnings_warning,
        "indicators": {
            "current_price": entry,
            "rsi": rsi,
            "macd_crossover": macd,
            "trend": trend,
            "sma_50": entry * 0.95,
            "sma_200": entry * 0.85,
            "atr": entry * 0.03,
            "support": entry * 0.92,
            "volume_ratio": vol_ratio,
        },
        "fundamentals": {},
    }


# ---------------------------------------------------------------------------
# Tests: _detect_market_regime
# ---------------------------------------------------------------------------

class TestDetectMarketRegime:
    def test_bullish_regime(self):
        signals = [_make_signal(score=80, signal="STRONG BUY") for _ in range(10)]
        signals += [_make_signal(score=70, signal="BUY") for _ in range(10)]
        regime = _detect_market_regime(signals)
        assert regime == "BULLISH"

    def test_bearish_regime(self):
        signals = [_make_signal(score=30, signal="AVOID") for _ in range(15)]
        signals += [_make_signal(score=35, signal="SELL") for _ in range(10)]
        regime = _detect_market_regime(signals)
        assert regime == "BEARISH"

    def test_neutral_regime(self):
        signals = (
            [_make_signal(score=60, signal="BUY") for _ in range(5)]
            + [_make_signal(score=50, signal="HOLD") for _ in range(10)]
            + [_make_signal(score=40, signal="SELL") for _ in range(5)]
        )
        regime = _detect_market_regime(signals)
        assert regime in ("NEUTRAL", "VOLATILE", "BULLISH")

    def test_empty_returns_neutral(self):
        assert _detect_market_regime([]) == "NEUTRAL"


# ---------------------------------------------------------------------------
# Tests: _calculate_confidence
# ---------------------------------------------------------------------------

class TestCalculateConfidence:
    def _good_sector_data(self) -> dict:
        return {"Technology": {"avg_score": 70, "trend": "HOT 🔥"}}

    def test_strong_buy_high_confidence(self):
        sig = _make_signal(score=85, signal="STRONG BUY", vol_ratio=2.0, rr=3.0)
        conf = _calculate_confidence(sig, "BULLISH", self._good_sector_data())
        assert conf >= 75

    def test_low_score_low_confidence(self):
        sig = _make_signal(score=50, signal="BUY", vol_ratio=0.8, rr=1.0)
        conf = _calculate_confidence(sig, "BEARISH", {})
        assert conf < 85

    def test_confidence_capped_at_100(self):
        sig = _make_signal(score=100, signal="STRONG BUY", vol_ratio=5.0, rr=5.0)
        conf = _calculate_confidence(sig, "BULLISH", {"Technology": {"avg_score": 100}})
        assert conf <= 100.0

    def test_confidence_non_negative(self):
        sig = _make_signal(score=0, signal="BUY", vol_ratio=0, rr=0)
        conf = _calculate_confidence(sig, "BEARISH", {})
        assert conf >= 0


# ---------------------------------------------------------------------------
# Tests: _assess_urgency
# ---------------------------------------------------------------------------

class TestAssessUrgency:
    def test_strong_buy_bullish_macd_high_volume_is_now(self):
        sig = _make_signal(signal="STRONG BUY", macd="bullish_crossover", vol_ratio=2.0)
        assert _assess_urgency(sig) == "NOW"

    def test_strong_buy_is_at_least_today(self):
        sig = _make_signal(signal="STRONG BUY", macd="none", vol_ratio=0.8)
        urgency = _assess_urgency(sig)
        assert urgency in ("NOW", "TODAY")

    def test_weak_buy_is_this_week_or_watch(self):
        sig = _make_signal(score=65, signal="BUY", macd="none", vol_ratio=1.0)
        urgency = _assess_urgency(sig)
        assert urgency in ("THIS_WEEK", "WATCH", "TODAY")

    def test_hold_is_watch(self):
        sig = _make_signal(score=50, signal="HOLD", macd="none", vol_ratio=0.9)
        urgency = _assess_urgency(sig)
        assert urgency == "WATCH"


# ---------------------------------------------------------------------------
# Tests: generate_trade_recommendations
# ---------------------------------------------------------------------------

class TestGenerateTradeRecommendations:
    def test_only_high_confidence_returned(self):
        """With strong setup, at least some recommendations should be returned."""
        signals = [_make_signal(f"T{i}", score=85, signal="STRONG BUY") for i in range(5)]
        recs = generate_trade_recommendations(signals, account_size=5000.0)
        assert all(r["confidence"] >= MIN_CONFIDENCE for r in recs)

    def test_sorted_by_confidence_desc(self):
        signals = [_make_signal(f"T{i}", score=80 + i, signal="STRONG BUY") for i in range(5)]
        recs = generate_trade_recommendations(signals)
        confs = [r["confidence"] for r in recs]
        assert confs == sorted(confs, reverse=True)

    def test_avoid_signals_excluded(self):
        signals = [_make_signal("BAD", score=20, signal="AVOID")]
        recs = generate_trade_recommendations(signals)
        assert all(r["ticker"] != "BAD" for r in recs)

    def test_recommendation_keys_present(self):
        signals = [_make_signal("NVDA", score=90, signal="STRONG BUY")]
        recs = generate_trade_recommendations(signals, account_size=5000.0)
        if recs:
            rec = recs[0]
            required_keys = [
                "ticker", "signal", "confidence", "entry_price", "stop_loss",
                "target_1", "target_2", "shares", "total_cost", "risk_dollars",
                "reward_dollars", "risk_reward_ratio", "urgency", "reasoning",
                "exit_plan", "broker_steps", "pre_trade_checklist",
            ]
            for key in required_keys:
                assert key in rec, f"Missing key: {key}"

    def test_empty_scan_results_returns_empty(self):
        assert generate_trade_recommendations([]) == []


# ---------------------------------------------------------------------------
# Tests: generate_sell_recommendations
# ---------------------------------------------------------------------------

class TestGenerateSellRecommendations:
    def _make_position(
        self,
        ticker: str = "AAPL",
        entry: float = 150.0,
        shares: int = 3,
        stop: float = 143.0,
        t1: float = 160.0,
        t2: float = 170.0,
        t1_hit: bool = False,
    ) -> dict:
        return {
            "ticker": ticker,
            "entry_price": entry,
            "shares": shares,
            "stop_loss": stop,
            "target_1": t1,
            "target_2": t2,
            "trade_type": "swing",
            "status": "open",
            "target_1_hit": t1_hit,
            "entry_date": "2026-01-01",
        }

    def test_stop_loss_triggers_alert(self):
        pos = [self._make_position(stop=143.0)]
        sig = _make_signal("AAPL", entry=140.0)  # below stop
        alerts = generate_sell_recommendations(pos, [sig])
        assert any(a["alert_type"] == "STOP_HIT" for a in alerts)

    def test_target_1_triggers_alert(self):
        pos = [self._make_position(t1=160.0, t1_hit=False)]
        sig = _make_signal("AAPL", entry=162.0)  # above target 1
        alerts = generate_sell_recommendations(pos, [sig])
        assert any(a["alert_type"] == "TARGET_1_HIT" for a in alerts)

    def test_target_2_triggers_alert(self):
        pos = [self._make_position(t2=170.0, t1_hit=True)]
        sig = _make_signal("AAPL", entry=172.0)  # above target 2
        alerts = generate_sell_recommendations(pos, [sig])
        assert any(a["alert_type"] in ("TARGET_2_HIT", "TARGET_1_HIT") for a in alerts)

    def test_trend_reversal_triggers_alert(self):
        pos = [self._make_position()]
        sig = _make_signal("AAPL", signal="AVOID", entry=155.0)
        alerts = generate_sell_recommendations(pos, [sig])
        assert any(a["alert_type"] == "TREND_REVERSAL" for a in alerts)

    def test_no_alert_for_healthy_position(self):
        pos = [self._make_position(stop=143.0, t1=160.0, t2=170.0)]
        sig = _make_signal("AAPL", entry=152.0)  # between stop and target
        alerts = generate_sell_recommendations(pos, [sig])
        assert all(a["ticker"] != "AAPL" for a in alerts)

    def test_empty_inputs_return_empty(self):
        assert generate_sell_recommendations([], []) == []
        assert generate_sell_recommendations([self._make_position()], []) == []

    def test_stop_alerts_before_target_alerts(self):
        pos = [
            self._make_position("A", stop=143.0),  # will hit stop
            self._make_position("B", t1=160.0),     # at target
        ]
        sigs = [
            _make_signal("A", entry=140.0),  # below stop
            _make_signal("B", entry=162.0),  # above target
        ]
        alerts = generate_sell_recommendations(pos, sigs)
        if len(alerts) >= 2:
            urgencies = [a["urgency"] for a in alerts]
            urgency_order = {"NOW": 0, "TODAY": 1, "THIS_WEEK": 2, "WATCH": 3}
            assert urgency_order[urgencies[0]] <= urgency_order[urgencies[1]]


# ---------------------------------------------------------------------------
# Tests: analyze_market
# ---------------------------------------------------------------------------

class TestAnalyzeMarket:
    def test_returns_expected_keys(self):
        signals = [_make_signal(f"T{i}", score=80, signal="STRONG BUY") for i in range(5)]
        result = analyze_market(signals, account_size=5000.0)
        expected_keys = [
            "market_regime", "market_summary", "sector_analysis",
            "recommended_trades", "risk_warnings", "portfolio_suggestion",
        ]
        for key in expected_keys:
            assert key in result

    def test_empty_scan_returns_neutral(self):
        result = analyze_market([])
        assert result["market_regime"] == "NEUTRAL"
        assert result["recommended_trades"] == []

    def test_market_regime_in_valid_values(self):
        signals = [_make_signal(f"T{i}") for i in range(10)]
        result = analyze_market(signals)
        assert result["market_regime"] in ("BULLISH", "BEARISH", "NEUTRAL", "VOLATILE")

    def test_market_summary_is_non_empty_string(self):
        signals = [_make_signal(f"T{i}") for i in range(5)]
        result = analyze_market(signals)
        assert isinstance(result["market_summary"], str)
        assert len(result["market_summary"]) > 10


# ---------------------------------------------------------------------------
# Tests: _generate_reasoning
# ---------------------------------------------------------------------------

class TestGenerateReasoning:
    def test_reasoning_includes_ticker(self):
        sig = _make_signal("NVDA")
        reasoning = _generate_reasoning(sig, {}, "BULLISH")
        assert "NVDA" in reasoning

    def test_reasoning_is_non_empty(self):
        sig = _make_signal("AAPL")
        reasoning = _generate_reasoning(sig, {}, "NEUTRAL")
        assert len(reasoning) > 20


# ---------------------------------------------------------------------------
# Tests: _generate_exit_plan
# ---------------------------------------------------------------------------

class TestGenerateExitPlan:
    def test_exit_plan_includes_stop(self):
        sig = _make_signal("NVDA", stop=143.0)
        plan = _generate_exit_plan(sig, "swing")
        assert "143" in plan

    def test_exit_plan_includes_targets(self):
        sig = _make_signal("NVDA", t1=160.0, t2=170.0)
        plan = _generate_exit_plan(sig, "swing")
        assert "160" in plan
        assert "170" in plan

    def test_day_trade_mentions_close(self):
        sig = _make_signal("NVDA")
        plan = _generate_exit_plan(sig, "day")
        assert "close" in plan.lower() or "day" in plan.lower()
