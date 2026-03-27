"""
Unit tests for the KešMani Position Monitor.
"""

import json
import sys
from pathlib import Path
from datetime import date
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from src.portfolio.position_monitor import (
    add_position,
    remove_position,
    check_all_positions,
    update_trailing_stops,
    get_portfolio_summary,
    load_positions,
    save_positions,
    _extract_price,
    _days_held,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def temp_positions_file(tmp_path, monkeypatch):
    """Redirect positions file to a temp directory for all tests."""
    import src.portfolio.position_monitor as pm
    test_file = tmp_path / "positions.json"
    test_file.write_text("[]")
    monkeypatch.setattr(pm, "_POSITIONS_FILE", test_file)
    yield test_file


def _make_position_signal(
    ticker: str = "AAPL",
    price: float = 150.0,
    signal: str = "BUY",
) -> dict:
    return {
        "ticker": ticker,
        "signal": signal,
        "composite_score": 75.0,
        "sector": "Technology",
        "entry": price,
        "stop_loss": price * 0.95,
        "target_1": price * 1.05,
        "target_2": price * 1.10,
        "position_shares": 3,
        "rr_ratio": 2.0,
        "earnings_warning": False,
        "indicators": {"current_price": price, "rsi": 55.0, "volume_ratio": 1.2},
    }


# ---------------------------------------------------------------------------
# Tests: load_positions / save_positions
# ---------------------------------------------------------------------------

class TestLoadSavePositions:
    def test_empty_file_returns_empty_list(self):
        assert load_positions() == []

    def test_save_and_reload(self):
        positions = [{"ticker": "AAPL", "status": "open"}]
        save_positions(positions)
        loaded = load_positions()
        assert len(loaded) == 1
        assert loaded[0]["ticker"] == "AAPL"

    def test_malformed_json_returns_empty(self, temp_positions_file):
        temp_positions_file.write_text("{not_a_list}")
        result = load_positions()
        assert result == []

    def test_non_list_json_returns_empty(self, temp_positions_file):
        temp_positions_file.write_text('{"key": "value"}')
        result = load_positions()
        assert result == []


# ---------------------------------------------------------------------------
# Tests: add_position
# ---------------------------------------------------------------------------

class TestAddPosition:
    def test_adds_position_successfully(self):
        pos = add_position("AAPL", 150.0, 3, 143.0, 160.0, 170.0)
        assert pos["ticker"] == "AAPL"
        assert pos["entry_price"] == 150.0
        assert pos["shares"] == 3
        assert pos["status"] == "open"

    def test_position_persisted(self):
        add_position("MSFT", 300.0, 2, 285.0, 320.0, 340.0)
        loaded = load_positions()
        assert any(p["ticker"] == "MSFT" for p in loaded)

    def test_duplicate_ticker_replaces_open_position(self):
        add_position("NVDA", 140.0, 2, 133.0, 150.0, 160.0)
        add_position("NVDA", 145.0, 3, 138.0, 155.0, 165.0)
        positions = [p for p in load_positions() if p["ticker"] == "NVDA" and p["status"] == "open"]
        assert len(positions) == 1
        assert positions[0]["entry_price"] == 145.0

    def test_entry_date_is_today(self):
        pos = add_position("AAPL", 150.0, 3, 143.0, 160.0, 170.0)
        assert pos["entry_date"] == str(date.today())

    def test_optional_notes_saved(self):
        pos = add_position("AAPL", 150.0, 3, 143.0, 160.0, 170.0, notes="Test note")
        assert pos["notes"] == "Test note"

    def test_trailing_stop_saved(self):
        pos = add_position("AAPL", 150.0, 3, 143.0, 160.0, 170.0, trailing_stop=145.0)
        assert pos["trailing_stop"] == 145.0


# ---------------------------------------------------------------------------
# Tests: remove_position
# ---------------------------------------------------------------------------

class TestRemovePosition:
    def test_removes_open_position(self):
        add_position("AAPL", 150.0, 3, 143.0, 160.0, 170.0)
        result = remove_position("AAPL")
        assert result is True
        positions = [p for p in load_positions() if p["ticker"] == "AAPL" and p["status"] == "open"]
        assert len(positions) == 0

    def test_removes_nonexistent_returns_false(self):
        result = remove_position("ZZZZ")
        assert result is False

    def test_closed_position_marked_correctly(self):
        add_position("AAPL", 150.0, 3, 143.0, 160.0, 170.0)
        remove_position("AAPL")
        all_positions = load_positions()
        closed = [p for p in all_positions if p["ticker"] == "AAPL"]
        assert all(p["status"] == "closed" for p in closed)


# ---------------------------------------------------------------------------
# Tests: check_all_positions
# ---------------------------------------------------------------------------

class TestCheckAllPositions:
    def test_stop_loss_hit_generates_alert(self):
        add_position("AAPL", 150.0, 3, 143.0, 160.0, 170.0)
        scan = [_make_position_signal("AAPL", price=140.0)]  # below stop
        alerts = check_all_positions(scan)
        assert any(a["alert_type"] in ("STOP_HIT", "TRAILING_STOP_HIT") for a in alerts)

    def test_target_1_hit_generates_alert(self):
        add_position("AAPL", 150.0, 3, 143.0, 160.0, 170.0)
        scan = [_make_position_signal("AAPL", price=162.0)]  # above target 1
        alerts = check_all_positions(scan)
        assert any(a["alert_type"] == "TARGET_1_HIT" for a in alerts)

    def test_no_alert_for_healthy_position(self):
        add_position("AAPL", 150.0, 3, 143.0, 160.0, 170.0)
        scan = [_make_position_signal("AAPL", price=153.0)]  # between stop and target
        alerts = check_all_positions(scan)
        assert not any(a["ticker"] == "AAPL" for a in alerts)

    def test_empty_positions_returns_empty(self):
        scan = [_make_position_signal("AAPL", price=150.0)]
        alerts = check_all_positions(scan)
        assert alerts == []

    def test_trend_reversal_generates_alert(self):
        add_position("AAPL", 150.0, 3, 143.0, 160.0, 170.0)
        scan = [_make_position_signal("AAPL", price=155.0, signal="AVOID")]
        alerts = check_all_positions(scan)
        assert any(a["alert_type"] == "TREND_REVERSAL" for a in alerts)


# ---------------------------------------------------------------------------
# Tests: update_trailing_stops
# ---------------------------------------------------------------------------

class TestUpdateTrailingStops:
    def test_trailing_stop_ratchets_up(self):
        add_position("AAPL", 150.0, 3, 143.0, 160.0, 170.0, trailing_stop=145.0)
        scan = [_make_position_signal("AAPL", price=165.0)]  # price moved up
        result = update_trailing_stops(scan)
        aapl = next((p for p in result if p["ticker"] == "AAPL"), None)
        if aapl and aapl.get("trailing_stop"):
            assert aapl["trailing_stop"] >= 145.0

    def test_no_trailing_stop_unchanged(self):
        add_position("AAPL", 150.0, 3, 143.0, 160.0, 170.0)  # no trailing stop
        scan = [_make_position_signal("AAPL", price=165.0)]
        result = update_trailing_stops(scan)
        aapl = next((p for p in result if p["ticker"] == "AAPL"), None)
        if aapl:
            assert aapl.get("trailing_stop") is None


# ---------------------------------------------------------------------------
# Tests: get_portfolio_summary
# ---------------------------------------------------------------------------

class TestGetPortfolioSummary:
    def test_empty_portfolio(self):
        summary = get_portfolio_summary()
        assert summary["total_positions"] == 0
        assert summary["total_invested"] == 0.0

    def test_with_positions(self):
        add_position("AAPL", 150.0, 3, 143.0, 160.0, 170.0)
        summary = get_portfolio_summary()
        assert summary["total_positions"] == 1
        assert summary["total_invested"] == pytest.approx(450.0)

    def test_pnl_calculated_correctly(self):
        add_position("NVDA", 140.0, 2, 133.0, 150.0, 160.0)
        scan = [_make_position_signal("NVDA", price=150.0)]  # $10 gain per share
        summary = get_portfolio_summary(scan)
        assert summary["total_pnl"] == pytest.approx(20.0, abs=1.0)

    def test_available_capital_computed(self):
        add_position("AAPL", 150.0, 3, 143.0, 160.0, 170.0)
        summary = get_portfolio_summary()
        assert "available_capital" in summary
        assert summary["available_capital"] >= 0

    def test_positions_list_enriched(self):
        add_position("AAPL", 150.0, 3, 143.0, 160.0, 170.0)
        summary = get_portfolio_summary()
        assert len(summary["positions"]) == 1
        pos = summary["positions"][0]
        assert "pnl" in pos
        assert "current_value" in pos
        assert "days_held" in pos


# ---------------------------------------------------------------------------
# Tests: helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_extract_price_from_entry(self):
        sig = {"entry": 150.0, "indicators": {}}
        assert _extract_price(sig) == 150.0

    def test_extract_price_from_indicators(self):
        sig = {"indicators": {"current_price": 200.0}}
        assert _extract_price(sig) == 200.0

    def test_extract_price_none_for_empty(self):
        assert _extract_price({}) is None

    def test_days_held_today(self):
        assert _days_held(str(date.today())) == 0

    def test_days_held_past_date(self):
        from datetime import timedelta
        past = str(date.today() - timedelta(days=5))
        assert _days_held(past) == 5

    def test_days_held_invalid_returns_0(self):
        assert _days_held("not-a-date") == 0
        assert _days_held("") == 0
