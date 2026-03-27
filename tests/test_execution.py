"""
Unit tests for the trade execution module.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from src.analysis.execution import (
    generate_execution_plan,
    _determine_order_type,
    _determine_timing,
    _build_broker_steps,
    _build_checklist,
    _build_warnings,
    _build_scale_in_plan,
    _build_partial_profit_plan,
    _empty_plan,
    _SCALE_IN_THRESHOLD,
)
from config.settings import MEGA_CAPS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_buy_signal(
    ticker: str = "AAPL",
    signal: str = "BUY",
    entry: float = 150.0,
    stop_loss: float = 143.0,
    target_1: float = 164.0,
    target_2: float = 178.0,
    shares: int = 5,
    position_value: float = 750.0,
    risk_amount: float = 20.0,
    vix_adjusted: str | None = None,
    earnings_warning: bool = False,
) -> dict:
    return {
        "ticker": ticker,
        "signal": signal,
        "composite_score": 75.0,
        "sector": "Technology",
        "entry": entry,
        "stop_loss": stop_loss,
        "target_1": target_1,
        "target_2": target_2,
        "position_shares": shares,
        "position_value": position_value,
        "risk_amount": risk_amount,
        "rr_ratio": 2.0,
        "reasoning": "Test signal.",
        "indicators": {
            "current_price": entry,
            "rsi": 55.0,
            "macd_crossover": "bullish_crossover",
            "trend": "BULLISH",
            "sma_50": 140.0,
            "sma_200": 120.0,
            "sma_20": 145.0,
            "atr": 4.0,
            "support": 143.0,
            "volume_ratio": 1.5,
        },
        "fundamentals": {},
        "vix_adjusted": vix_adjusted,
        "earnings_warning": earnings_warning,
    }


# ---------------------------------------------------------------------------
# Tests: generate_execution_plan
# ---------------------------------------------------------------------------

class TestGenerateExecutionPlan:
    def test_returns_dict_with_required_keys(self):
        plan = generate_execution_plan(_make_buy_signal(), account_size=10000.0)
        required_keys = [
            "order_type", "limit_price", "timing", "entry_strategy",
            "position_size_shares", "position_size_dollars", "total_risk_dollars",
            "stop_loss_type", "stop_loss_price", "target_1_price", "target_2_price",
            "partial_profit_plan", "max_hold_days", "broker_steps", "checklist",
            "warnings",
        ]
        for key in required_keys:
            assert key in plan, f"Missing key: {key}"

    def test_limit_price_below_entry(self):
        signal = _make_buy_signal(entry=150.0)
        plan = generate_execution_plan(signal, account_size=10000.0)
        assert plan["limit_price"] < signal["entry"]

    def test_limit_price_reasonable_discount(self):
        # Limit price should not be more than 1% below entry
        signal = _make_buy_signal(entry=150.0)
        plan = generate_execution_plan(signal, account_size=10000.0)
        assert plan["limit_price"] >= signal["entry"] * 0.99

    def test_stop_loss_price_matches_signal(self):
        signal = _make_buy_signal(stop_loss=143.0)
        plan = generate_execution_plan(signal, account_size=10000.0)
        assert plan["stop_loss_price"] == pytest.approx(143.0, abs=0.01)

    def test_targets_preserved(self):
        signal = _make_buy_signal(target_1=164.0, target_2=178.0)
        plan = generate_execution_plan(signal, account_size=10000.0)
        assert plan["target_1_price"] == pytest.approx(164.0, abs=0.01)
        assert plan["target_2_price"] == pytest.approx(178.0, abs=0.01)

    def test_max_hold_days_is_positive(self):
        plan = generate_execution_plan(_make_buy_signal(), account_size=10000.0)
        assert plan["max_hold_days"] > 0

    def test_broker_steps_is_nonempty_list(self):
        plan = generate_execution_plan(_make_buy_signal(), account_size=10000.0)
        assert isinstance(plan["broker_steps"], list)
        assert len(plan["broker_steps"]) >= 5

    def test_checklist_is_nonempty_list(self):
        plan = generate_execution_plan(_make_buy_signal(), account_size=10000.0)
        assert isinstance(plan["checklist"], list)
        assert len(plan["checklist"]) >= 5

    def test_warnings_is_list(self):
        plan = generate_execution_plan(_make_buy_signal(), account_size=10000.0)
        assert isinstance(plan["warnings"], list)
        assert len(plan["warnings"]) >= 1

    def test_zero_entry_returns_empty_plan(self):
        signal = _make_buy_signal(entry=0.0)
        plan = generate_execution_plan(signal, account_size=10000.0)
        assert plan["order_type"] == "N/A"
        assert plan["position_size_shares"] == 0

    def test_none_entry_returns_empty_plan(self):
        signal = _make_buy_signal()
        signal["entry"] = None
        plan = generate_execution_plan(signal, account_size=10000.0)
        assert plan["order_type"] == "N/A"

    def test_strong_buy_uses_trailing_stop(self):
        signal = _make_buy_signal(signal="STRONG BUY")
        plan = generate_execution_plan(signal, account_size=10000.0)
        assert plan["stop_loss_type"] == "trailing_stop"

    def test_buy_uses_hard_stop(self):
        plan = generate_execution_plan(_make_buy_signal(signal="BUY"), account_size=10000.0)
        assert plan["stop_loss_type"] == "hard_stop"

    def test_large_position_triggers_scale_in(self):
        signal = _make_buy_signal(position_value=_SCALE_IN_THRESHOLD + 1)
        plan = generate_execution_plan(signal, account_size=50000.0)
        assert plan["entry_strategy"] == "scale_in"
        assert plan["scale_in_plan"] is not None

    def test_small_position_is_full_position(self):
        signal = _make_buy_signal(position_value=500.0)
        plan = generate_execution_plan(signal, account_size=10000.0)
        assert plan["entry_strategy"] == "full_position"
        assert plan["scale_in_plan"] is None


# ---------------------------------------------------------------------------
# Tests: _determine_order_type
# ---------------------------------------------------------------------------

class TestDetermineOrderType:
    def test_mega_cap_no_vix_returns_market(self):
        ticker = MEGA_CAPS[0]  # e.g. AAPL
        order_type, _ = _determine_order_type(ticker, 150.0, None)
        assert order_type == "MARKET"

    def test_mid_cap_returns_limit(self):
        order_type, _ = _determine_order_type("ZZZZ", 50.0, None)
        assert order_type == "LIMIT"

    def test_elevated_vix_overrides_mega_cap_to_limit(self):
        ticker = MEGA_CAPS[0]
        order_type, _ = _determine_order_type(ticker, 150.0, "VIX 27.0 — ELEVATED")
        assert order_type == "LIMIT"

    def test_reasoning_is_nonempty_string(self):
        _, reasoning = _determine_order_type("AAPL", 150.0, None)
        assert isinstance(reasoning, str) and len(reasoning) > 0


# ---------------------------------------------------------------------------
# Tests: _build_broker_steps
# ---------------------------------------------------------------------------

class TestBuildBrokerSteps:
    def test_includes_ticker(self):
        steps = _build_broker_steps("NVDA", "LIMIT", 140.0, 3, 135.0, 155.0)
        assert any("NVDA" in s for s in steps)

    def test_includes_limit_price_for_limit_order(self):
        steps = _build_broker_steps("AAPL", "LIMIT", 148.5, 5, 143.0, 160.0)
        assert any("148.50" in s or "148.5" in s for s in steps)

    def test_includes_stop_price(self):
        steps = _build_broker_steps("MSFT", "LIMIT", 370.0, 2, 355.0, 395.0)
        assert any("355.00" in s or "355" in s for s in steps)

    def test_includes_target_alert(self):
        steps = _build_broker_steps("AMZN", "LIMIT", 180.0, 3, 170.0, 190.0)
        assert any("190.00" in s or "190" in s for s in steps)

    def test_numbered_steps_all_strings(self):
        steps = _build_broker_steps("AAPL", "MARKET", 150.0, 5, 143.0, 165.0)
        assert all(isinstance(s, str) for s in steps)


# ---------------------------------------------------------------------------
# Tests: _build_checklist
# ---------------------------------------------------------------------------

class TestBuildChecklist:
    def test_earnings_warning_prepended(self):
        items = _build_checklist(True, None, 10000.0, 200.0)
        assert any("EARNINGS" in item.upper() for item in items)
        # Should be near the top
        assert any("EARNINGS" in item.upper() for item in items[:3])

    def test_vix_warning_prepended(self):
        items = _build_checklist(False, "VIX 27.0 — ELEVATED", 10000.0, 200.0)
        assert any("VIX" in item for item in items[:3])

    def test_risk_pct_in_checklist(self):
        items = _build_checklist(False, None, 10000.0, 200.0)
        # 200/10000 = 2.0% — should appear in checklist
        assert any("2.0%" in item for item in items)

    def test_all_items_are_strings(self):
        items = _build_checklist(False, None, 10000.0, 200.0)
        assert all(isinstance(i, str) for i in items)

    def test_minimum_checklist_length(self):
        items = _build_checklist(False, None, 10000.0, 200.0)
        assert len(items) >= 7


# ---------------------------------------------------------------------------
# Tests: _build_warnings
# ---------------------------------------------------------------------------

class TestBuildWarnings:
    def test_earnings_warning_included(self):
        signal = _make_buy_signal(earnings_warning=True)
        warnings = _build_warnings(True, None, 150.0, signal)
        assert any("Earnings" in w for w in warnings)

    def test_vix_note_included(self):
        signal = _make_buy_signal()
        warnings = _build_warnings(False, "VIX 27.0 — ELEVATED", 150.0, signal)
        assert any("VIX" in w for w in warnings)

    def test_overbought_rsi_warning(self):
        signal = _make_buy_signal()
        signal["indicators"]["rsi"] = 78.0
        warnings = _build_warnings(False, None, 150.0, signal)
        assert any("RSI" in w or "overbought" in w.lower() for w in warnings)

    def test_extended_from_ma_warning(self):
        signal = _make_buy_signal(entry=165.0)  # > 145 * 1.10
        warnings = _build_warnings(False, None, 165.0, signal)
        # entry 165 vs sma_20 145 → 13.8% above
        assert any("above" in w.lower() or "extended" in w.lower() for w in warnings)

    def test_no_warnings_gives_ok_message(self):
        signal = _make_buy_signal()
        signal["indicators"]["rsi"] = 55.0
        signal["indicators"]["sma_20"] = 148.0  # only 1.3% below entry
        warnings = _build_warnings(False, None, 150.0, signal)
        assert len(warnings) >= 1  # always returns at least one item

    def test_low_volume_warning(self):
        signal = _make_buy_signal()
        signal["indicators"]["volume_ratio"] = 0.3
        warnings = _build_warnings(False, None, 150.0, signal)
        assert any("volume" in w.lower() for w in warnings)


# ---------------------------------------------------------------------------
# Tests: _build_scale_in_plan
# ---------------------------------------------------------------------------

class TestBuildScaleInPlan:
    def test_full_position_returns_none(self):
        assert _build_scale_in_plan(10, 150.0, "full_position") is None

    def test_scale_in_returns_three_tranches(self):
        plan = _build_scale_in_plan(20, 150.0, "scale_in")
        assert plan is not None
        assert len(plan) == 3

    def test_tranche_shares_sum_to_total(self):
        shares = 20
        plan = _build_scale_in_plan(shares, 150.0, "scale_in")
        total = sum(t["shares"] for t in plan)
        assert total == shares

    def test_tranche_prices_ordered(self):
        plan = _build_scale_in_plan(20, 150.0, "scale_in")
        # Tranche 1 price <= Tranche 3 price (1 buys at limit, 3 buys higher on confirmation)
        assert plan[0]["price"] <= plan[2]["price"]


# ---------------------------------------------------------------------------
# Tests: _build_partial_profit_plan
# ---------------------------------------------------------------------------

class TestBuildPartialProfitPlan:
    def test_both_targets_present(self):
        plan = _build_partial_profit_plan(160.0, 175.0, "AAPL")
        assert "160.00" in plan or "160" in plan
        assert "175.00" in plan or "175" in plan
        assert "50%" in plan

    def test_only_target_1(self):
        plan = _build_partial_profit_plan(160.0, None, "AAPL")
        assert isinstance(plan, str)
        assert len(plan) > 0

    def test_no_targets(self):
        plan = _build_partial_profit_plan(None, None, "AAPL")
        assert isinstance(plan, str)
        assert len(plan) > 0


# ---------------------------------------------------------------------------
# Tests: _empty_plan
# ---------------------------------------------------------------------------

class TestEmptyPlan:
    def test_returns_dict_with_ticker(self):
        plan = _empty_plan("TEST")
        assert plan["ticker"] == "TEST"
        assert plan["order_type"] == "N/A"
        assert plan["position_size_shares"] == 0
        assert len(plan["broker_steps"]) >= 1

    def test_warnings_present(self):
        plan = _empty_plan("TEST")
        assert len(plan["warnings"]) >= 1
