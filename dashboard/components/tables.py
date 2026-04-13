"""
Reusable styled data table components for the KešMani dashboard.
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
                "Recommendation": f"{signal_emoji(s['signal'])} {s['signal']}",
                "Health Score (0-100)": s["composite_score"],
                "Current Price": fmt_currency(ind.get("current_price")),
                "RSI (momentum)": f"{ind.get('rsi', 0):.1f}" if ind.get("rsi") else "N/A",
                "Trend Direction": ind.get("trend", "N/A"),
                "Volume Surge": f"{ind.get('volume_ratio', 1.0):.1f}x",
                "Buy At": fmt_currency(s.get("entry")),
                "Stop Loss": fmt_currency(s.get("stop_loss")),
                "Take Profit": fmt_currency(s.get("target_1")),
                "Reward/Risk": f"{s.get('rr_ratio', 'N/A')}:1",
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Health Score (0-100)": st.column_config.ProgressColumn(
                "Health Score (0-100)", min_value=0, max_value=100, format="%.0f"
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
        pnl = p.get("unrealized_pnl", 0.0)
        pnl_pct = p.get("unrealized_pnl_pct", 0.0)
        # Color-code the P&L
        if pnl > 0:
            pnl_str = f"🟢 +{fmt_currency(pnl)}"
        elif pnl < 0:
            pnl_str = f"🔴 {fmt_currency(pnl)}"
        else:
            pnl_str = fmt_currency(pnl)

        rows.append(
            {
                "Ticker": p["ticker"],
                "Entry Date": p.get("entry_date", ""),
                "Shares": p["shares"],
                "Entry Price": fmt_currency(p["entry_price"]),
                "Current Price": fmt_currency(p.get("live_price")),
                "Market Value": fmt_currency(p.get("market_value")),
                "Profit/Loss Now": pnl_str,
                "Return %": fmt_pct(pnl_pct),
                "Stop Loss": fmt_currency(p["stop_loss"]),
                "Target 1": fmt_currency(p.get("target_1")),
                "Status": "⚠️ AT STOP — Consider Selling" if p.get("at_stop") else ("💰 TARGET HIT — Consider Taking Profits" if p.get("at_target_1") else "✅ Active"),
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
        pnl = t.get("pnl", 0.0)
        result = "✅ Winner" if (pnl or 0) > 0 else "❌ Loser"
        rows.append(
            {
                "Ticker": t["ticker"],
                "Entry Date": t.get("entry_date", ""),
                "Exit Date": t.get("exit_date", ""),
                "Entry Price": fmt_currency(t.get("entry_price")),
                "Exit Price": fmt_currency(t.get("exit_price")),
                "Shares": t.get("shares", 0),
                "Total Profit/Loss": fmt_currency(pnl),
                "Return %": fmt_pct(t.get("pnl_pct")),
                "Result": result,
                "Reason": t.get("reason", ""),
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
