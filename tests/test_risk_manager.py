"""
Unit tests for the risk management module.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from src.analysis.risk_manager import (
    calculate_position_size,
    calculate_portfolio_heat,
    would_exceed_heat_limit,
    calculate_r_multiple,
    portfolio_statistics,
)


# ---------------------------------------------------------------------------
# Position sizing tests
# ---------------------------------------------------------------------------

class TestCalculatePositionSize:
    def test_basic_calculation(self):
        result = calculate_position_size(
            account_size=1000.0,
            entry_price=100.0,
            stop_loss=95.0,
            risk_pct=0.02,
        )
        # Risk = $20, risk per share = $5 → 4 shares
        assert result["shares"] == 4
        assert result["position_value"] == pytest.approx(400.0)
        assert result["risk_amount"] == pytest.approx(20.0)
        assert result["risk_per_share"] == pytest.approx(5.0)

    def test_one_percent_risk(self):
        result = calculate_position_size(10_000.0, 50.0, 48.0, 0.01)
        # Risk = $100, per share = $2 → 50 shares
        assert result["shares"] == 50
        assert result["risk_amount"] == pytest.approx(100.0)

    def test_minimum_one_share(self):
        # Huge stock price relative to small account — still at least 1 share
        result = calculate_position_size(100.0, 500.0, 490.0, 0.02)
        assert result["shares"] >= 1

    def test_invalid_entry_equals_stop(self):
        with pytest.raises(ValueError):
            calculate_position_size(1000.0, 100.0, 100.0)

    def test_entry_below_stop_raises(self):
        with pytest.raises(ValueError):
            calculate_position_size(1000.0, 95.0, 100.0)

    def test_zero_entry_raises(self):
        with pytest.raises(ValueError):
            calculate_position_size(1000.0, 0.0, 0.0)

    def test_risk_pct_reflected_in_output(self):
        result = calculate_position_size(1000.0, 100.0, 90.0, 0.02)
        assert result["risk_pct_of_account"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Portfolio heat tests
# ---------------------------------------------------------------------------

class TestCalculatePortfolioHeat:
    def _make_positions(self, n: int = 2) -> list[dict]:
        return [
            {
                "ticker": f"STOCK{i}",
                "shares": 10,
                "entry_price": 100.0,
                "stop_loss": 95.0,
            }
            for i in range(n)
        ]

    def test_heat_calculation(self):
        positions = self._make_positions(1)
        result = calculate_portfolio_heat(positions, 1000.0)
        # Risk per position: (100-95) * 10 = $50 → 5% heat
        assert result["total_heat_pct"] == pytest.approx(5.0)
        assert result["total_risk_dollars"] == pytest.approx(50.0)

    def test_within_limit_when_low_heat(self):
        positions = self._make_positions(1)
        result = calculate_portfolio_heat(positions, 10_000.0)
        # 5% risk / $10k = 0.5% heat → well within 8% limit
        assert result["within_limit"] is True

    def test_over_limit_when_high_heat(self):
        # Many positions with large risk
        positions = [
            {"ticker": f"X{i}", "shares": 100, "entry_price": 100.0, "stop_loss": 80.0}
            for i in range(5)
        ]
        result = calculate_portfolio_heat(positions, 1000.0)
        # Risk = (100-80)*100 * 5 = $10,000 >> $1,000 account
        assert result["within_limit"] is False

    def test_empty_positions_zero_heat(self):
        result = calculate_portfolio_heat([], 1000.0)
        assert result["total_heat_pct"] == pytest.approx(0.0)
        assert result["within_limit"] is True

    def test_position_heats_listed(self):
        positions = self._make_positions(2)
        result = calculate_portfolio_heat(positions, 1000.0)
        assert len(result["position_heats"]) == 2

    def test_max_heat_pct_from_settings(self):
        result = calculate_portfolio_heat([], 1000.0)
        assert result["max_heat_pct"] == pytest.approx(8.0)


# ---------------------------------------------------------------------------
# would_exceed_heat_limit tests
# ---------------------------------------------------------------------------

class TestWouldExceedHeatLimit:
    def test_new_position_within_limit(self):
        result = would_exceed_heat_limit(
            positions=[],
            account_size=10_000.0,
            new_entry=100.0,
            new_stop=95.0,
            new_shares=10,
        )
        # Risk = $50 / $10,000 = 0.5% — well within 8%
        assert result is False

    def test_new_position_exceeds_limit(self):
        result = would_exceed_heat_limit(
            positions=[],
            account_size=100.0,
            new_entry=100.0,
            new_stop=10.0,
            new_shares=100,
        )
        # Risk = $9,000 / $100 = 9,000% — massively over limit
        assert result is True


# ---------------------------------------------------------------------------
# R-multiple tests
# ---------------------------------------------------------------------------

class TestCalculateRMultiple:
    def test_winning_trade_positive_r(self):
        r = calculate_r_multiple(entry=100.0, exit_price=106.0, stop_loss=97.0)
        # reward = 6, risk = 3 → R = 2.0
        assert r == pytest.approx(2.0)

    def test_losing_trade_negative_r(self):
        # Exit at stop-loss → R = -1.0
        r = calculate_r_multiple(entry=100.0, exit_price=97.0, stop_loss=97.0)
        assert r == pytest.approx(-1.0)

    def test_breakeven_zero_r(self):
        r = calculate_r_multiple(entry=100.0, exit_price=100.0, stop_loss=95.0)
        assert r == pytest.approx(0.0)

    def test_zero_risk_returns_zero(self):
        r = calculate_r_multiple(entry=100.0, exit_price=110.0, stop_loss=100.0)
        assert r == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Portfolio statistics tests
# ---------------------------------------------------------------------------

class TestPortfolioStatistics:
    def _make_trades(self) -> list[dict]:
        return [
            {"entry_price": 100.0, "exit_price": 106.0, "stop_loss": 97.0, "pnl": 60.0},  # 2R win
            {"entry_price": 50.0, "exit_price": 47.0, "stop_loss": 47.0, "pnl": -30.0},   # loss
            {"entry_price": 200.0, "exit_price": 209.0, "stop_loss": 197.0, "pnl": 90.0}, # 3R win
        ]

    def test_win_rate_calculation(self):
        stats = portfolio_statistics(self._make_trades())
        assert stats["total_trades"] == 3
        assert stats["win_rate"] == pytest.approx(66.67, abs=0.1)

    def test_avg_r_positive_for_winning_system(self):
        stats = portfolio_statistics(self._make_trades())
        assert stats["avg_r_multiple"] > 0

    def test_empty_trades_returns_zeros(self):
        stats = portfolio_statistics([])
        assert stats["total_trades"] == 0
        assert stats["win_rate"] == 0.0
        assert stats["avg_r_multiple"] == 0.0

    def test_all_keys_present(self):
        stats = portfolio_statistics(self._make_trades())
        for key in ("total_trades", "win_rate", "avg_r_multiple", "avg_win", "avg_loss",
                    "profit_factor", "estimated_sharpe"):
            assert key in stats
