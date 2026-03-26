"""
Reusable styled data table components for the Kesmani dashboard.
"""

from typing import Optional
import pandas as pd
import streamlit as st

from src.utils.helpers import fmt_currency, fmt_pct, signal_color, signal_emoji


def screener_table(signals: list[dict]) -> None:
    """
    Render an interactive screener table with color-coded signals.

    Parameters
    ----------
    signals:
        List of signal dicts from generate_all_signals().
    """
    if not signals:
        st.info("No data available. Run the screener first.")
        return

    rows = []
    for s in signals:
        ind = s.get("indicators", {})
        rows.append(
            {
                "Ticker": s["ticker"],
                "Signal": f"{signal_emoji(s['signal'])} {s['signal']}",
                "Score": s["composite_score"],
                "Price": fmt_currency(ind.get("current_price")),
                "RSI": f"{ind.get('rsi', 0):.1f}" if ind.get("rsi") else "N/A",
                "Trend": ind.get("trend", "N/A"),
                "Vol Ratio": f"{ind.get('volume_ratio', 1.0):.1f}x",
                "Entry": fmt_currency(s.get("entry")),
                "Stop": fmt_currency(s.get("stop_loss")),
                "Target 1": fmt_currency(s.get("target_1")),
                "R:R": f"{s.get('rr_ratio', 'N/A')}:1",
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score": st.column_config.ProgressColumn(
                "Score", min_value=0, max_value=100, format="%.0f"
            ),
        },
    )


def positions_table(positions: list[dict]) -> None:
    """
    Render the open positions table with live P&L.

    Parameters
    ----------
    positions:
        Enriched position dicts from get_portfolio_summary().
    """
    if not positions:
        st.info("No open positions.")
        return

    rows = []
    for p in positions:
        pnl_pct = p.get("unrealized_pnl_pct", 0.0)
        rows.append(
            {
                "Ticker": p["ticker"],
                "Entry Date": p.get("entry_date", ""),
                "Shares": p["shares"],
                "Entry Price": fmt_currency(p["entry_price"]),
                "Current Price": fmt_currency(p.get("live_price")),
                "Market Value": fmt_currency(p.get("market_value")),
                "Unrealized P&L": fmt_currency(p.get("unrealized_pnl")),
                "P&L %": fmt_pct(pnl_pct),
                "Stop Loss": fmt_currency(p["stop_loss"]),
                "Target 1": fmt_currency(p.get("target_1")),
                "Status": "⚠️ AT STOP" if p.get("at_stop") else ("💰 TARGET HIT" if p.get("at_target_1") else "✅ Active"),
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def closed_trades_table(closed_trades: list[dict]) -> None:
    """Render the closed trade history table."""
    if not closed_trades:
        st.info("No closed trades yet.")
        return

    rows = []
    for t in closed_trades:
        rows.append(
            {
                "Ticker": t["ticker"],
                "Entry Date": t.get("entry_date", ""),
                "Exit Date": t.get("exit_date", ""),
                "Entry Price": fmt_currency(t.get("entry_price")),
                "Exit Price": fmt_currency(t.get("exit_price")),
                "Shares": t.get("shares", 0),
                "P&L": fmt_currency(t.get("pnl")),
                "P&L %": fmt_pct(t.get("pnl_pct")),
                "Reason": t.get("reason", ""),
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
