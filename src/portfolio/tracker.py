"""
Portfolio tracker for KešMani.

Persists open positions to a SQLite database (data/portfolio.db) for atomic,
crash-safe transactions.  Falls back to the legacy JSON file if the database
cannot be opened.  Public API is identical to the original JSON-backed version
so no page code changes are required.

Position schema:
  {
    "ticker": "NVDA",
    "entry_date": "2026-03-01",
    "entry_price": 142.50,
    "shares": 3.0,          # float — supports fractional shares
    "fractional": False,    # True when broker allows fractional shares
    "stop_loss": 138.00,
    "target_1": 155.00,
    "target_2": 163.00,
    "notes": ""
  }
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import DATA_DIR, PORTFOLIO_SETTINGS
from src.data.market_data import get_current_price

logger = logging.getLogger(__name__)

PORTFOLIO_FILE = DATA_DIR / "portfolio.json"
DB_FILE = DATA_DIR / "portfolio.db"

# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

def _init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they do not already exist."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS positions (
            id            TEXT PRIMARY KEY,
            data          TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS closed_trades (
            id            TEXT PRIMARY KEY,
            data          TEXT NOT NULL
        );
        """
    )
    conn.commit()


@contextmanager
def _db():
    """
    Context manager that yields an open, initialised SQLite connection.

    A new connection is created on every call so there is no shared
    connection state between threads — ``check_same_thread=False`` is
    safe here because each call to ``_db()`` owns its own connection.
    """
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        _init_db(conn)
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _load_portfolio() -> dict:
    """Load the portfolio from SQLite, returning a default skeleton if missing."""
    try:
        with _db() as conn:
            # Metadata
            rows = conn.execute("SELECT key, value FROM metadata").fetchall()
            meta = {r["key"]: r["value"] for r in rows}
            starting_capital = float(meta.get("starting_capital", PORTFOLIO_SETTINGS["starting_capital"]))
            cash = float(meta.get("cash", starting_capital))
            last_updated = meta.get("last_updated", datetime.now().isoformat())

            # Positions
            pos_rows = conn.execute("SELECT data FROM positions").fetchall()
            positions = [json.loads(r["data"]) for r in pos_rows]

            # Closed trades
            ct_rows = conn.execute("SELECT data FROM closed_trades ORDER BY rowid").fetchall()
            closed_trades = [json.loads(r["data"]) for r in ct_rows]

            return {
                "starting_capital": starting_capital,
                "cash": cash,
                "positions": positions,
                "closed_trades": closed_trades,
                "last_updated": last_updated,
            }
    except Exception as exc:
        logger.error("SQLite load failed (%s), falling back to JSON", exc)
        return _load_portfolio_json()


def _save_portfolio(data: dict) -> None:
    """Persist the portfolio dict atomically to SQLite."""
    try:
        with _db() as conn:
            with conn:  # atomic transaction
                conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                    ("starting_capital", str(data.get("starting_capital", PORTFOLIO_SETTINGS["starting_capital"]))),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                    ("cash", str(data.get("cash", 0.0))),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                    ("last_updated", data.get("last_updated", datetime.now().isoformat())),
                )
                # Replace all positions
                conn.execute("DELETE FROM positions")
                for pos in data.get("positions", []):
                    conn.execute(
                        "INSERT INTO positions (id, data) VALUES (?, ?)",
                        (pos["id"], json.dumps(pos, default=str)),
                    )
                # Upsert closed trades (append-only, never delete)
                for ct in data.get("closed_trades", []):
                    conn.execute(
                        "INSERT OR IGNORE INTO closed_trades (id, data) VALUES (?, ?)",
                        (ct["id"], json.dumps(ct, default=str)),
                    )
    except Exception as exc:
        logger.error("SQLite save failed (%s), falling back to JSON", exc)
        _save_portfolio_json(data)


# ---------------------------------------------------------------------------
# JSON fallback helpers (legacy)
# ---------------------------------------------------------------------------

def _load_portfolio_json() -> dict:
    if not PORTFOLIO_FILE.exists():
        return _default_portfolio()
    try:
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load portfolio JSON: %s", exc)
        return _default_portfolio()


def _save_portfolio_json(data: dict) -> None:
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
    shares: int | float,
    stop_loss: float,
    target_1: Optional[float] = None,
    target_2: Optional[float] = None,
    notes: str = "",
    fractional: bool = False,
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
        Number of shares (int for whole shares, float when fractional=True).
    stop_loss:
        Stop-loss price.
    target_1, target_2:
        Price targets (optional).
    notes:
        Free-text notes.
    fractional:
        Set True for brokers that support fractional shares (e.g. Robinhood,
        Schwab).  When True, ``shares`` is stored as a float.

    Returns
    -------
    The newly created position dict.
    """
    portfolio = _load_portfolio()
    shares_value: float = float(shares) if fractional else float(int(shares))
    cost_basis = entry_price * shares_value

    position: dict = {
        "id": _generate_id(),
        "ticker": ticker.upper(),
        "entry_date": datetime.now().strftime("%Y-%m-%d"),
        "entry_price": round(entry_price, 2),
        "shares": shares_value,
        "fractional": fractional,
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
    logger.info("Added position: %s x%.4f @ $%.2f", ticker, shares_value, entry_price)
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
