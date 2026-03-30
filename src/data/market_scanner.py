"""
Market scanner module for KešMani.

Scans the full FULL_UNIVERSE of 200+ tickers, ranks them by composite
score, and provides filtering by sector, signal type, price range,
and minimum score.  Designed for repeated intraday use with caching.

Key public functions:
  scan_market()          — Scan a list of tickers (default: FULL_UNIVERSE)
  scan_by_sector()       — Scan only tickers belonging to one sector
  get_top_picks()        — Return the top N across all or filtered sectors
  get_sector_rotation()  — Rank sectors by average composite score
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from config.settings import (
    FULL_UNIVERSE,
    SCAN_UNIVERSE,
    SECTOR_LABELS,
    TICKER_SECTORS,
)
from src.analysis.screener import run_screener, score_ticker
from src.analysis.signals import generate_all_signals, generate_signal
from src.data.market_data import fetch_ohlcv

logger = logging.getLogger(__name__)

# Merge SECTOR_LABELS with the watchlist TICKER_SECTORS so every ticker
# is covered by a sector lookup regardless of source.
_SECTOR_MAP: dict[str, str] = {**TICKER_SECTORS, **SECTOR_LABELS}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_sector(ticker: str) -> str:
    """Return the human-readable sector for a ticker, or 'Unknown'."""
    return _SECTOR_MAP.get(ticker, "Unknown")


def _tickers_for_sectors(sectors: list[str]) -> list[str]:
    """Return all tickers whose sector matches one of the requested sectors."""
    return [t for t in FULL_UNIVERSE if _get_sector(t) in sectors]


def _tickers_for_category(category: str) -> list[str]:
    """Return tickers belonging to the named SCAN_UNIVERSE category."""
    return SCAN_UNIVERSE.get(category, [])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_market(
    tickers: list[str] | None = None,
    account_size: float | None = None,
    sectors: list[str] | None = None,
    signal_filter: list[str] | None = None,
    min_score: float = 0.0,
    min_price: float | None = None,
    max_price: float | None = None,
    quick: bool = False,
    max_workers: int = 10,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """
    Scan tickers and return signal dicts ranked by composite score.

    Parameters
    ----------
    tickers:
        List of symbols to scan.  Defaults to FULL_UNIVERSE.
    account_size:
        Portfolio value used for position sizing (passed to generate_signal).
    sectors:
        If provided, only scan tickers whose sector is in this list.
    signal_filter:
        If provided, only return results whose signal matches.
    min_score:
        Minimum composite score to include in results.
    min_price:
        Minimum current price filter.
    max_price:
        Maximum current price filter.
    quick:
        When True, skip tickers that already have a fresh cache entry
        (speeds up repeated intraday runs).
    max_workers:
        Number of parallel threads used for data fetching (default 10).
    progress_callback:
        Optional ``Callable[[completed, total], None]`` invoked after each
        ticker completes.  Use this to update a Streamlit progress bar.

    Returns
    -------
    List of signal dicts sorted by composite_score descending.
    """
    universe = tickers or FULL_UNIVERSE

    # Sector pre-filter
    if sectors:
        universe = [t for t in universe if _get_sector(t) in sectors]

    if quick:
        from config.settings import CACHE_DIR, DATA_SETTINGS
        import time
        from pathlib import Path

        def _is_fresh(ticker: str) -> bool:
            path = CACHE_DIR / f"{ticker}_1y.parquet"
            if not path.exists():
                return False
            age = (time.time() - path.stat().st_mtime) / 60
            return age < DATA_SETTINGS["cache_ttl_minutes"]

        universe = [t for t in universe if _is_fresh(t)] or universe

    logger.info("Scanning %d tickers…", len(universe))

    # Parallel data prefetch so screener hits cache
    total = len(universe)
    completed = 0

    def _prefetch(ticker: str) -> str:
        fetch_ohlcv(ticker)
        return ticker

    if progress_callback is not None:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_prefetch, t): t for t in universe}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    logger.debug("Prefetch error: %s", exc)
                completed += 1
                progress_callback(completed, total)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            list(executor.map(_prefetch, universe))

    screener_results = run_screener(universe)
    signals = generate_all_signals(screener_results, account_size)

    # Attach sector label to every signal
    for sig in signals:
        sig.setdefault("sector", _get_sector(sig["ticker"]))

    # Apply post-scan filters
    filtered: list[dict] = []
    for sig in signals:
        if sig["composite_score"] < min_score:
            continue
        if signal_filter and sig["signal"] not in signal_filter:
            continue
        price = sig.get("entry") or sig.get("indicators", {}).get("current_price")
        if min_price is not None and price is not None and price < min_price:
            continue
        if max_price is not None and price is not None and price > max_price:
            continue
        filtered.append(sig)

    return filtered


def scan_by_sector(
    sector: str,
    account_size: float | None = None,
    **kwargs,
) -> list[dict]:
    """
    Scan only tickers belonging to the named sector.

    Parameters
    ----------
    sector:
        Sector label (e.g. "Technology", "Healthcare").
        Also accepts a SCAN_UNIVERSE category key (e.g. "ai_and_cloud").
    account_size:
        Portfolio value for position sizing.
    **kwargs:
        Additional filters forwarded to scan_market().

    Returns
    -------
    List of signal dicts sorted by composite_score descending.
    """
    # Try SCAN_UNIVERSE category first, then sector label lookup
    if sector in SCAN_UNIVERSE:
        tickers = _tickers_for_category(sector)
    else:
        tickers = _tickers_for_sectors([sector])

    if not tickers:
        logger.warning("No tickers found for sector '%s'", sector)
        return []

    return scan_market(tickers=tickers, account_size=account_size, **kwargs)


def get_top_picks(
    n: int = 10,
    sectors: list[str] | None = None,
    account_size: float | None = None,
    signal_filter: list[str] | None = None,
) -> list[dict]:
    """
    Return the top N picks across all sectors, or filtered to specific sectors.

    Parameters
    ----------
    n:
        Number of top picks to return.
    sectors:
        Optional list of sector labels to restrict the scan.
    account_size:
        Portfolio value for position sizing.
    signal_filter:
        Optional signal types to include (default: BUY and STRONG BUY).

    Returns
    -------
    Up to N signal dicts sorted by composite_score descending.
    """
    if signal_filter is None:
        signal_filter = ["STRONG BUY", "BUY"]

    results = scan_market(
        sectors=sectors,
        account_size=account_size,
        signal_filter=signal_filter,
    )
    return results[:n]


def get_sector_rotation(
    account_size: float | None = None,
) -> list[dict]:
    """
    Compare average composite scores across all SCAN_UNIVERSE sectors.

    Identifies where institutional money is rotating — sectors with
    rising average scores indicate accumulation; falling scores indicate
    distribution.

    Returns
    -------
    List of dicts sorted by avg_score descending:
        [{"sector": str, "avg_score": float, "ticker_count": int,
          "strong_buys": int, "buys": int, "best_ticker": str,
          "best_score": float}, ...]
    """
    # Run full scan once
    all_signals = scan_market(account_size=account_size)
    if not all_signals:
        return []

    # Aggregate by sector
    sector_data: dict[str, list[dict]] = {}
    for sig in all_signals:
        sector = sig.get("sector", "Unknown")
        sector_data.setdefault(sector, []).append(sig)

    rotation: list[dict] = []
    for sector, sigs in sector_data.items():
        scores = [s["composite_score"] for s in sigs]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        best = max(sigs, key=lambda x: x["composite_score"])
        rotation.append({
            "sector": sector,
            "avg_score": round(avg_score, 2),
            "ticker_count": len(sigs),
            "strong_buys": sum(1 for s in sigs if s["signal"] == "STRONG BUY"),
            "buys": sum(1 for s in sigs if s["signal"] == "BUY"),
            "best_ticker": best["ticker"],
            "best_score": best["composite_score"],
        })

    return sorted(rotation, key=lambda x: x["avg_score"], reverse=True)
