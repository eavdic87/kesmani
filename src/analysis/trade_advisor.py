"""
KešMani Trade Advisor — VP-Level Trade Analysis Engine.

Analyzes market scanner results through the lens of a veteran institutional
trader with 30+ years of experience. Generates high-confidence trade
recommendations with complete execution details.

Philosophy:
- Capital preservation first, profit second.
- Only trade when the edge is clear and multiple indicators align.
- Size positions based on conviction level.
- Always have an exit plan before entering.
- Never fight the trend.

Only recommendations with confidence >= 75 are surfaced to the user.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_CONFIDENCE: float = 75.0

_SIGNAL_RANK: dict[str, int] = {
    "STRONG BUY": 5,
    "BUY": 4,
    "HOLD": 3,
    "SELL": 2,
    "AVOID": 1,
}

_URGENCY_LABELS: dict[str, str] = {
    "NOW": "🔴 NOW",
    "TODAY": "🟡 TODAY",
    "THIS_WEEK": "🔵 THIS WEEK",
    "WATCH": "⚫ WATCH",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_market(
    scan_results: list[dict],
    account_size: float = 5000.0,
) -> dict:
    """
    Run full VP-level market analysis.

    Parameters
    ----------
    scan_results:
        List of signal dicts from scan_market().
    account_size:
        Portfolio size in dollars.

    Returns
    -------
    Dict with:
        - market_regime: str
        - market_summary: str
        - sector_analysis: dict
        - recommended_trades: list[dict]
        - risk_warnings: list[str]
        - portfolio_suggestion: str
    """
    if not scan_results:
        return _empty_analysis()

    market_regime = _detect_market_regime(scan_results)
    market_summary = _build_market_summary(scan_results, market_regime)
    sector_analysis = _analyze_sectors(scan_results)
    recommended_trades = generate_trade_recommendations(scan_results, account_size)
    risk_warnings = _build_risk_warnings(scan_results, market_regime)
    portfolio_suggestion = _build_portfolio_suggestion(
        recommended_trades, account_size, market_regime
    )

    return {
        "market_regime": market_regime,
        "market_summary": market_summary,
        "sector_analysis": sector_analysis,
        "recommended_trades": recommended_trades,
        "risk_warnings": risk_warnings,
        "portfolio_suggestion": portfolio_suggestion,
    }


def generate_trade_recommendations(
    scan_results: list[dict],
    account_size: float = 5000.0,
    timeframe: str = "swing",
) -> list[dict]:
    """
    Generate ranked trade recommendations from scan results.

    Only returns trades with confidence >= 75.

    Parameters
    ----------
    scan_results:
        List of signal dicts.
    account_size:
        Portfolio value in dollars.
    timeframe:
        "day", "swing" (default), or "position".

    Returns
    -------
    List of recommendation dicts, sorted by confidence descending.
    """
    buy_signals = [
        s for s in scan_results
        if s.get("signal") in ("STRONG BUY", "BUY")
    ]

    recommendations: list[dict] = []
    sector_data = _analyze_sectors(scan_results)
    market_regime = _detect_market_regime(scan_results)

    for sig in buy_signals:
        try:
            confidence = _calculate_confidence(sig, market_regime, sector_data)
            if confidence < MIN_CONFIDENCE:
                continue

            rec = _build_recommendation(
                sig, confidence, account_size, timeframe,
                sector_data, market_regime
            )
            recommendations.append(rec)
        except Exception as exc:
            ticker = sig.get("ticker", "?")
            logger.warning("Failed to build recommendation for %s: %s", ticker, exc)
            continue

    recommendations.sort(key=lambda r: r["confidence"], reverse=True)
    return recommendations


def generate_sell_recommendations(
    open_positions: list[dict],
    scan_results: list[dict],
) -> list[dict]:
    """
    Analyze open positions and generate sell recommendations.

    Triggers on: stop loss hit, target reached, trend reversal,
    max hold period exceeded, or indicators turned bearish.

    Parameters
    ----------
    open_positions:
        List of position dicts from position_monitor.
    scan_results:
        Latest scan results for current price/signal data.

    Returns
    -------
    List of sell alert dicts sorted by urgency.
    """
    if not open_positions or not scan_results:
        return []

    # Build lookup: ticker → signal dict
    signal_map = {s["ticker"]: s for s in scan_results}
    alerts: list[dict] = []

    for pos in open_positions:
        ticker = pos.get("ticker", "")
        sig = signal_map.get(ticker)
        if not sig:
            continue

        current_price = _get_price(sig)
        entry_price = pos.get("entry_price", 0.0)
        stop_loss = pos.get("stop_loss", 0.0)
        target_1 = pos.get("target_1", 0.0)
        target_2 = pos.get("target_2", 0.0)
        signal = sig.get("signal", "HOLD")

        alert = None

        # Check stop loss
        if stop_loss and current_price and current_price <= stop_loss:
            alert = {
                "ticker": ticker,
                "alert_type": "STOP_HIT",
                "current_price": current_price,
                "level": stop_loss,
                "action": f"SELL ALL — Stop Loss Hit at ${stop_loss:.2f}",
                "urgency": "NOW",
                "pnl_pct": ((current_price - entry_price) / entry_price * 100) if entry_price else 0,
            }

        # Check target 1
        elif target_1 and current_price and current_price >= target_1 and not pos.get("target_1_hit"):
            alert = {
                "ticker": ticker,
                "alert_type": "TARGET_1_HIT",
                "current_price": current_price,
                "level": target_1,
                "action": f"SELL 50% — Target 1 reached at ${target_1:.2f}. Move stop to breakeven.",
                "urgency": "TODAY",
                "pnl_pct": ((current_price - entry_price) / entry_price * 100) if entry_price else 0,
            }

        # Check target 2
        elif target_2 and current_price and current_price >= target_2:
            alert = {
                "ticker": ticker,
                "alert_type": "TARGET_2_HIT",
                "current_price": current_price,
                "level": target_2,
                "action": f"SELL ALL — Target 2 reached at ${target_2:.2f}. Full exit.",
                "urgency": "TODAY",
                "pnl_pct": ((current_price - entry_price) / entry_price * 100) if entry_price else 0,
            }

        # Check trend reversal (signal turned negative)
        elif signal in ("SELL", "AVOID") and entry_price and current_price:
            alert = {
                "ticker": ticker,
                "alert_type": "TREND_REVERSAL",
                "current_price": current_price,
                "level": None,
                "action": f"Consider SELLING — Signal flipped to {signal}. Protect gains.",
                "urgency": "TODAY",
                "pnl_pct": ((current_price - entry_price) / entry_price * 100) if entry_price else 0,
            }

        if alert:
            alerts.append(alert)

    urgency_order = {"NOW": 0, "TODAY": 1, "THIS_WEEK": 2, "WATCH": 3}
    alerts.sort(key=lambda a: urgency_order.get(a["urgency"], 4))
    return alerts


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _detect_market_regime(scan_results: list[dict]) -> str:
    """
    Determine market regime: BULLISH, BEARISH, NEUTRAL, or VOLATILE.

    Based on:
    - % of bullish signals in scan universe
    - Average composite score
    - Benchmark performance proxy
    """
    if not scan_results:
        return "NEUTRAL"

    total = len(scan_results)
    buys = sum(1 for s in scan_results if s.get("signal") in ("STRONG BUY", "BUY"))
    sells = sum(1 for s in scan_results if s.get("signal") in ("SELL", "AVOID"))
    avg_score = sum(s.get("composite_score", 50) for s in scan_results) / total

    buy_pct = buys / total
    sell_pct = sells / total

    if avg_score >= 65 and buy_pct >= 0.40:
        return "BULLISH"
    if avg_score <= 40 or sell_pct >= 0.50:
        return "BEARISH"
    if sell_pct >= 0.30 or (buy_pct < 0.25 and sell_pct > 0.25):
        return "VOLATILE"
    return "NEUTRAL"


def _build_market_summary(scan_results: list[dict], regime: str) -> str:
    """Build a 2–3 sentence market assessment."""
    total = len(scan_results)
    buys = sum(1 for s in scan_results if s.get("signal") in ("STRONG BUY", "BUY"))
    strong_buys = sum(1 for s in scan_results if s.get("signal") == "STRONG BUY")
    avg_score = sum(s.get("composite_score", 50) for s in scan_results) / total if total else 50

    regime_desc = {
        "BULLISH": "The market is showing broad bullish momentum",
        "BEARISH": "Market conditions are bearish with widespread selling pressure",
        "VOLATILE": "Markets are volatile — proceed with caution and smaller position sizes",
        "NEUTRAL": "Mixed market conditions — selective opportunities exist",
    }

    desc = regime_desc.get(regime, "Market conditions are mixed")
    buy_pct = buys / total * 100 if total else 0

    return (
        f"{desc}. {buy_pct:.0f}% of the scan universe ({buys}/{total} tickers) "
        f"are showing BUY or STRONG BUY signals, with {strong_buys} high-conviction setups. "
        f"Average composite score: {avg_score:.1f}/100."
    )


def _analyze_sectors(scan_results: list[dict]) -> dict:
    """
    Analyze sector performance from scan results.

    Returns dict mapping sector → {avg_score, signal_dist, top_ticker, trend}.
    """
    sector_map: dict[str, list[dict]] = {}
    for sig in scan_results:
        sector = sig.get("sector", "Unknown")
        sector_map.setdefault(sector, []).append(sig)

    analysis: dict[str, dict] = {}
    for sector, sigs in sector_map.items():
        scores = [s.get("composite_score", 50) for s in sigs]
        avg_score = sum(scores) / len(scores) if scores else 50
        buys = sum(1 for s in sigs if s.get("signal") in ("STRONG BUY", "BUY"))
        sells = sum(1 for s in sigs if s.get("signal") in ("SELL", "AVOID"))
        best = max(sigs, key=lambda x: x.get("composite_score", 0))

        if avg_score >= 65:
            trend = "HOT 🔥"
        elif avg_score >= 50:
            trend = "WARM"
        elif avg_score >= 40:
            trend = "COOL"
        else:
            trend = "COLD ❄️"

        analysis[sector] = {
            "avg_score": round(avg_score, 1),
            "ticker_count": len(sigs),
            "buys": buys,
            "sells": sells,
            "top_ticker": best.get("ticker", ""),
            "trend": trend,
        }

    return analysis


def _calculate_confidence(
    signal: dict,
    market_regime: str,
    sector_data: dict,
) -> float:
    """
    Calculate trade confidence score (0–100).

    Weights:
    - Composite score (25%)
    - Signal strength (25%)
    - Trend alignment (15%)
    - Volume confirmation (15%)
    - Risk/reward quality (10%)
    - Sector momentum (10%)
    """
    score = 0.0

    # Composite score (25%)
    composite = signal.get("composite_score", 50)
    score += (composite / 100) * 25

    # Signal strength (25%)
    signal_str = signal.get("signal", "HOLD")
    signal_score = {"STRONG BUY": 25, "BUY": 18}.get(signal_str, 0)
    score += signal_score

    # Trend alignment (15%)
    indicators = signal.get("indicators", {})
    trend = indicators.get("trend", "NEUTRAL")
    if trend == "BULLISH" and market_regime in ("BULLISH", "NEUTRAL"):
        score += 15
    elif trend == "BULLISH":
        score += 8

    # Volume confirmation (15%)
    vol_ratio = indicators.get("volume_ratio", 1.0) or 1.0
    if vol_ratio >= 2.0:
        score += 15
    elif vol_ratio >= 1.5:
        score += 10
    elif vol_ratio >= 1.0:
        score += 5

    # Risk/reward quality (10%)
    rr = signal.get("rr_ratio") or 0
    if rr >= 3.0:
        score += 10
    elif rr >= 2.0:
        score += 7
    elif rr >= 1.5:
        score += 4

    # Sector momentum (10%)
    sector = signal.get("sector", "Unknown")
    sector_info = sector_data.get(sector, {})
    sector_avg = sector_info.get("avg_score", 50)
    if sector_avg >= 65:
        score += 10
    elif sector_avg >= 50:
        score += 5

    return round(min(score, 100.0), 1)


def _assess_urgency(signal: dict) -> str:
    """
    Determine trade urgency.

    - STRONG BUY + high volume + bullish MACD → NOW
    - Strong setup today → TODAY
    - Good setup forming → THIS_WEEK
    - Interesting but needs confirmation → WATCH
    """
    indicators = signal.get("indicators", {})
    sig_str = signal.get("signal", "HOLD")
    macd = indicators.get("macd_crossover", "none")
    vol_ratio = indicators.get("volume_ratio", 1.0) or 1.0
    composite = signal.get("composite_score", 50)

    if sig_str == "STRONG BUY" and macd == "bullish_crossover" and vol_ratio >= 1.5:
        return "NOW"
    if sig_str == "STRONG BUY" or (sig_str == "BUY" and composite >= 75 and vol_ratio >= 1.3):
        return "TODAY"
    if sig_str == "BUY" and composite >= 65:
        return "THIS_WEEK"
    return "WATCH"


def _generate_reasoning(
    signal: dict,
    sector_data: dict,
    market_regime: str,
) -> str:
    """
    Generate VP-level trade reasoning narrative.

    Reads like a professional analyst note — concise, specific, actionable.
    """
    ticker = signal.get("ticker", "?")
    indicators = signal.get("indicators", {})
    composite = signal.get("composite_score", 50)
    sig_str = signal.get("signal", "BUY")
    sector = signal.get("sector", "Unknown")

    rsi = indicators.get("rsi")
    macd = indicators.get("macd_crossover", "none")
    vol_ratio = indicators.get("volume_ratio", 1.0) or 1.0
    trend = indicators.get("trend", "NEUTRAL")
    rr = signal.get("rr_ratio") or 0

    parts: list[str] = []

    # Signal and score
    parts.append(
        f"{ticker} is showing a {sig_str} signal with a composite score of {composite:.0f}/100."
    )

    # Technical indicators
    if rsi:
        if rsi < 40:
            parts.append(f"RSI at {rsi:.0f} indicates oversold conditions — potential mean reversion.")
        elif rsi < 60:
            parts.append(f"RSI at {rsi:.0f} shows healthy momentum without being overbought.")
        else:
            parts.append(f"RSI at {rsi:.0f} — approaching overbought; tighter stop recommended.")

    if macd == "bullish_crossover":
        parts.append("Fresh bullish MACD crossover signals momentum shift to the upside.")
    elif macd == "bearish_crossover":
        parts.append("Note: recent bearish MACD crossover — watch for follow-through.")

    # Volume
    if vol_ratio >= 2.0:
        parts.append(f"Volume running at {vol_ratio:.1f}x the 20-day average — strong institutional participation.")
    elif vol_ratio >= 1.3:
        parts.append(f"Volume at {vol_ratio:.1f}x average — above-normal buying interest confirmed.")

    # Trend
    if trend == "BULLISH":
        parts.append(f"Price is trending above key moving averages — trade is with the trend.")

    # Sector
    sector_info = sector_data.get(sector, {})
    sector_avg = sector_info.get("avg_score", 50)
    sector_trend = sector_info.get("trend", "")
    if sector_avg >= 65:
        parts.append(f"{sector} sector is leading the market ({sector_trend}) — tailwind confirmed.")
    elif sector_avg < 45:
        parts.append(f"Caution: {sector} sector is underperforming — reduce size accordingly.")

    # Market regime
    if market_regime == "BULLISH":
        parts.append("Broad market is bullish — high-probability environment for long setups.")
    elif market_regime == "BEARISH":
        parts.append("Market regime is bearish — exercise extra caution and use smaller size.")

    # R:R
    if rr >= 2.0:
        parts.append(f"Risk/reward of {rr:.1f}:1 meets the minimum threshold for an institutional-grade setup.")

    return " ".join(parts)


def _generate_exit_plan(signal: dict, timeframe: str) -> str:
    """Generate a clear, specific exit plan in plain English."""
    entry = signal.get("entry") or _get_price(signal)
    stop = signal.get("stop_loss")
    t1 = signal.get("target_1")
    t2 = signal.get("target_2")
    ticker = signal.get("ticker", "?")

    max_days = {"day": 1, "swing": 10, "position": 30}.get(timeframe, 10)

    parts: list[str] = []

    if t1 and entry:
        parts.append(f"SELL 50% at ${t1:.2f} (Target 1). Move stop to breakeven (${entry:.2f}).")

    if t2:
        parts.append(f"SELL remaining at ${t2:.2f} (Target 2), or trail stop to Target 1.")

    if stop:
        parts.append(f"HARD STOP at ${stop:.2f} — no exceptions. Cut losses without hesitation.")

    parts.append(f"Maximum hold: {max_days} trading day{'s' if max_days != 1 else ''}.")

    if timeframe == "day":
        parts.append("Close position before market close if Target 1 not reached.")

    return " ".join(parts) if parts else f"Exit {ticker} if signal turns bearish or stop is hit."


def _build_recommendation(
    signal: dict,
    confidence: float,
    account_size: float,
    timeframe: str,
    sector_data: dict,
    market_regime: str,
) -> dict:
    """Assemble a complete trade recommendation dict."""
    ticker = signal.get("ticker", "?")
    sig_str = signal.get("signal", "BUY")
    sector = signal.get("sector", "Unknown")
    entry = signal.get("entry") or _get_price(signal) or 0.0
    stop = signal.get("stop_loss") or (entry * 0.95)
    t1 = signal.get("target_1") or (entry * 1.05)
    t2 = signal.get("target_2") or (entry * 1.10)
    shares = signal.get("position_shares") or max(1, int((account_size * 0.02) / max(entry - stop, 0.01)))

    # Limit order slightly below current price for better fill
    limit_price = round(entry * 0.998, 2) if entry else entry

    risk_dollars = round((entry - stop) * shares, 2) if entry and stop else 0.0
    reward_dollars = round((t1 - entry) * shares, 2) if t1 and entry else 0.0
    rr = round(reward_dollars / risk_dollars, 2) if risk_dollars and risk_dollars > 0 else 0.0

    urgency = _assess_urgency(signal)
    reasoning = _generate_reasoning(signal, sector_data, market_regime)
    exit_plan = _generate_exit_plan(signal, timeframe)

    timeframe_type = "day_trade" if timeframe == "day" else "swing_trade"
    max_days = {"day": 1, "swing": 10, "position": 30}.get(timeframe, 10)

    indicators = signal.get("indicators", {})
    rsi = indicators.get("rsi")
    macd = indicators.get("macd_crossover", "none")

    # Catalyst
    catalyst_parts: list[str] = []
    if sig_str == "STRONG BUY":
        catalyst_parts.append("High-conviction breakout setup")
    if macd == "bullish_crossover":
        catalyst_parts.append("bullish MACD crossover")
    if indicators.get("volume_ratio", 1.0) >= 1.5:
        catalyst_parts.append("above-average volume")
    if indicators.get("trend") == "BULLISH":
        catalyst_parts.append("uptrend confirmed")
    catalyst = ", ".join(catalyst_parts) or "Technical momentum"

    # Warnings
    warnings: list[str] = []
    if rsi and rsi > 65:
        warnings.append(f"RSI at {rsi:.0f} — approaching overbought territory")
    if signal.get("earnings_warning"):
        warnings.append("Earnings report within 7 days — elevated volatility risk")
    if market_regime == "BEARISH":
        warnings.append("Market regime is BEARISH — reduce position size by 50%")
    if market_regime == "VOLATILE":
        warnings.append("Volatile market — use wider stops and smaller size")

    # Broker steps
    broker_steps = [
        f"Open your brokerage app (Robinhood, Fidelity, TD Ameritrade, etc.)",
        f"Search for ticker: {ticker}",
        "Select 'Buy' → Choose order type",
        f"Set order type: LIMIT ORDER at ${limit_price:.2f}",
        f"Set quantity: {shares} share{'s' if shares != 1 else ''}",
        "Set Time in Force: GTC (Good Till Cancelled) for swing trades",
        "Review total cost and confirm",
        f"AFTER FILL: Immediately place a STOP-LOSS order at ${stop:.2f}",
        f"Set a price alert at ${t1:.2f} (Target 1)",
    ]

    # Pre-trade checklist
    checklist = [
        "✅ Check if earnings are within 7 days (avoid if yes)",
        f"✅ Market regime is {market_regime} — adjust size if BEARISH/VOLATILE",
        f"✅ Total cost (${entry * shares:,.2f}) fits within account budget",
        f"✅ Risk (${risk_dollars:.2f}) is ≤ 2% of account (${account_size * 0.02:,.2f})",
        "✅ VIX is below 25 (check market overview)",
        "✅ Not in first 15 minutes of market open (9:30–9:45 AM ET)",
        "✅ Stock is not gapping up/down > 3% today",
    ]

    return {
        "ticker": ticker,
        "sector": sector,
        "signal": sig_str,
        "confidence": confidence,
        "timeframe": timeframe_type,
        "reasoning": reasoning,
        "entry_price": round(entry, 2),
        "entry_type": "LIMIT",
        "limit_price": limit_price,
        "shares": shares,
        "total_cost": round(entry * shares, 2),
        "stop_loss": round(stop, 2),
        "stop_type": "hard",
        "target_1": round(t1, 2),
        "target_1_action": "Sell 50% of position",
        "target_2": round(t2, 2),
        "target_2_action": "Sell remaining, or trail stop to Target 1",
        "risk_dollars": risk_dollars,
        "reward_dollars": reward_dollars,
        "risk_reward_ratio": rr,
        "max_hold_days": max_days,
        "urgency": urgency,
        "catalyst": catalyst,
        "warnings": warnings,
        "broker_steps": broker_steps,
        "exit_plan": exit_plan,
        "pre_trade_checklist": checklist,
    }


def _get_price(signal: dict) -> float:
    """Extract current price from a signal dict."""
    price = signal.get("entry")
    if price:
        return float(price)
    indicators = signal.get("indicators", {})
    return float(indicators.get("current_price", 0) or 0)


def _build_risk_warnings(scan_results: list[dict], market_regime: str) -> list[str]:
    """Build list of market-wide risk cautions."""
    warnings: list[str] = []
    if market_regime == "BEARISH":
        warnings.append("⚠️ Market regime is BEARISH — strongly consider sitting on the sidelines or hedging.")
    if market_regime == "VOLATILE":
        warnings.append("⚠️ High volatility detected — reduce all position sizes by 50%.")

    total = len(scan_results)
    if total > 0:
        avoid_pct = sum(1 for s in scan_results if s.get("signal") == "AVOID") / total
        if avoid_pct > 0.5:
            warnings.append("⚠️ Over 50% of the universe showing AVOID signals — broad market weakness.")

    return warnings


def _build_portfolio_suggestion(
    recommendations: list[dict],
    account_size: float,
    market_regime: str,
) -> str:
    """
    Build a high-level portfolio allocation suggestion.
    """
    if not recommendations:
        return "No high-confidence setups identified at this time. Hold cash and wait for clearer signals."

    top = recommendations[:3]
    total_cost = sum(r["total_cost"] for r in top)
    cash_reserve = account_size - total_cost

    if market_regime == "BULLISH":
        allocation_note = "Market is bullish — deploy up to 70% of capital into these setups."
    elif market_regime == "BEARISH":
        allocation_note = "Market is bearish — limit total exposure to 30% of capital."
    else:
        allocation_note = "Mixed market — deploy 40–50% of capital, keep the rest in cash."

    picks = ", ".join(r["ticker"] for r in top)
    return (
        f"{allocation_note} Top setups: {picks}. "
        f"Estimated total deployment: ${total_cost:,.2f}. "
        f"Suggested cash reserve: ${max(cash_reserve, 0):,.2f}."
    )


def _empty_analysis() -> dict:
    """Return a safe empty analysis dict."""
    return {
        "market_regime": "NEUTRAL",
        "market_summary": "No scan data available. Run a market scan to populate analysis.",
        "sector_analysis": {},
        "recommended_trades": [],
        "risk_warnings": ["No data — run a market scan first."],
        "portfolio_suggestion": "Run a market scan to generate recommendations.",
    }
