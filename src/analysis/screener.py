"""
Stock screening engine for KešMani.

Scores each ticker on a composite 0–100 scale across five dimensions:
  - Trend (25%)        : MA alignment, price position
  - Momentum (25%)     : RSI positioning, MACD signal
  - Volume (20%)       : Volume surge, accumulation/distribution
  - Fundamental (15%)  : Earnings & valuation quality
  - Relative strength (15%): Performance vs SPY over 1M / 3M

The output is a ranked list of ticker dicts with individual sub-scores
and a composite score, ready for display or signal generation.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from config.settings import SCREENER_WEIGHTS, TECHNICAL_SETTINGS
from src.analysis.technical import compute_all_indicators
from src.data.fundamentals import fetch_fundamentals, score_fundamentals
from src.data.market_data import fetch_ohlcv

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sub-score calculators
# ---------------------------------------------------------------------------

def _trend_score(indicators: dict) -> float:
    """
    Score the trend strength on 0–100.

    Rubric:
    - BULLISH alignment (price > SMA20 > SMA50 > SMA200): 60–100
    - Partial bullish: 30–60
    - BEARISH: 0–30
    """
    if not indicators:
        return 50.0

    trend = indicators.get("trend", "NEUTRAL")
    price = indicators.get("current_price", 0.0)
    sma20 = indicators.get("sma_20")
    sma50 = indicators.get("sma_50")
    sma200 = indicators.get("sma_200")

    base = 50.0
    if trend == "BULLISH":
        base = 80.0
    elif trend == "BEARISH":
        base = 20.0

    # Bonus/penalty for distance above/below key MAs
    if sma50 and price and sma50 > 0:
        pct_above_50 = (price - sma50) / sma50 * 100
        base += min(10.0, max(-10.0, pct_above_50))

    if sma200 and price and sma200 > 0:
        above_200 = price > sma200
        base += 10.0 if above_200 else -10.0

    return round(min(100.0, max(0.0, base)), 2)


def _momentum_score(indicators: dict) -> float:
    """
    Score the momentum on 0–100.

    Rubric:
    - RSI in ideal range (40–65): high score
    - MACD bullish crossover: bonus
    - Overbought (>70) or oversold (<30): penalty
    """
    if not indicators:
        return 50.0

    rsi = indicators.get("rsi")
    macd_cross = indicators.get("macd_crossover", "none")
    macd_hist = indicators.get("macd_histogram", 0.0)

    score = 50.0

    if rsi is not None:
        if 40 <= rsi <= 65:
            score += 30.0
        elif 65 < rsi <= 70:
            score += 15.0
        elif rsi > 70:
            score -= 20.0
        elif rsi < 30:
            score -= 15.0
        elif 30 <= rsi < 40:
            score += 5.0

    if macd_cross == "bullish_crossover":
        score += 20.0
    elif macd_cross == "bearish_crossover":
        score -= 20.0

    if macd_hist is not None:
        score += 5.0 if macd_hist > 0 else -5.0

    return round(min(100.0, max(0.0, score)), 2)


def _volume_score(indicators: dict) -> float:
    """
    Score volume behaviour on 0–100.

    High volume on upside price action = accumulation = bullish.
    """
    if not indicators:
        return 50.0

    vol_ratio = indicators.get("volume_ratio", 1.0)
    price = indicators.get("current_price", 0.0)
    sma20 = indicators.get("sma_20")

    score = 50.0
    if vol_ratio >= 2.0:
        score += 30.0
    elif vol_ratio >= 1.5:
        score += 20.0
    elif vol_ratio >= 1.2:
        score += 10.0
    elif vol_ratio < 0.7:
        score -= 15.0

    # Bonus if price is above 20-day MA (accumulation pattern)
    if sma20 and price and price > sma20:
        score += 10.0

    # Bonus for Bollinger squeeze (pending breakout)
    if indicators.get("bb_squeeze"):
        score += 10.0

    return round(min(100.0, max(0.0, score)), 2)


def _relative_strength_score(ticker: str, spy_df: pd.DataFrame) -> float:
    """
    Score relative strength vs SPY over 1M and 3M.

    Parameters
    ----------
    ticker:
        Symbol to compare.
    spy_df:
        OHLCV DataFrame for SPY.

    Returns
    -------
    Score 0–100.
    """
    df = fetch_ohlcv(ticker)
    if df.empty or spy_df.empty:
        return 50.0

    score = 50.0
    try:
        # 1-month RS
        if len(df) >= 21 and len(spy_df) >= 21:
            ticker_ret_1m = (df["Close"].iloc[-1] / df["Close"].iloc[-21]) - 1
            spy_ret_1m = (spy_df["Close"].iloc[-1] / spy_df["Close"].iloc[-21]) - 1
            rs_1m = ticker_ret_1m - spy_ret_1m
            score += min(25.0, max(-25.0, rs_1m * 200))

        # 3-month RS
        if len(df) >= 63 and len(spy_df) >= 63:
            ticker_ret_3m = (df["Close"].iloc[-1] / df["Close"].iloc[-63]) - 1
            spy_ret_3m = (spy_df["Close"].iloc[-1] / spy_df["Close"].iloc[-63]) - 1
            rs_3m = ticker_ret_3m - spy_ret_3m
            score += min(25.0, max(-25.0, rs_3m * 150))
    except Exception as exc:
        logger.debug("RS calculation failed for %s: %s", ticker, exc)

    return round(min(100.0, max(0.0, score)), 2)


# ---------------------------------------------------------------------------
# Composite scorer
# ---------------------------------------------------------------------------

def score_ticker(ticker: str, spy_df: Optional[pd.DataFrame] = None) -> dict:
    """
    Compute the full composite score for a single ticker.

    Parameters
    ----------
    ticker:
        Symbol to score.
    spy_df:
        Pre-fetched SPY DataFrame (optional, avoids repeat fetches).

    Returns
    -------
    Dict with sub-scores and composite score (0–100).
    """
    df = fetch_ohlcv(ticker)
    if df.empty:
        return _empty_score(ticker)

    indicators = compute_all_indicators(df)
    if not indicators:
        return _empty_score(ticker)

    fundamentals = fetch_fundamentals(ticker)
    fund_score = score_fundamentals(fundamentals)

    if spy_df is None:
        spy_df = fetch_ohlcv("SPY")

    trend = _trend_score(indicators)
    momentum = _momentum_score(indicators)
    volume = _volume_score(indicators)
    rs = _relative_strength_score(ticker, spy_df)

    weights = SCREENER_WEIGHTS
    composite = (
        trend * weights["trend"]
        + momentum * weights["momentum"]
        + volume * weights["volume"]
        + fund_score * weights["fundamental"]
        + rs * weights["relative_strength"]
    )

    return {
        "ticker": ticker,
        "composite_score": round(composite, 2),
        "trend_score": trend,
        "momentum_score": momentum,
        "volume_score": volume,
        "fundamental_score": fund_score,
        "rs_score": rs,
        "indicators": indicators,
        "fundamentals": fundamentals,
    }


def _empty_score(ticker: str) -> dict:
    """Return a placeholder score dict when data is unavailable."""
    return {
        "ticker": ticker,
        "composite_score": 0.0,
        "trend_score": 0.0,
        "momentum_score": 0.0,
        "volume_score": 0.0,
        "fundamental_score": 0.0,
        "rs_score": 0.0,
        "indicators": {},
        "fundamentals": {},
    }


def run_screener(tickers: list[str]) -> list[dict]:
    """
    Score all tickers and return a ranked list.

    Parameters
    ----------
    tickers:
        List of equity symbols.

    Returns
    -------
    List of score dicts sorted by composite_score descending.
    """
    spy_df = fetch_ohlcv("SPY")
    results: list[dict] = []
    for ticker in tickers:
        try:
            result = score_ticker(ticker, spy_df)
            results.append(result)
        except Exception as exc:
            logger.error("Screener failed for %s: %s", ticker, exc)
            results.append(_empty_score(ticker))

    return sorted(results, key=lambda x: x["composite_score"], reverse=True)
