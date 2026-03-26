"""
Risk management module for Kesmani.

Handles:
  - Position sizing based on fixed-fractional (1-2 % account risk)
  - Portfolio heat calculation (total open risk as % of account)
  - Risk/reward ratio validation
  - Portfolio-level statistics (win rate, avg R-multiple, Sharpe estimate)
"""

import logging
import math
from typing import Optional

from config.settings import PORTFOLIO_SETTINGS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Position sizing
# ---------------------------------------------------------------------------

def calculate_position_size(
    account_size: float,
    entry_price: float,
    stop_loss: float,
    risk_pct: float = PORTFOLIO_SETTINGS["max_risk_per_trade"],
) -> dict:
    """
    Calculate position size using fixed-fractional risk management.

    Parameters
    ----------
    account_size:
        Total portfolio value in dollars.
    entry_price:
        Planned entry price per share.
    stop_loss:
        Stop-loss price per share.
    risk_pct:
        Fraction of account to risk on this trade (default 2 %).

    Returns
    -------
    Dict with: shares, position_value, risk_amount, risk_per_share,
               risk_pct_of_account.

    Raises
    ------
    ValueError if entry_price <= stop_loss (invalid setup).
    """
    if entry_price <= 0:
        raise ValueError(f"entry_price must be > 0, got {entry_price}")
    if stop_loss <= 0:
        raise ValueError(f"stop_loss must be > 0, got {stop_loss}")
    if entry_price <= stop_loss:
        raise ValueError(
            f"entry_price ({entry_price}) must be greater than stop_loss ({stop_loss})"
        )

    risk_amount = account_size * risk_pct
    risk_per_share = entry_price - stop_loss
    shares = math.floor(risk_amount / risk_per_share)
    shares = max(1, shares)  # at least 1 share
    position_value = shares * entry_price

    return {
        "shares": shares,
        "position_value": round(position_value, 2),
        "risk_amount": round(risk_amount, 2),
        "risk_per_share": round(risk_per_share, 2),
        "risk_pct_of_account": round(risk_pct * 100, 2),
    }


# ---------------------------------------------------------------------------
# Portfolio heat
# ---------------------------------------------------------------------------

def calculate_portfolio_heat(positions: list[dict], account_size: float) -> dict:
    """
    Calculate the total portfolio heat (sum of open position risks).

    Parameters
    ----------
    positions:
        List of position dicts, each with keys:
            ticker, shares, entry_price, stop_loss.
    account_size:
        Current total portfolio value.

    Returns
    -------
    Dict with: total_heat_pct, total_risk_dollars, max_heat_pct,
               within_limit, position_heats.
    """
    max_heat = PORTFOLIO_SETTINGS["max_portfolio_heat"]
    total_risk = 0.0
    position_heats: list[dict] = []

    for pos in positions:
        try:
            entry = pos.get("entry_price", 0.0)
            stop = pos.get("stop_loss", 0.0)
            shares = pos.get("shares", 0)
            if entry > stop > 0 and shares > 0:
                pos_risk = (entry - stop) * shares
                pos_heat_pct = pos_risk / account_size * 100
                total_risk += pos_risk
                position_heats.append(
                    {
                        "ticker": pos.get("ticker", "?"),
                        "risk_dollars": round(pos_risk, 2),
                        "heat_pct": round(pos_heat_pct, 2),
                    }
                )
        except Exception as exc:
            logger.warning("Heat calc failed for position %s: %s", pos.get("ticker"), exc)

    total_heat_pct = total_risk / account_size * 100 if account_size > 0 else 0.0

    return {
        "total_heat_pct": round(total_heat_pct, 2),
        "total_risk_dollars": round(total_risk, 2),
        "max_heat_pct": round(max_heat * 100, 2),
        "within_limit": total_heat_pct <= max_heat * 100,
        "position_heats": position_heats,
    }


def would_exceed_heat_limit(
    positions: list[dict],
    account_size: float,
    new_entry: float,
    new_stop: float,
    new_shares: int,
) -> bool:
    """
    Return True if adding a new position would breach the max heat limit.

    Parameters
    ----------
    positions:
        Existing open positions.
    account_size:
        Current portfolio value.
    new_entry, new_stop, new_shares:
        Proposed new position parameters.
    """
    new_risk = (new_entry - new_stop) * new_shares if new_entry > new_stop else 0
    current_heat = calculate_portfolio_heat(positions, account_size)
    projected_heat = (current_heat["total_risk_dollars"] + new_risk) / account_size
    return projected_heat > PORTFOLIO_SETTINGS["max_portfolio_heat"]


# ---------------------------------------------------------------------------
# R-multiple & win rate statistics
# ---------------------------------------------------------------------------

def calculate_r_multiple(entry: float, exit_price: float, stop_loss: float) -> float:
    """
    Calculate the R-multiple of a completed trade.

    R = (exit - entry) / (entry - stop)
    Positive R = win, negative R = loss.
    """
    risk = entry - stop_loss
    if risk <= 0:
        return 0.0
    return round((exit_price - entry) / risk, 2)


def portfolio_statistics(closed_trades: list[dict]) -> dict:
    """
    Calculate portfolio-level statistics from closed trade history.

    Parameters
    ----------
    closed_trades:
        List of dicts, each with: entry_price, exit_price, stop_loss, pnl.

    Returns
    -------
    Dict with: total_trades, win_rate, avg_r_multiple, avg_win,
               avg_loss, profit_factor, estimated_sharpe.
    """
    if not closed_trades:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_r_multiple": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "estimated_sharpe": 0.0,
        }

    r_multiples: list[float] = []
    wins: list[float] = []
    losses: list[float] = []

    for trade in closed_trades:
        try:
            r = calculate_r_multiple(
                trade["entry_price"], trade["exit_price"], trade["stop_loss"]
            )
            r_multiples.append(r)
            if r > 0:
                wins.append(trade.get("pnl", 0.0))
            else:
                losses.append(trade.get("pnl", 0.0))
        except Exception:
            continue

    total = len(r_multiples)
    win_rate = len(wins) / total * 100 if total > 0 else 0.0
    avg_r = sum(r_multiples) / len(r_multiples) if r_multiples else 0.0
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    profit_factor = abs(sum(wins) / sum(losses)) if sum(losses) < 0 else float("inf")

    # Rough Sharpe estimate: mean(R) / std(R)
    if len(r_multiples) > 1:
        mean_r = avg_r
        variance = sum((r - mean_r) ** 2 for r in r_multiples) / (len(r_multiples) - 1)
        std_r = variance ** 0.5
        sharpe = mean_r / std_r if std_r > 0 else 0.0
    else:
        sharpe = 0.0

    return {
        "total_trades": total,
        "win_rate": round(win_rate, 2),
        "avg_r_multiple": round(avg_r, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2),
        "estimated_sharpe": round(sharpe, 2),
    }
