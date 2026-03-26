"""
Common utilities for the Kesmani Trading Intelligence System.

Provides:
  - Logging setup
  - Number/currency/percentage formatters
  - Signal color helpers
  - Date utilities
"""

import logging
import sys
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(level: int = logging.INFO, log_file: Optional[str] = None) -> None:
    """
    Configure the root logger.

    Parameters
    ----------
    level:
        Logging level (default INFO).
    log_file:
        Optional path to a log file.  Console handler is always added.
    """
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, handlers=handlers, force=True)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def fmt_currency(value: Optional[float], symbol: str = "$") -> str:
    """Return a formatted currency string, e.g. '$1,234.56'."""
    if value is None:
        return "N/A"
    return f"{symbol}{value:,.2f}"


def fmt_pct(value: Optional[float], decimals: int = 2) -> str:
    """Return a formatted percentage string, e.g. '+3.45%'."""
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{decimals}f}%"


def fmt_large_number(value: Optional[float]) -> str:
    """Return a human-readable large number, e.g. '1.23B', '456.7M'."""
    if value is None:
        return "N/A"
    abs_val = abs(value)
    if abs_val >= 1e12:
        return f"${value / 1e12:.2f}T"
    if abs_val >= 1e9:
        return f"${value / 1e9:.2f}B"
    if abs_val >= 1e6:
        return f"${value / 1e6:.2f}M"
    if abs_val >= 1e3:
        return f"${value / 1e3:.2f}K"
    return f"${value:.2f}"


def fmt_ratio(value: Optional[float]) -> str:
    """Return a formatted ratio string, e.g. '23.45x'."""
    if value is None:
        return "N/A"
    return f"{value:.2f}x"


# ---------------------------------------------------------------------------
# Signal helpers
# ---------------------------------------------------------------------------

SIGNAL_COLORS: dict[str, str] = {
    "STRONG BUY": "#00cc44",
    "BUY": "#66cc00",
    "HOLD": "#ffcc00",
    "SELL": "#ff6600",
    "AVOID": "#cc0000",
}

SIGNAL_EMOJIS: dict[str, str] = {
    "STRONG BUY": "🚀",
    "BUY": "✅",
    "HOLD": "⏸️",
    "SELL": "💰",
    "AVOID": "🚫",
}


def signal_color(signal: str) -> str:
    """Return the hex color for a given signal string."""
    return SIGNAL_COLORS.get(signal, "#888888")


def signal_emoji(signal: str) -> str:
    """Return the emoji for a given signal string."""
    return SIGNAL_EMOJIS.get(signal, "❓")


def trend_color(trend: str) -> str:
    """Return a color for BULLISH / BEARISH / NEUTRAL trend."""
    return {"BULLISH": "#00cc44", "BEARISH": "#cc0000", "NEUTRAL": "#ffcc00"}.get(trend, "#888888")


# ---------------------------------------------------------------------------
# Date utilities
# ---------------------------------------------------------------------------

def market_date_label() -> str:
    """Return today's date in a friendly format."""
    return datetime.now().strftime("%A, %B %d, %Y")


def is_market_open() -> bool:
    """
    Rough check: returns True Mon–Fri between 09:30 and 16:00 ET.

    Note: Does not account for market holidays.
    """
    from datetime import timezone
    import zoneinfo

    try:
        et = zoneinfo.ZoneInfo("America/New_York")
        now_et = datetime.now(et)
        if now_et.weekday() >= 5:  # Saturday or Sunday
            return False
        open_time = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        close_time = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        return open_time <= now_et <= close_time
    except Exception:
        return False
