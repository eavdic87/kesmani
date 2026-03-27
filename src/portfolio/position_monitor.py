"""
KešMani Position Monitor — Open Trade Tracking System.

Tracks open positions, monitors stop/target levels, generates sell alerts,
and persists state to data/positions.json.
"""

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_POSITIONS_FILE = _DATA_DIR / "positions.json"

# Ensure data directory exists
_DATA_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_positions() -> list[dict]:
    """
    Load open positions from data/positions.json.

    Returns
    -------
    List of position dicts. Empty list if file does not exist or is malformed.
    """
    try:
        if not _POSITIONS_FILE.exists():
            return []
        with _POSITIONS_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            logger.warning("positions.json is not a list — resetting.")
            return []
        return data
    except Exception as exc:
        logger.error("Failed to load positions.json: %s", exc)
        return []


def save_positions(positions: list[dict]) -> None:
    """
    Persist positions list to data/positions.json.

    Parameters
    ----------
    positions:
        List of position dicts to save.
    """
    try:
        _POSITIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _POSITIONS_FILE.open("w", encoding="utf-8") as fh:
            json.dump(positions, fh, indent=2, default=str)
    except Exception as exc:
        logger.error("Failed to save positions.json: %s", exc)


def add_position(
    ticker: str,
    entry_price: float,
    shares: int,
    stop_loss: float,
    target_1: float,
    target_2: float,
    trade_type: str = "swing",
    notes: str = "",
    trailing_stop: Optional[float] = None,
) -> dict:
    """
    Add a new position to the monitor.

    Parameters
    ----------
    ticker:
        Stock symbol.
    entry_price:
        Price per share at entry.
    shares:
        Number of shares purchased.
    stop_loss:
        Hard stop-loss price.
    target_1:
        First profit target price.
    target_2:
        Second profit target price.
    trade_type:
        "day", "swing", or "position".
    notes:
        Optional trade notes/reasoning.
    trailing_stop:
        Optional trailing stop price (None = use hard stop only).

    Returns
    -------
    The new position dict that was saved.
    """
    positions = load_positions()

    # Remove existing open position for the same ticker
    positions = [p for p in positions if not (p["ticker"] == ticker and p["status"] == "open")]

    new_pos: dict = {
        "ticker": ticker,
        "entry_price": round(float(entry_price), 2),
        "shares": int(shares),
        "entry_date": str(date.today()),
        "stop_loss": round(float(stop_loss), 2),
        "trailing_stop": round(float(trailing_stop), 2) if trailing_stop else None,
        "target_1": round(float(target_1), 2),
        "target_2": round(float(target_2), 2),
        "trade_type": trade_type,
        "status": "open",
        "target_1_hit": False,
        "notes": notes,
        "added_at": datetime.utcnow().isoformat(),
    }

    positions.append(new_pos)
    save_positions(positions)
    logger.info("Added position: %s @ $%.2f × %d shares", ticker, entry_price, shares)
    return new_pos


def remove_position(ticker: str) -> bool:
    """
    Mark a position as closed and remove it from open positions.

    Parameters
    ----------
    ticker:
        Stock symbol to close.

    Returns
    -------
    True if found and closed, False if not found.
    """
    positions = load_positions()
    found = False
    for pos in positions:
        if pos["ticker"] == ticker and pos["status"] == "open":
            pos["status"] = "closed"
            pos["closed_at"] = datetime.utcnow().isoformat()
            found = True
    if found:
        save_positions(positions)
        logger.info("Closed position: %s", ticker)
    return found


def check_all_positions(scan_results: list[dict]) -> list[dict]:
    """
    Check all open positions against current market data.

    Parameters
    ----------
    scan_results:
        Latest scan results list.

    Returns
    -------
    List of alert dicts for positions that need action.
    """
    open_positions = [p for p in load_positions() if p["status"] == "open"]
    if not open_positions or not scan_results:
        return []

    signal_map = {s["ticker"]: s for s in scan_results}
    alerts: list[dict] = []
    positions_updated = False
    all_positions = load_positions()

    for i, pos in enumerate(all_positions):
        if pos["status"] != "open":
            continue

        ticker = pos["ticker"]
        sig = signal_map.get(ticker)
        if not sig:
            continue

        current_price = _extract_price(sig)
        if not current_price:
            continue

        entry = pos.get("entry_price", 0.0)
        stop = pos.get("stop_loss", 0.0)
        t1 = pos.get("target_1", 0.0)
        t2 = pos.get("target_2", 0.0)
        trailing = pos.get("trailing_stop")
        signal_str = sig.get("signal", "HOLD")

        pnl_pct = ((current_price - entry) / entry * 100) if entry else 0.0

        # Stop loss check
        effective_stop = trailing if trailing else stop
        if effective_stop and current_price <= effective_stop:
            alert_type = "TRAILING_STOP_HIT" if trailing else "STOP_HIT"
            alerts.append({
                "ticker": ticker,
                "alert_type": alert_type,
                "current_price": current_price,
                "stop_level": effective_stop,
                "action_needed": f"SELL ALL — {'Trailing stop' if trailing else 'Stop loss'} triggered at ${effective_stop:.2f}",
                "urgency": "NOW",
                "pnl_pct": pnl_pct,
            })

        # Target 1 check
        elif t1 and current_price >= t1 and not pos.get("target_1_hit"):
            alerts.append({
                "ticker": ticker,
                "alert_type": "TARGET_1_HIT",
                "current_price": current_price,
                "stop_level": t1,
                "action_needed": f"SELL 50% at ${t1:.2f}. Move stop to breakeven (${entry:.2f}).",
                "urgency": "TODAY",
                "pnl_pct": pnl_pct,
            })
            all_positions[i]["target_1_hit"] = True
            positions_updated = True

        # Target 2 check
        elif t2 and current_price >= t2:
            alerts.append({
                "ticker": ticker,
                "alert_type": "TARGET_2_HIT",
                "current_price": current_price,
                "stop_level": t2,
                "action_needed": f"SELL ALL — Final target ${t2:.2f} reached. Take full profits.",
                "urgency": "TODAY",
                "pnl_pct": pnl_pct,
            })

        # Trend reversal
        elif signal_str in ("SELL", "AVOID") and entry:
            alerts.append({
                "ticker": ticker,
                "alert_type": "TREND_REVERSAL",
                "current_price": current_price,
                "stop_level": None,
                "action_needed": f"Signal flipped to {signal_str} — consider exiting to protect gains.",
                "urgency": "TODAY",
                "pnl_pct": pnl_pct,
            })

    if positions_updated:
        save_positions(all_positions)

    urgency_order = {"NOW": 0, "TODAY": 1, "THIS_WEEK": 2, "WATCH": 3}
    alerts.sort(key=lambda a: urgency_order.get(a["urgency"], 4))
    return alerts


def update_trailing_stops(scan_results: list[dict]) -> list[dict]:
    """
    Update trailing stop prices for all open positions.

    The trailing stop is moved up if the current price has risen above
    the previous trailing stop level (ratchets up, never down).

    Parameters
    ----------
    scan_results:
        Latest scan results.

    Returns
    -------
    List of updated position dicts.
    """
    positions = load_positions()
    signal_map = {s["ticker"]: s for s in scan_results}
    updated = False

    for pos in positions:
        if pos["status"] != "open":
            continue
        if pos.get("trailing_stop") is None:
            continue

        ticker = pos["ticker"]
        sig = signal_map.get(ticker)
        if not sig:
            continue

        current_price = _extract_price(sig)
        if not current_price:
            continue

        # Use 5% trailing distance as default
        trailing_pct = 0.05
        new_stop = round(current_price * (1 - trailing_pct), 2)
        if new_stop > pos["trailing_stop"]:
            old_stop = pos["trailing_stop"]
            pos["trailing_stop"] = new_stop
            updated = True
            logger.info("Updated trailing stop for %s: $%.2f → $%.2f", ticker, old_stop, new_stop)

    if updated:
        save_positions(positions)

    return [p for p in positions if p["status"] == "open"]


def get_portfolio_summary(scan_results: Optional[list[dict]] = None) -> dict:
    """
    Calculate a portfolio summary with live P&L.

    Parameters
    ----------
    scan_results:
        Latest scan results for current prices. If None, uses entry prices.

    Returns
    -------
    Dict with: total_positions, total_invested, total_current_value,
    total_pnl, total_pnl_pct, available_capital, portfolio_heat_pct,
    positions (list of position dicts with current P&L fields).
    """
    from config.settings import ACCOUNT_SIZE, PORTFOLIO_SETTINGS

    account_size = float(ACCOUNT_SIZE)
    positions = [p for p in load_positions() if p["status"] == "open"]

    signal_map: dict[str, dict] = {}
    if scan_results:
        signal_map = {s["ticker"]: s for s in scan_results}

    enriched: list[dict] = []
    total_invested = 0.0
    total_current = 0.0
    total_risk = 0.0

    for pos in positions:
        ticker = pos["ticker"]
        entry = pos.get("entry_price", 0.0)
        shares = pos.get("shares", 0)
        stop = pos.get("stop_loss", 0.0)

        cost_basis = entry * shares

        # Get current price
        sig = signal_map.get(ticker)
        current_price = _extract_price(sig) if sig else entry
        current_value = (current_price or entry) * shares

        pnl = current_value - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0.0

        # Risk: what we'd lose if stop is hit
        risk_per_share = entry - stop if stop else entry * 0.05
        position_risk = risk_per_share * shares

        total_invested += cost_basis
        total_current += current_value
        total_risk += position_risk

        enriched.append({
            **pos,
            "current_price": round(current_price or entry, 2),
            "current_value": round(current_value, 2),
            "cost_basis": round(cost_basis, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "position_risk": round(position_risk, 2),
            "days_held": _days_held(pos.get("entry_date", "")),
        })

    total_pnl = total_current - total_invested
    available_capital = max(account_size - total_invested, 0.0)
    heat_pct = (total_risk / account_size * 100) if account_size else 0.0

    return {
        "total_positions": len(positions),
        "total_invested": round(total_invested, 2),
        "total_current_value": round(total_current, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round((total_pnl / total_invested * 100) if total_invested else 0.0, 2),
        "available_capital": round(available_capital, 2),
        "portfolio_heat_pct": round(heat_pct, 2),
        "positions": enriched,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_price(signal: dict) -> Optional[float]:
    """Extract current price from a signal dict."""
    price = signal.get("entry")
    if price:
        return float(price)
    indicators = signal.get("indicators", {})
    p = indicators.get("current_price")
    return float(p) if p else None


def _days_held(entry_date_str: str) -> int:
    """Calculate days held from entry date string."""
    if not entry_date_str:
        return 0
    try:
        entry = date.fromisoformat(entry_date_str)
        return (date.today() - entry).days
    except Exception:
        return 0
