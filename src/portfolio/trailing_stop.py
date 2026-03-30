"""
Trailing stop engine for KešMani.

Provides ATR-based and percentage-based trailing stop calculations,
and a helper that updates open positions' stop_loss values when the
trailing stop has moved above the current stop.

Public functions
---------------
calculate_atr_trailing_stop(entry_price, atr, multiplier) → float
calculate_percentage_trailing_stop(current_price, trail_pct) → float
update_trailing_stops(positions) → list[dict]   (with updated stop_loss values)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Individual trailing stop calculations
# ---------------------------------------------------------------------------

def calculate_atr_trailing_stop(
    entry_price: float,
    atr: float,
    multiplier: float = 2.0,
) -> float:
    """
    Calculate an ATR-based trailing stop.

    Stop = current_price - (ATR × multiplier).

    Parameters
    ----------
    entry_price:
        The current (or entry) price of the position.
    atr:
        Current 14-period ATR value.
    multiplier:
        ATR multiplier (default 2.0 — standard Chandelier exit).

    Returns
    -------
    Trailing stop price (rounded to 2 decimal places).
    """
    if atr <= 0 or entry_price <= 0:
        raise ValueError(f"entry_price ({entry_price}) and atr ({atr}) must be > 0")
    stop = entry_price - (atr * multiplier)
    return round(max(0.01, stop), 2)


def calculate_percentage_trailing_stop(
    current_price: float,
    trail_pct: float = 0.08,
) -> float:
    """
    Calculate a percentage-based trailing stop.

    Stop = current_price × (1 - trail_pct).

    Parameters
    ----------
    current_price:
        The current market price of the position.
    trail_pct:
        Trailing percentage as a decimal (default 0.08 = 8 %).

    Returns
    -------
    Trailing stop price (rounded to 2 decimal places).
    """
    if current_price <= 0:
        raise ValueError(f"current_price ({current_price}) must be > 0")
    if not 0 < trail_pct < 1:
        raise ValueError(f"trail_pct ({trail_pct}) must be between 0 and 1")
    stop = current_price * (1 - trail_pct)
    return round(stop, 2)


# ---------------------------------------------------------------------------
# Batch updater
# ---------------------------------------------------------------------------

def update_trailing_stops(
    positions: list[dict],
    trail_pct: float = 0.08,
    use_atr: bool = False,
    atr_multiplier: float = 2.0,
) -> list[dict]:
    """
    Update stop_loss values for open positions using trailing stop logic.

    For each position the trailing stop is calculated from the live price.
    The stop_loss is only raised — never lowered — so existing stops are
    protected.

    Parameters
    ----------
    positions:
        List of enriched position dicts (from ``get_portfolio_summary``).
        Each dict must have: ticker, live_price, stop_loss.
        When ``use_atr=True``, each dict must also have
        ``indicators.atr`` or ``atr``.
    trail_pct:
        Trailing percentage (default 0.08 = 8 %).  Used when
        ``use_atr=False``.
    use_atr:
        When True, use ATR-based trailing stop instead of percentage.
    atr_multiplier:
        ATR multiplier for ATR-based trailing stop (default 2.0).

    Returns
    -------
    A new list of position dicts with updated ``stop_loss`` values.
    The original list is not mutated.
    """
    updated: list[dict] = []
    for pos in positions:
        pos_copy = dict(pos)
        live = pos_copy.get("live_price") or pos_copy.get("entry_price", 0.0)
        current_stop = pos_copy.get("stop_loss", 0.0)

        try:
            if use_atr:
                atr = (
                    pos_copy.get("atr")
                    or pos_copy.get("indicators", {}).get("atr")
                )
                if atr:
                    new_stop = calculate_atr_trailing_stop(live, float(atr), atr_multiplier)
                else:
                    new_stop = calculate_percentage_trailing_stop(live, trail_pct)
            else:
                new_stop = calculate_percentage_trailing_stop(live, trail_pct)

            # Only raise the stop — never lower it
            if new_stop > current_stop:
                pos_copy["stop_loss"] = new_stop
                logger.debug(
                    "Trailing stop updated for %s: %.2f → %.2f",
                    pos_copy.get("ticker"), current_stop, new_stop,
                )
        except Exception as exc:
            logger.warning("Trailing stop failed for %s: %s", pos_copy.get("ticker"), exc)

        updated.append(pos_copy)
    return updated
