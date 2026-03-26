"""
Portfolio tracker for Kesmani.

Persists open positions to data/portfolio.json and provides
CRUD operations plus live P&L calculations.

Position schema:
  {
    "ticker": "NVDA",
    "entry_date": "2026-03-01",
    "entry_price": 142.50,
    "shares": 3,
    "stop_loss": 138.00,
    "target_1": 155.00,
    "target_2": 163.00,
    "notes": ""
  }
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import DATA_DIR, PORTFOLIO_SETTINGS
from src.data.market_data import get_current_price

logger = logging.getLogger(__name__)

PORTFOLIO_FILE = DATA_DIR / "portfolio.json"


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _load_portfolio() -> dict:
    """Load the portfolio JSON file, returning a default skeleton if missing."""
    if not PORTFOLIO_FILE.exists():
        return _default_portfolio()
    try:
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load portfolio file: %s", exc)
        return _default_portfolio()


def _save_portfolio(data: dict) -> None:
    """Persist the portfolio dict to disk."""
    PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _default_portfolio() -> dict:
    """Return the initial portfolio skeleton."""
    return {
        "starting_capital": PORTFOLIO_SETTINGS["starting_capital"],
        "cash": PORTFOLIO_SETTINGS["starting_capital"],
        "positions": [],
        "closed_trades": [],
        "last_updated": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# Position management
# ---------------------------------------------------------------------------

def add_position(
    ticker: str,
    entry_price: float,
    shares: int,
    stop_loss: float,
    target_1: Optional[float] = None,
    target_2: Optional[float] = None,
    notes: str = "",
) -> dict:
    """
    Add a new open position to the portfolio.

    Parameters
    ----------
    ticker:
        Equity symbol.
    entry_price:
        Price at which shares were purchased.
    shares:
        Number of shares.
    stop_loss:
        Stop-loss price.
    target_1, target_2:
        Price targets (optional).
    notes:
        Free-text notes.

    Returns
    -------
    The newly created position dict.
    """
    portfolio = _load_portfolio()
    cost_basis = entry_price * shares

    position: dict = {
        "id": _generate_id(),
        "ticker": ticker.upper(),
        "entry_date": datetime.now().strftime("%Y-%m-%d"),
        "entry_price": round(entry_price, 2),
        "shares": shares,
        "cost_basis": round(cost_basis, 2),
        "stop_loss": round(stop_loss, 2),
        "target_1": round(target_1, 2) if target_1 else None,
        "target_2": round(target_2, 2) if target_2 else None,
        "notes": notes,
    }

    portfolio["positions"].append(position)
    portfolio["cash"] = round(portfolio.get("cash", 0.0) - cost_basis, 2)
    portfolio["last_updated"] = datetime.now().isoformat()
    _save_portfolio(portfolio)
    logger.info("Added position: %s x%d @ $%.2f", ticker, shares, entry_price)
    return position


def remove_position(position_id: str, exit_price: float, reason: str = "manual") -> Optional[dict]:
    """
    Close an open position and record it in closed_trades.

    Parameters
    ----------
    position_id:
        ID of the position to close.
    exit_price:
        Exit price per share.
    reason:
        Reason for closing (e.g. "target", "stop", "manual").

    Returns
    -------
    The closed trade dict, or None if position_id not found.
    """
    portfolio = _load_portfolio()
    positions = portfolio.get("positions", [])
    pos = next((p for p in positions if p["id"] == position_id), None)
    if not pos:
        logger.warning("Position %s not found", position_id)
        return None

    exit_value = exit_price * pos["shares"]
    pnl = exit_value - pos["cost_basis"]
    pnl_pct = pnl / pos["cost_basis"] * 100

    closed_trade = {
        **pos,
        "exit_date": datetime.now().strftime("%Y-%m-%d"),
        "exit_price": round(exit_price, 2),
        "exit_value": round(exit_value, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "reason": reason,
    }

    portfolio["positions"] = [p for p in positions if p["id"] != position_id]
    portfolio.setdefault("closed_trades", []).append(closed_trade)
    portfolio["cash"] = round(portfolio.get("cash", 0.0) + exit_value, 2)
    portfolio["last_updated"] = datetime.now().isoformat()
    _save_portfolio(portfolio)
    logger.info("Closed %s: PnL $%.2f (%.1f%%)", pos["ticker"], pnl, pnl_pct)
    return closed_trade


def update_stop_loss(position_id: str, new_stop: float) -> bool:
    """Update the stop-loss on an open position. Returns True on success."""
    portfolio = _load_portfolio()
    for pos in portfolio.get("positions", []):
        if pos["id"] == position_id:
            pos["stop_loss"] = round(new_stop, 2)
            portfolio["last_updated"] = datetime.now().isoformat()
            _save_portfolio(portfolio)
            return True
    return False


# ---------------------------------------------------------------------------
# Portfolio summary
# ---------------------------------------------------------------------------

def get_portfolio_summary() -> dict:
    """
    Return a comprehensive portfolio snapshot with live P&L.

    Fetches current prices for all open positions.

    Returns
    -------
    Dict with: starting_capital, cash, positions (enriched with live_price
    and unrealized_pnl), total_invested, total_market_value, total_unrealized_pnl,
    total_unrealized_pnl_pct, closed_trades, total_realized_pnl.
    """
    portfolio = _load_portfolio()
    positions = portfolio.get("positions", [])
    enriched: list[dict] = []
    total_invested = 0.0
    total_market_value = 0.0

    for pos in positions:
        live_price = get_current_price(pos["ticker"])
        if live_price is None:
            live_price = pos["entry_price"]  # fallback to entry if no data

        market_value = live_price * pos["shares"]
        unrealized_pnl = market_value - pos["cost_basis"]
        unrealized_pnl_pct = unrealized_pnl / pos["cost_basis"] * 100

        enriched.append(
            {
                **pos,
                "live_price": round(live_price, 2),
                "market_value": round(market_value, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
                "at_stop": live_price <= pos["stop_loss"],
                "at_target_1": pos.get("target_1") and live_price >= pos["target_1"],
            }
        )
        total_invested += pos["cost_basis"]
        total_market_value += market_value

    closed_trades = portfolio.get("closed_trades", [])
    total_realized_pnl = sum(t.get("pnl", 0.0) for t in closed_trades)
    total_unrealized_pnl = total_market_value - total_invested
    total_unrealized_pnl_pct = (
        total_unrealized_pnl / total_invested * 100 if total_invested > 0 else 0.0
    )
    cash = portfolio.get("cash", portfolio.get("starting_capital", PORTFOLIO_SETTINGS["starting_capital"]))
    net_worth = cash + total_market_value

    return {
        "starting_capital": portfolio.get("starting_capital", PORTFOLIO_SETTINGS["starting_capital"]),
        "cash": round(cash, 2),
        "positions": enriched,
        "total_invested": round(total_invested, 2),
        "total_market_value": round(total_market_value, 2),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "total_unrealized_pnl_pct": round(total_unrealized_pnl_pct, 2),
        "total_realized_pnl": round(total_realized_pnl, 2),
        "net_worth": round(net_worth, 2),
        "closed_trades": closed_trades,
        "last_updated": portfolio.get("last_updated"),
    }


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _generate_id() -> str:
    """Generate a short unique ID for a position."""
    import uuid
    return str(uuid.uuid4())[:8]
