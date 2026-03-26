"""
Fundamentals fetching module for Kesmani.

Pulls P/E, forward P/E, PEG, earnings growth, revenue growth, profit
margins, market cap, and dividend yield via yfinance's info dictionary.
All functions degrade gracefully — a missing field returns None, never
an exception that would crash the dashboard.
"""

import logging
from typing import Any, Optional

import yfinance as yf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_get(info: dict, key: str, default: Any = None) -> Any:
    """Return info[key] or default, suppressing any KeyError/TypeError."""
    try:
        val = info.get(key)
        return val if val is not None else default
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_fundamentals(ticker: str) -> dict:
    """
    Fetch key fundamental metrics for a single ticker.

    Parameters
    ----------
    ticker:
        Equity symbol (e.g. "NVDA").

    Returns
    -------
    Dict with the following keys (value is None if unavailable):
        pe_ratio, forward_pe, peg_ratio, eps_growth_qoq, eps_growth_yoy,
        revenue_growth, profit_margin, market_cap, dividend_yield,
        earnings_per_share, price_to_book, beta, short_ratio.
    """
    try:
        info = yf.Ticker(ticker).info
    except Exception as exc:
        logger.error("Failed to fetch fundamentals for %s: %s", ticker, exc)
        return _empty_fundamentals(ticker)

    return {
        "ticker": ticker,
        "pe_ratio": _safe_get(info, "trailingPE"),
        "forward_pe": _safe_get(info, "forwardPE"),
        "peg_ratio": _safe_get(info, "pegRatio"),
        "eps_growth_qoq": _safe_get(info, "earningsQuarterlyGrowth"),
        "eps_growth_yoy": _safe_get(info, "earningsGrowth"),
        "revenue_growth": _safe_get(info, "revenueGrowth"),
        "profit_margin": _safe_get(info, "profitMargins"),
        "market_cap": _safe_get(info, "marketCap"),
        "dividend_yield": _safe_get(info, "dividendYield"),
        "earnings_per_share": _safe_get(info, "trailingEps"),
        "price_to_book": _safe_get(info, "priceToBook"),
        "beta": _safe_get(info, "beta"),
        "short_ratio": _safe_get(info, "shortRatio"),
        "company_name": _safe_get(info, "longName", ticker),
        "sector": _safe_get(info, "sector", "N/A"),
        "industry": _safe_get(info, "industry", "N/A"),
    }


def fetch_all_fundamentals(tickers: list[str]) -> dict[str, dict]:
    """
    Fetch fundamentals for a list of tickers.

    Returns
    -------
    Dict mapping ticker → fundamentals dict.
    """
    result: dict[str, dict] = {}
    for ticker in tickers:
        result[ticker] = fetch_fundamentals(ticker)
    return result


def _empty_fundamentals(ticker: str) -> dict:
    """Return a skeleton fundamentals dict with all values None."""
    return {
        "ticker": ticker,
        "pe_ratio": None,
        "forward_pe": None,
        "peg_ratio": None,
        "eps_growth_qoq": None,
        "eps_growth_yoy": None,
        "revenue_growth": None,
        "profit_margin": None,
        "market_cap": None,
        "dividend_yield": None,
        "earnings_per_share": None,
        "price_to_book": None,
        "beta": None,
        "short_ratio": None,
        "company_name": ticker,
        "sector": "N/A",
        "industry": "N/A",
    }


def score_fundamentals(fundamentals: dict) -> float:
    """
    Score a ticker's fundamentals on a 0–100 scale.

    Scoring rubric (higher = better):
    - Positive earnings growth (YoY): +30 pts
    - Forward P/E < 30: +20 pts (scaled)
    - Revenue growth > 0: +20 pts
    - Positive profit margin: +15 pts
    - PEG < 2: +15 pts

    Returns 50.0 (neutral) when most data is missing.
    """
    score = 0.0
    weight_applied = 0.0

    # Earnings growth YoY (0–30 pts)
    eg = fundamentals.get("eps_growth_yoy")
    if eg is not None:
        pts = min(30.0, max(0.0, eg * 100))  # e.g. 0.30 growth → 30 pts
        score += pts
        weight_applied += 30.0

    # Forward P/E (0–20 pts — lower is better)
    fpe = fundamentals.get("forward_pe")
    if fpe is not None and fpe > 0:
        pts = max(0.0, 20.0 - (fpe / 50.0) * 20.0)  # 0 → 20 pts; 50 → 0 pts
        score += pts
        weight_applied += 20.0

    # Revenue growth (0–20 pts)
    rg = fundamentals.get("revenue_growth")
    if rg is not None:
        pts = min(20.0, max(0.0, rg * 100))
        score += pts
        weight_applied += 20.0

    # Profit margin (0–15 pts)
    pm = fundamentals.get("profit_margin")
    if pm is not None:
        pts = min(15.0, max(0.0, pm * 100))
        score += pts
        weight_applied += 15.0

    # PEG ratio (0–15 pts — below 1 is ideal)
    peg = fundamentals.get("peg_ratio")
    if peg is not None and peg > 0:
        pts = max(0.0, 15.0 * (1 - min(peg / 3.0, 1.0)))
        score += pts
        weight_applied += 15.0

    if weight_applied == 0:
        return 50.0  # neutral when no data

    # Normalise to 0–100
    return round((score / weight_applied) * 100, 2)
