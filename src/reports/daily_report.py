"""
Daily report generator for KešMani.

Produces a comprehensive morning briefing in three formats:
  1. Plain text   — for terminal output / logging
  2. HTML         — for email delivery
  3. Dict         — for the Streamlit dashboard

The report covers:
  - Market overview (SPY/QQQ/IWM + regime)
  - Top 5 watchlist setups
  - Open position updates
  - Catalyst calendar (next 7 days)
  - Risk dashboard
  - Recommended next steps
"""

import logging
from datetime import datetime
from typing import Optional

from src.analysis.risk_manager import calculate_portfolio_heat
from src.analysis.screener import run_screener
from src.analysis.signals import generate_all_signals
from src.data.market_data import get_market_snapshot, get_price_summary
from src.data.news_catalysts import get_upcoming_catalysts
from src.portfolio.tracker import get_portfolio_summary
from src.utils.helpers import fmt_currency, fmt_pct, market_date_label, signal_emoji
from config.settings import ALL_TICKERS, BENCHMARK_TICKERS, PORTFOLIO_SETTINGS, WATCHLIST

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Market regime
# ---------------------------------------------------------------------------

def _detect_regime(benchmarks: list[dict]) -> str:
    """
    Classify market regime as BULLISH, BEARISH, or NEUTRAL.

    Uses the average day-change of SPY, QQQ, IWM.
    """
    changes = [b.get("day_change_pct", 0.0) for b in benchmarks if b]
    if not changes:
        return "NEUTRAL"
    avg = sum(changes) / len(changes)
    if avg > 0.3:
        return "BULLISH"
    if avg < -0.3:
        return "BEARISH"
    return "NEUTRAL"


# ---------------------------------------------------------------------------
# Core report builder
# ---------------------------------------------------------------------------

def build_daily_report(
    tickers: Optional[list[str]] = None,
    account_size: Optional[float] = None,
) -> dict:
    """
    Build the full daily report as a structured dict.

    Parameters
    ----------
    tickers:
        Tickers to screen.  Defaults to all tickers minus benchmarks.
    account_size:
        Portfolio value.  Defaults to PORTFOLIO_SETTINGS["starting_capital"].

    Returns
    -------
    Dict with all report sections.
    """
    if account_size is None:
        account_size = PORTFOLIO_SETTINGS["starting_capital"]

    screener_tickers = tickers or [
        t for t in ALL_TICKERS if t not in BENCHMARK_TICKERS
    ]

    logger.info("Building daily report for %d tickers…", len(screener_tickers))

    # --- Market overview ---
    benchmark_snapshots = get_market_snapshot()
    regime = _detect_regime(benchmark_snapshots)

    # --- Screener & signals ---
    try:
        screener_results = run_screener(screener_tickers)
        signals = generate_all_signals(screener_results, account_size)
    except Exception as exc:
        logger.error("Screener/signal error: %s", exc)
        screener_results = []
        signals = []

    top_setups = [s for s in signals if s["signal"] in ("STRONG BUY", "BUY")][:5]

    # --- Portfolio ---
    try:
        portfolio = get_portfolio_summary()
        positions = portfolio.get("positions", [])
        heat = calculate_portfolio_heat(
            [
                {
                    "ticker": p["ticker"],
                    "shares": p["shares"],
                    "entry_price": p["entry_price"],
                    "stop_loss": p["stop_loss"],
                }
                for p in positions
            ],
            account_size,
        )
    except Exception as exc:
        logger.error("Portfolio error: %s", exc)
        portfolio = {}
        positions = []
        heat = {}

    # --- Catalysts ---
    try:
        catalysts = get_upcoming_catalysts(screener_tickers)
    except Exception as exc:
        logger.error("Catalyst error: %s", exc)
        catalysts = {"earnings": [], "warnings": [], "economic": []}

    # --- Next steps ---
    next_steps = _build_next_steps(top_setups, positions, heat, catalysts)

    return {
        "date": market_date_label(),
        "as_of": datetime.now().isoformat(),
        "regime": regime,
        "benchmarks": benchmark_snapshots,
        "top_setups": top_setups,
        "all_signals": signals,
        "screener_results": screener_results,
        "portfolio": portfolio,
        "heat": heat,
        "catalysts": catalysts,
        "next_steps": next_steps,
    }


# ---------------------------------------------------------------------------
# Plain-text formatter
# ---------------------------------------------------------------------------

def format_text_report(report: dict) -> str:
    """Render the daily report as a plain-text string."""
    lines: list[str] = []
    sep = "═" * 60

    lines.append(sep)
    lines.append(f"  📈 DAILY TRADING BRIEF — {report['date']}")
    lines.append(sep)
    lines.append("")

    # Market overview
    regime = report.get("regime", "NEUTRAL")
    regime_emoji = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "🟡"}.get(regime, "🟡")
    lines.append(f"MARKET OVERVIEW  {regime_emoji} {regime}")
    for b in report.get("benchmarks", []):
        chg = fmt_pct(b.get("day_change_pct"))
        lines.append(f"  {b.get('ticker','?'):4s}  {fmt_currency(b.get('current_price'))}  {chg}")
    lines.append("")

    # Top setups
    lines.append("─── TOP WATCHLIST SETUPS " + "─" * 35)
    setups = report.get("top_setups", [])
    if setups:
        for i, s in enumerate(setups, 1):
            emoji = signal_emoji(s["signal"])
            lines.append(
                f"  {i}. {s['ticker']:<6s} {emoji} {s['signal']}"
                f"  (Score: {s['composite_score']:.0f})"
            )
            lines.append(
                f"     Entry: {fmt_currency(s.get('entry'))}  "
                f"Stop: {fmt_currency(s.get('stop_loss'))}  "
                f"T1: {fmt_currency(s.get('target_1'))}  "
                f"R:R {s.get('rr_ratio', 'N/A')}:1"
            )
            if s.get("reasoning"):
                lines.append(f"     {s['reasoning']}")
            lines.append("")
    else:
        lines.append("  No high-conviction setups today.")
        lines.append("")

    # Open positions
    lines.append("─── OPEN POSITIONS " + "─" * 41)
    positions = report.get("portfolio", {}).get("positions", [])
    if positions:
        for p in positions:
            pnl_str = fmt_pct(p.get("unrealized_pnl_pct"))
            action = "⚠️ AT STOP" if p.get("at_stop") else ("💰 AT TARGET" if p.get("at_target_1") else "HOLD")
            lines.append(f"  {p['ticker']:<6s}  {pnl_str}  {action}")
    else:
        lines.append("  No open positions.")
    lines.append("")

    # Catalyst calendar
    lines.append("─── UPCOMING CATALYSTS " + "─" * 37)
    earnings = report.get("catalysts", {}).get("earnings", [])
    if earnings:
        for e in earnings[:5]:
            warn = "⚠️ " if e.get("warning") else "   "
            lines.append(
                f"  {warn}{e['ticker']:<6s} earnings in {e['days_until']} days"
                f" ({e['earnings_date'].strftime('%b %d') if hasattr(e['earnings_date'], 'strftime') else e['earnings_date']})"
            )
    else:
        lines.append("  No earnings in the next 14 days.")
    lines.append("")

    # Risk dashboard
    heat = report.get("heat", {})
    lines.append("─── RISK DASHBOARD " + "─" * 41)
    lines.append(
        f"  Portfolio Heat: {heat.get('total_heat_pct', 0):.1f}% / {heat.get('max_heat_pct', 8):.1f}% max  "
        f"{'✅ Within limit' if heat.get('within_limit', True) else '🚨 OVER LIMIT'}"
    )
    lines.append("")

    # Next steps
    lines.append("─── RECOMMENDED NEXT STEPS " + "─" * 33)
    for step in report.get("next_steps", []):
        lines.append(f"  {step}")
    lines.append("")
    lines.append(sep)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML formatter (for email)
# ---------------------------------------------------------------------------

def format_html_report(report: dict) -> str:
    """Render the daily report as an HTML string."""
    regime = report.get("regime", "NEUTRAL")
    regime_color = {"BULLISH": "#00cc44", "BEARISH": "#cc0000", "NEUTRAL": "#ffcc00"}.get(
        regime, "#888"
    )

    benchmarks_html = "".join(
        f"""
        <tr>
          <td style="font-weight:bold">{b.get('ticker','')}</td>
          <td>{fmt_currency(b.get('current_price'))}</td>
          <td style="color:{'#00cc44' if (b.get('day_change_pct') or 0) >= 0 else '#cc0000'}">
            {fmt_pct(b.get('day_change_pct'))}
          </td>
        </tr>"""
        for b in report.get("benchmarks", [])
    )

    setups_html = ""
    for s in report.get("top_setups", []):
        emoji = signal_emoji(s["signal"])
        setups_html += f"""
        <tr>
          <td style="font-weight:bold">{s['ticker']}</td>
          <td>{emoji} {s['signal']}</td>
          <td>{s['composite_score']:.0f}</td>
          <td>{fmt_currency(s.get('entry'))}</td>
          <td>{fmt_currency(s.get('stop_loss'))}</td>
          <td>{fmt_currency(s.get('target_1'))}</td>
          <td>{s.get('rr_ratio', 'N/A')}:1</td>
        </tr>"""

    positions_html = ""
    for p in report.get("portfolio", {}).get("positions", []):
        pct = p.get("unrealized_pnl_pct", 0.0)
        color = "#00cc44" if pct >= 0 else "#cc0000"
        positions_html += f"""
        <tr>
          <td style="font-weight:bold">{p['ticker']}</td>
          <td>{fmt_currency(p.get('entry_price'))}</td>
          <td>{fmt_currency(p.get('live_price'))}</td>
          <td style="color:{color}">{fmt_pct(pct)}</td>
          <td>{fmt_currency(p.get('stop_loss'))}</td>
        </tr>"""

    next_steps_html = "".join(
        f"<li>{step}</li>" for step in report.get("next_steps", [])
    )

    heat = report.get("heat", {})
    heat_color = "#00cc44" if heat.get("within_limit", True) else "#cc0000"

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; background: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; }}
  h1 {{ color: #58a6ff; }}
  h2 {{ color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 6px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
  th {{ background: #161b22; color: #8b949e; text-align: left; padding: 8px; border: 1px solid #30363d; }}
  td {{ padding: 8px; border: 1px solid #30363d; }}
  tr:nth-child(even) {{ background: #161b22; }}
  .regime {{ font-size: 1.4em; font-weight: bold; color: {regime_color}; }}
  .heat {{ color: {heat_color}; font-weight: bold; }}
  ul {{ padding-left: 20px; }}
  li {{ margin-bottom: 6px; }}
  .footer {{ font-size: 0.8em; color: #8b949e; margin-top: 30px; border-top: 1px solid #30363d; padding-top: 10px; }}
</style>
</head>
<body>
<h1>📈 Kesmani Daily Trading Brief</h1>
<p>{report['date']}</p>

<h2>Market Overview</h2>
<p class="regime">Market Regime: {regime}</p>
<table>
  <tr><th>Index</th><th>Price</th><th>Day Change</th></tr>
  {benchmarks_html}
</table>

<h2>Top Watchlist Setups</h2>
{"<p>No high-conviction setups today.</p>" if not report.get('top_setups') else f"""
<table>
  <tr><th>Ticker</th><th>Signal</th><th>Score</th><th>Entry</th><th>Stop</th><th>Target 1</th><th>R:R</th></tr>
  {setups_html}
</table>"""}

<h2>Open Positions</h2>
{"<p>No open positions.</p>" if not report.get('portfolio', {}).get('positions') else f"""
<table>
  <tr><th>Ticker</th><th>Entry</th><th>Current</th><th>P&L %</th><th>Stop</th></tr>
  {positions_html}
</table>"""}

<h2>Risk Dashboard</h2>
<p class="heat">Portfolio Heat: {heat.get('total_heat_pct', 0):.1f}% / {heat.get('max_heat_pct', 8):.1f}% max
{"✅ Within limit" if heat.get("within_limit", True) else "🚨 OVER LIMIT"}</p>

<h2>Recommended Next Steps</h2>
<ul>{next_steps_html}</ul>

<div class="footer">
  <p>⚠️ <strong>Disclaimer:</strong> Kesmani is a trading intelligence tool, not financial advice.
  All trading decisions carry risk. Past performance does not guarantee future results.
  Never risk more than you can afford to lose.</p>
  <p>Generated: {report.get('as_of', '')}</p>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _build_next_steps(
    top_setups: list[dict],
    positions: list[dict],
    heat: dict,
    catalysts: dict,
) -> list[str]:
    """Generate a prioritised action list."""
    steps: list[str] = []

    if heat and not heat.get("within_limit", True):
        steps.append("🚨 URGENT: Portfolio heat exceeds limit — reduce exposure before adding new positions")

    for s in top_setups[:3]:
        emoji = signal_emoji(s["signal"])
        steps.append(
            f"{emoji} Watch {s['ticker']} for entry near {fmt_currency(s.get('entry'))} "
            f"(stop: {fmt_currency(s.get('stop_loss'))}, target: {fmt_currency(s.get('target_1'))})"
        )

    for p in positions:
        if p.get("at_stop"):
            steps.append(f"⚠️ {p['ticker']} is at stop-loss — evaluate exit immediately")
        elif p.get("at_target_1"):
            steps.append(f"💰 {p['ticker']} hit Target 1 — consider taking partial profits")
        else:
            pct = p.get("unrealized_pnl_pct", 0)
            if pct > 10:
                steps.append(f"📌 {p['ticker']} up {pct:.1f}% — consider trailing stop")

    warnings = catalysts.get("warnings", [])
    for w in warnings:
        steps.append(
            f"⚠️ {w['ticker']} earnings in {w['days_until']} days — size down or wait for reaction"
        )

    if not steps:
        steps.append("✅ No immediate action required — monitor watchlist and wait for setups")

    return steps
