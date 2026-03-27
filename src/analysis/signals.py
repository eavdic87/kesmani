"""
Signal generation module for Kesmani.

Translates composite screener scores and technical indicators into
clear, actionable trading signals with entry, stop-loss, and target
price levels.

Signal hierarchy:
  STRONG BUY  : score > 80, bullish MACD crossover, RSI < 60, above 50-day MA
  BUY         : score > 65, positive trend, acceptable R:R
  HOLD        : existing positions not yet at target or stop
  SELL        : RSI > 75, bearish MACD crossover, or hit target
  AVOID       : score < 40, below 200-day MA, declining volume
"""

import logging
from typing import Optional

from config.settings import (
    PORTFOLIO_SETTINGS,
    SECTOR_LABELS,
    SIGNAL_THRESHOLDS,
    TECHNICAL_SETTINGS,
    TICKER_SECTORS,
    VIX_THRESHOLDS,
)

# Combined sector map (watchlist + full universe)
_SECTOR_MAP: dict[str, str] = {**TICKER_SECTORS, **SECTOR_LABELS}

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_signal(score_result: dict, account_size: Optional[float] = None) -> dict:
    """
    Generate a trading signal from a scored ticker result.

    Parameters
    ----------
    score_result:
        Output dict from screener.score_ticker().
    account_size:
        Current portfolio value in dollars (used for position sizing).
        Defaults to PORTFOLIO_SETTINGS["starting_capital"].

    Returns
    -------
    Dict with keys:
        ticker, signal, composite_score, entry, stop_loss, target_1,
        target_2, position_shares, position_value, risk_amount,
        rr_ratio, reasoning.
    """
    if account_size is None:
        account_size = PORTFOLIO_SETTINGS["starting_capital"]

    ticker = score_result.get("ticker", "UNKNOWN")
    composite = score_result.get("composite_score", 0.0)
    indicators = score_result.get("indicators", {})

    rsi = indicators.get("rsi")
    macd_cross = indicators.get("macd_crossover", "none")
    trend = indicators.get("trend", "NEUTRAL")
    price = indicators.get("current_price", 0.0)
    sma50 = indicators.get("sma_50")
    sma200 = indicators.get("sma_200")
    atr = indicators.get("atr")
    support = indicators.get("support")
    vol_ratio = indicators.get("volume_ratio", 1.0)

    thresholds = SIGNAL_THRESHOLDS

    # -----------------------------------------------------------------------
    # Determine signal
    # -----------------------------------------------------------------------
    signal = _classify_signal(
        composite, rsi, macd_cross, trend, price, sma50, sma200, vol_ratio, thresholds
    )

    # -----------------------------------------------------------------------
    # Entry / stop / target calculation
    # -----------------------------------------------------------------------
    entry, stop_loss, target_1, target_2 = _calculate_levels(
        signal, price, atr, support, PORTFOLIO_SETTINGS["default_rr_ratio"]
    )

    # -----------------------------------------------------------------------
    # Position sizing (1-2 % account risk)
    # -----------------------------------------------------------------------
    risk_pct = PORTFOLIO_SETTINGS["max_risk_per_trade"]
    risk_amount = account_size * risk_pct
    risk_per_share = (entry - stop_loss) if entry and stop_loss and (entry - stop_loss) > 0 else None
    position_shares = int(risk_amount / risk_per_share) if risk_per_share else 0
    position_value = position_shares * entry if entry else 0.0

    rr_ratio = None
    if entry and stop_loss and target_1:
        reward = target_1 - entry
        risk = entry - stop_loss
        rr_ratio = round(reward / risk, 2) if risk > 0 else None

    # -----------------------------------------------------------------------
    # Reasoning summary
    # -----------------------------------------------------------------------
    reasoning = _build_reasoning(
        signal, composite, rsi, macd_cross, trend, vol_ratio, rr_ratio
    )

    return {
        "ticker": ticker,
        "signal": signal,
        "composite_score": composite,
        "sector": _SECTOR_MAP.get(ticker, "Unknown"),
        "entry": round(entry, 2) if entry else None,
        "stop_loss": round(stop_loss, 2) if stop_loss else None,
        "target_1": round(target_1, 2) if target_1 else None,
        "target_2": round(target_2, 2) if target_2 else None,
        "position_shares": position_shares,
        "position_value": round(position_value, 2),
        "risk_amount": round(risk_amount, 2),
        "rr_ratio": rr_ratio,
        "reasoning": reasoning,
        "indicators": indicators,
        "earnings_warning": _check_earnings_warning(ticker),
        "vix_adjusted": _check_vix_adjustment(),
    }


def generate_all_signals(
    screener_results: list[dict],
    account_size: Optional[float] = None,
) -> list[dict]:
    """
    Generate signals for all screener results.

    Returns
    -------
    List of signal dicts sorted by composite_score descending.
    """
    signals: list[dict] = []
    for result in screener_results:
        try:
            sig = generate_signal(result, account_size)
            signals.append(sig)
        except Exception as exc:
            logger.error("Signal generation failed for %s: %s", result.get("ticker"), exc)
    return sorted(signals, key=lambda x: x["composite_score"], reverse=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _classify_signal(
    composite: float,
    rsi: Optional[float],
    macd_cross: str,
    trend: str,
    price: float,
    sma50: Optional[float],
    sma200: Optional[float],
    vol_ratio: float,
    thresholds: dict,
) -> str:
    """Apply signal classification rules."""
    # STRONG BUY conditions
    if (
        composite >= thresholds["strong_buy_min_score"]
        and (rsi is None or rsi < thresholds["strong_buy_max_rsi"])
        and macd_cross == "bullish_crossover"
        and trend in ("BULLISH", "NEUTRAL")
        and (sma50 is None or price > sma50)
        and vol_ratio >= 1.1
    ):
        return "STRONG BUY"

    # BUY conditions
    if (
        composite >= thresholds["buy_min_score"]
        and trend != "BEARISH"
        and (rsi is None or rsi < 75)
    ):
        return "BUY"

    # AVOID conditions
    if (
        composite < thresholds["avoid_max_score"]
        or (sma200 is not None and price < sma200)
        or (rsi is not None and rsi < 25)
    ):
        return "AVOID"

    # SELL signal
    if (
        rsi is not None and rsi > thresholds["sell_rsi"]
        and macd_cross == "bearish_crossover"
    ):
        return "SELL"

    return "HOLD"


def _calculate_levels(
    signal: str,
    price: float,
    atr: Optional[float],
    support: Optional[float],
    rr_ratio: float,
) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Calculate entry, stop-loss, and target levels.

    Stop-loss is placed at the greater of:
    - Just below the nearest support level
    - 1.5 × ATR below entry

    Targets use the configured R:R ratio.
    """
    if price <= 0:
        return None, None, None, None

    entry = price

    atr_stop = (entry - 1.5 * atr) if atr else None
    support_stop = support * 0.99 if support else None

    if atr_stop and support_stop:
        stop_loss = max(atr_stop, support_stop)  # use the higher (tighter) stop
    elif atr_stop:
        stop_loss = atr_stop
    elif support_stop:
        stop_loss = support_stop
    else:
        stop_loss = entry * 0.95  # default 5 % stop

    stop_loss = min(stop_loss, entry * 0.95)  # never more than 5 % away

    risk = entry - stop_loss
    target_1 = entry + risk * rr_ratio
    target_2 = entry + risk * (rr_ratio + 1.0)

    if signal in ("AVOID", "HOLD", "SELL"):
        return entry, stop_loss, target_1, target_2

    return entry, stop_loss, target_1, target_2


def _build_reasoning(
    signal: str,
    composite: float,
    rsi: Optional[float],
    macd_cross: str,
    trend: str,
    vol_ratio: float,
    rr_ratio: Optional[float],
) -> str:
    """Build a human-readable reasoning string for the signal."""
    parts: list[str] = []

    parts.append(f"Composite score: {composite:.0f}/100.")
    parts.append(f"Trend: {trend}.")

    if rsi is not None:
        rsi_label = "overbought" if rsi > 70 else ("oversold" if rsi < 30 else "healthy")
        parts.append(f"RSI {rsi:.1f} ({rsi_label}).")

    if macd_cross != "none":
        parts.append(f"MACD {macd_cross.replace('_', ' ')}.")

    if vol_ratio >= 1.5:
        parts.append(f"Volume surge {vol_ratio:.1f}x average.")
    elif vol_ratio < 0.8:
        parts.append(f"Below-average volume ({vol_ratio:.1f}x).")

    if rr_ratio:
        parts.append(f"Risk/reward: {rr_ratio:.1f}:1.")

    return " ".join(parts)


def _check_earnings_warning(ticker: str) -> bool:
    """
    Return True if earnings are expected within the next 7 days.

    Uses yfinance calendar data.  Returns False gracefully on any failure.
    """
    try:
        import yfinance as yf
        from datetime import datetime, timedelta

        try:
            from config.settings import DATA_SETTINGS
            warning_days = int(DATA_SETTINGS.get("earnings_warning_days", 7))
        except Exception:
            warning_days = 7

        t = yf.Ticker(ticker)
        cal = t.calendar
        if cal is None:
            return False
        # calendar can be a dict or DataFrame depending on yfinance version
        if hasattr(cal, "columns"):
            # DataFrame
            if "Earnings Date" in cal.columns:
                dates = cal["Earnings Date"].dropna().tolist()
            else:
                return False
        elif isinstance(cal, dict):
            dates = cal.get("Earnings Date", [])
            if not isinstance(dates, list):
                dates = [dates]
        else:
            return False

        now = datetime.now()
        cutoff = now + timedelta(days=warning_days)
        for d in dates:
            try:
                if hasattr(d, "to_pydatetime"):
                    d = d.to_pydatetime()
                if hasattr(d, "replace"):
                    d = d.replace(tzinfo=None)
                if now <= d <= cutoff:
                    return True
            except Exception:
                continue
    except Exception as exc:
        logger.debug("Earnings check failed for %s: %s", ticker, exc)
    return False


def _check_vix_adjustment() -> str | None:
    """
    Return a position-size note when VIX is elevated, or None when calm.

    Avoids a circular import by importing fetch_vix lazily.
    """
    try:
        from src.data.market_data import fetch_vix
        vix = fetch_vix()
        if vix is None:
            return None
        if vix >= VIX_THRESHOLDS["high_fear"]:
            return f"VIX {vix:.1f} — EXTREME FEAR: consider sitting out or reducing size by 75%."
        if vix >= VIX_THRESHOLDS["elevated"]:
            return f"VIX {vix:.1f} — ELEVATED: reduce position size by 50%."
        return None
    except Exception as exc:
        logger.debug("VIX check failed: %s", exc)
        return None
