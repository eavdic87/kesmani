"""
Trade execution guide for Kesmani.

Translates a trading signal into a complete, step-by-step execution
plan that a VP-level trader would follow.  The plan covers:

  - Order type (LIMIT vs MARKET) with reasoning
  - Precise limit price
  - Entry timing guidance
  - Position-sizing confirmation
  - Scale-in tranches for larger positions
  - Hard stop-loss price and trailing-stop logic
  - Two profit targets with partial-profit plan
  - Broker click-by-click instructions
  - Pre-trade checklist
  - Risk warnings (earnings, VIX, gap-open, etc.)

All monetary values are rounded to 2 decimal places.
All percentages are expressed to 2 decimal places.
"""

import logging
from typing import Optional

from config.settings import MEGA_CAPS, PORTFOLIO_SETTINGS, TIMING_WINDOWS, VIX_THRESHOLDS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Limit-order discount below current price (fraction of price)
_LIMIT_DISCOUNT_MEGA = 0.002   # 0.2% for mega-caps
_LIMIT_DISCOUNT_MID = 0.004    # 0.4% for mid/small-caps

# Maximum recommended hold for swing trades (trading days)
_MAX_HOLD_DAYS = 21

# Position above which we scale in rather than going full size at once
_SCALE_IN_THRESHOLD = 5000.0   # dollar value


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_execution_plan(signal: dict, account_size: float) -> dict:
    """
    Generate a detailed execution plan for a trade signal.

    Parameters
    ----------
    signal:
        Output dict from signals.generate_signal() — must contain at
        minimum: ticker, signal, entry, stop_loss, target_1, target_2,
        position_shares, position_value, risk_amount.
    account_size:
        Current portfolio value in dollars.

    Returns
    -------
    Dict with full execution guidance:
        order_type, limit_price, timing, entry_strategy, scale_in_plan,
        position_size_shares, position_size_dollars, total_risk_dollars,
        stop_loss_type, stop_loss_price, target_1_price, target_2_price,
        partial_profit_plan, max_hold_days, broker_steps, checklist,
        warnings.
    """
    ticker = signal.get("ticker", "UNKNOWN")
    sig_type = signal.get("signal", "HOLD")
    entry = signal.get("entry")
    stop_loss = signal.get("stop_loss")
    target_1 = signal.get("target_1")
    target_2 = signal.get("target_2")
    shares = signal.get("position_shares", 0)
    position_value = signal.get("position_value", 0.0)
    risk_amount = signal.get("risk_amount", account_size * PORTFOLIO_SETTINGS["max_risk_per_trade"])
    vix_note = signal.get("vix_adjusted")
    earnings_warning = signal.get("earnings_warning", False)

    if entry is None or entry <= 0:
        return _empty_plan(ticker)

    # -----------------------------------------------------------------------
    # Order type
    # -----------------------------------------------------------------------
    order_type, order_reasoning = _determine_order_type(ticker, entry, vix_note)

    # -----------------------------------------------------------------------
    # Limit price
    # -----------------------------------------------------------------------
    discount = _LIMIT_DISCOUNT_MEGA if ticker in MEGA_CAPS else _LIMIT_DISCOUNT_MID
    limit_price = round(entry * (1 - discount), 2)

    # -----------------------------------------------------------------------
    # Timing
    # -----------------------------------------------------------------------
    timing = _determine_timing(sig_type)

    # -----------------------------------------------------------------------
    # Entry strategy
    # -----------------------------------------------------------------------
    entry_strategy = "scale_in" if position_value >= _SCALE_IN_THRESHOLD else "full_position"
    scale_in_plan = _build_scale_in_plan(shares, limit_price, entry_strategy)

    # -----------------------------------------------------------------------
    # Stop-loss
    # -----------------------------------------------------------------------
    stop_loss_type = "trailing_stop" if sig_type == "STRONG BUY" else "hard_stop"
    stop_price = round(stop_loss, 2) if stop_loss else round(entry * 0.95, 2)

    # -----------------------------------------------------------------------
    # Targets
    # -----------------------------------------------------------------------
    t1 = round(target_1, 2) if target_1 else None
    t2 = round(target_2, 2) if target_2 else None
    partial_plan = _build_partial_profit_plan(t1, t2, ticker)

    # -----------------------------------------------------------------------
    # Broker steps
    # -----------------------------------------------------------------------
    broker_steps = _build_broker_steps(
        ticker, order_type, limit_price, shares, stop_price, t1
    )

    # -----------------------------------------------------------------------
    # Checklist
    # -----------------------------------------------------------------------
    checklist = _build_checklist(earnings_warning, vix_note, account_size, risk_amount)

    # -----------------------------------------------------------------------
    # Warnings
    # -----------------------------------------------------------------------
    warnings = _build_warnings(earnings_warning, vix_note, entry, signal)

    return {
        "ticker": ticker,
        "signal": sig_type,
        "order_type": order_type,
        "order_reasoning": order_reasoning,
        "limit_price": limit_price,
        "timing": timing,
        "entry_strategy": entry_strategy,
        "scale_in_plan": scale_in_plan,
        "position_size_shares": shares,
        "position_size_dollars": round(position_value, 2),
        "total_risk_dollars": round(risk_amount, 2),
        "stop_loss_type": stop_loss_type,
        "stop_loss_price": stop_price,
        "target_1_price": t1,
        "target_2_price": t2,
        "partial_profit_plan": partial_plan,
        "max_hold_days": _MAX_HOLD_DAYS,
        "broker_steps": broker_steps,
        "checklist": checklist,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _determine_order_type(
    ticker: str, entry: float, vix_note: Optional[str]
) -> tuple[str, str]:
    """Return (order_type, reasoning) based on ticker liquidity and VIX."""
    if ticker in MEGA_CAPS and not vix_note:
        return (
            "MARKET",
            f"{ticker} is a mega-cap with extremely high liquidity. "
            "A market order during normal hours gives fast execution with minimal slippage.",
        )
    if vix_note:
        return (
            "LIMIT",
            "VIX is elevated — use a limit order to avoid paying up in a volatile tape.",
        )
    return (
        "LIMIT",
        "Limit orders give you price control and better average fills. "
        "Set the limit slightly below the current price to avoid chasing.",
    )


def _determine_timing(sig_type: str) -> str:
    """Return a timing recommendation string."""
    tw = TIMING_WINDOWS
    best = tw["best_entry"]
    second = tw["second_best"]
    lines = [
        f"Best entry window: {best['start_hour']}:{best['start_min']:02d} – "
        f"{best['end_hour']}:{best['end_min']:02d} AM ET "
        "(after morning volatility settles, institutional flow established).",
        f"Second best: {second['start_hour']}:{second['start_min']:02d} – "
        f"{second['end_hour']}:{second['end_min']:02d} PM ET "
        "(afternoon institutional accumulation window).",
        "Avoid: first 15 minutes and last 15 minutes of the session.",
    ]
    if sig_type == "STRONG BUY":
        lines.append(
            "Exception: if the stock is breaking out on heavy volume, "
            "do NOT wait — use a market order to capture the momentum."
        )
    return "  ".join(lines)


def _build_scale_in_plan(shares: int, limit_price: float, strategy: str) -> list[dict] | None:
    """Return scale-in tranches when position is large, else None."""
    if strategy != "scale_in" or shares == 0:
        return None
    tranche_1 = max(1, int(shares * 0.50))
    tranche_2 = max(1, int(shares * 0.25))
    tranche_3 = shares - tranche_1 - tranche_2
    return [
        {
            "tranche": 1,
            "shares": tranche_1,
            "trigger": "Initial entry at limit price",
            "price": limit_price,
            "pct": "50%",
        },
        {
            "tranche": 2,
            "shares": tranche_2,
            "trigger": "On a 1-3% pullback from entry (buy the dip)",
            "price": round(limit_price * 0.98, 2),
            "pct": "25%",
        },
        {
            "tranche": 3,
            "shares": tranche_3,
            "trigger": "On confirmation (new high above entry, strong volume)",
            "price": round(limit_price * 1.01, 2),
            "pct": "25%",
        },
    ]


def _build_partial_profit_plan(
    t1: Optional[float], t2: Optional[float], ticker: str
) -> str:
    """Return a human-readable partial-profit plan."""
    if t1 and t2:
        return (
            f"Take 50% off at Target 1 (${t1:,.2f}). "
            f"Trail the remaining 50% with a trailing stop toward Target 2 (${t2:,.2f}). "
            "Never let a winner turn into a loser — move stop to break-even after Target 1 is hit."
        )
    if t1:
        return f"Take full profit at Target 1 (${t1:,.2f}). No partial plan — full exit at target."
    return "Monitor price action and exit at your predetermined profit target."


def _build_broker_steps(
    ticker: str,
    order_type: str,
    limit_price: float,
    shares: int,
    stop_price: float,
    target_1: Optional[float],
) -> list[str]:
    """Return numbered broker click-through instructions."""
    steps = [
        "Open your brokerage app (Fidelity, Schwab, TD Ameritrade, IBKR, etc.)",
        f"Search for ticker: {ticker}",
        f"Select 'Trade' → 'Buy'",
    ]
    if order_type == "MARKET":
        steps.append("Select Order Type: 'Market Order'")
    else:
        steps.append(f"Select Order Type: 'Limit Order'")
        steps.append(f"Set Limit Price: ${limit_price:,.2f}")
    steps += [
        f"Set Quantity: {shares} share{'s' if shares != 1 else ''}",
        "Set Time in Force: 'Day' (expires at close) or 'GTC' (Good Till Cancelled)",
        "Review the order summary carefully before submitting",
        "Click 'Submit Order' / 'Place Order'",
        f"After your order fills: immediately place a STOP-LOSS order at ${stop_price:,.2f}",
        "Set the stop as a 'Stop Market' or 'Stop Limit' order (GTC)",
    ]
    if target_1:
        steps.append(
            f"Set a price alert at ${target_1:,.2f} (Target 1) to be notified when to take partial profits"
        )
    steps.append("Record this trade in your trading journal (ticker, date, price, size, reason)")
    return steps


def _build_checklist(
    earnings_warning: bool,
    vix_note: Optional[str],
    account_size: float,
    risk_amount: float,
) -> list[str]:
    """Return a pre-trade checklist."""
    risk_pct = (risk_amount / account_size * 100) if account_size > 0 else 0
    items = [
        "✅ Check if earnings are within 7 days — avoid holding small accounts through earnings",
        "✅ Verify market regime is not BEARISH (check Market Overview page)",
        f"✅ Confirm position risk ({risk_pct:.1f}%) does not exceed 2% of account",
        "✅ Ensure total portfolio heat (all open risk) stays under 8%",
        "✅ Check VIX — if above 25, reduce position size by 50%",
        "✅ Avoid entering in the first 15 minutes of market open (let volatility settle)",
        "✅ Confirm the stock isn't gapping up >3% at open — wait for a pullback",
        "✅ Check average daily volume — avoid illiquid stocks (<500K shares/day)",
        "✅ Do NOT average down into a losing position",
        "✅ Have your stop-loss price written down BEFORE you enter the trade",
    ]
    if earnings_warning:
        items.insert(0, "⚠️  EARNINGS WITHIN 7 DAYS — Consider waiting until after the report")
    if vix_note:
        items.insert(0 if not earnings_warning else 1, f"⚠️  {vix_note}")
    return items


def _build_warnings(
    earnings_warning: bool,
    vix_note: Optional[str],
    entry: float,
    signal: dict,
) -> list[str]:
    """Collect all warnings applicable to this trade."""
    warnings: list[str] = []
    if earnings_warning:
        warnings.append(
            "⚠️  Earnings report expected within 7 days. "
            "Options premiums will be inflated. "
            "Consider waiting until after the report to avoid gap risk."
        )
    if vix_note:
        warnings.append(f"⚠️  {vix_note}")

    rsi = signal.get("indicators", {}).get("rsi")
    if rsi and rsi > 70:
        warnings.append(
            f"⚠️  RSI {rsi:.1f} — stock is overbought on the daily chart. "
            "Consider waiting for a pullback to a moving average before entering."
        )

    sma20 = signal.get("indicators", {}).get("sma_20")
    if sma20 and entry and entry > sma20 * 1.10:
        pct_above = (entry / sma20 - 1) * 100
        warnings.append(
            f"⚠️  Stock is {pct_above:.1f}% above its 20-day MA — extended from the mean. "
            "Odds of a near-term pullback are elevated."
        )

    vol_ratio = signal.get("indicators", {}).get("volume_ratio", 1.0)
    if vol_ratio < 0.5:
        warnings.append(
            "⚠️  Volume is significantly below average. "
            "Thin volume can lead to wide spreads and poor fills."
        )

    if not warnings:
        warnings.append("✅ No major warnings. Proceed with standard risk management rules.")

    return warnings


def _empty_plan(ticker: str) -> dict:
    """Return a placeholder plan when price data is unavailable."""
    return {
        "ticker": ticker,
        "signal": "UNKNOWN",
        "order_type": "N/A",
        "order_reasoning": "Price data unavailable — cannot generate execution plan.",
        "limit_price": None,
        "timing": "N/A",
        "entry_strategy": "N/A",
        "scale_in_plan": None,
        "position_size_shares": 0,
        "position_size_dollars": 0.0,
        "total_risk_dollars": 0.0,
        "stop_loss_type": "N/A",
        "stop_loss_price": None,
        "target_1_price": None,
        "target_2_price": None,
        "partial_profit_plan": "N/A",
        "max_hold_days": 0,
        "broker_steps": ["Price data unavailable — check ticker symbol and try again."],
        "checklist": [],
        "warnings": ["⚠️  No price data available for this ticker."],
    }
