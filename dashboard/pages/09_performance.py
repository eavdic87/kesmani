"""
Page 9: Performance Analytics — KešMani Dashboard

Win rate, expectancy, profit factor, max drawdown, equity curve,
PnL by ticker, average hold time, and win rate by setup type
(when journal data is available).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.portfolio.tracker import get_portfolio_summary
from src.analysis.risk_manager import portfolio_statistics
from src.utils.helpers import fmt_currency, fmt_pct
from dashboard.components.charts import get_chart_layout

st.set_page_config(
    page_title="KešMani | Performance",
    page_icon="📈",
    layout="wide",
)

from dashboard.theme import apply_theme
apply_theme()

st.title("📈 Performance Analytics — KešMani")
st.caption("Analyze your closed trade history and portfolio performance metrics.")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
portfolio = get_portfolio_summary()
closed_trades = portfolio.get("closed_trades", [])

if not closed_trades:
    st.info(
        "No closed trades yet. Start trading and close positions to see performance analytics here."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Build DataFrame
# ---------------------------------------------------------------------------
df = pd.DataFrame(closed_trades)

# Ensure numeric columns
for col in ("entry_price", "exit_price", "pnl", "pnl_pct", "shares"):
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# Parse dates
for dcol in ("entry_date", "exit_date"):
    if dcol in df.columns:
        df[dcol] = pd.to_datetime(df[dcol], errors="coerce")

df = df.sort_values("exit_date")

# ---------------------------------------------------------------------------
# Summary stats
# ---------------------------------------------------------------------------
stats = portfolio_statistics(closed_trades)

wins = df[df["pnl"] > 0]
losses = df[df["pnl"] <= 0]

win_rate = stats.get("win_rate", 0.0)
avg_win = stats.get("avg_win", 0.0)
avg_loss = stats.get("avg_loss", 0.0)
profit_factor = stats.get("profit_factor", 0.0)
sharpe = stats.get("estimated_sharpe", 0.0)
expectancy = avg_win * (win_rate / 100) + avg_loss * (1 - win_rate / 100)

# Max drawdown on equity curve
df["cumulative_pnl"] = df["pnl"].cumsum()
rolling_max = df["cumulative_pnl"].cummax()
drawdown = df["cumulative_pnl"] - rolling_max
max_drawdown = float(drawdown.min())

# Best and worst trades
best_trade = df.loc[df["pnl_pct"].idxmax()] if not df.empty else None
worst_trade = df.loc[df["pnl_pct"].idxmin()] if not df.empty else None

# Average hold time
if "entry_date" in df.columns and "exit_date" in df.columns:
    df["hold_days"] = (df["exit_date"] - df["entry_date"]).dt.days
    avg_hold = df["hold_days"].mean()
else:
    avg_hold = None

# ---------------------------------------------------------------------------
# Key metrics row
# ---------------------------------------------------------------------------
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Win Rate", f"{win_rate:.1f}%")
m2.metric("Profit Factor", f"{profit_factor:.2f}x" if profit_factor < 999 else "∞")
m3.metric("Avg Win", fmt_currency(avg_win))
m4.metric("Avg Loss", fmt_currency(avg_loss))
m5.metric("Max Drawdown", fmt_currency(max_drawdown))
m6.metric("Est. Sharpe", f"{sharpe:.2f}")

if best_trade is not None and worst_trade is not None:
    b1, b2 = st.columns(2)
    with b1:
        st.success(
            f"🏆 **Best Trade:** {best_trade.get('ticker', '?')} — "
            f"{fmt_pct(best_trade.get('pnl_pct', 0))} ({fmt_currency(best_trade.get('pnl', 0))})"
        )
    with b2:
        st.error(
            f"📉 **Worst Trade:** {worst_trade.get('ticker', '?')} — "
            f"{fmt_pct(worst_trade.get('pnl_pct', 0))} ({fmt_currency(worst_trade.get('pnl', 0))})"
        )

if avg_hold is not None:
    st.caption(f"⏱️ Average hold time: **{avg_hold:.1f} days**")

st.divider()

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
layout = get_chart_layout()

chart_col1, chart_col2 = st.columns(2)

# Equity curve
with chart_col1:
    st.subheader("📈 Equity Curve")
    eq_fig = go.Figure()
    eq_fig.add_trace(
        go.Scatter(
            x=df["exit_date"],
            y=df["cumulative_pnl"],
            mode="lines+markers",
            name="Cumulative P&L",
            line=dict(color="#3B82F6", width=2),
            fill="tozeroy",
            fillcolor="rgba(59,130,246,0.1)",
        )
    )
    eq_fig.update_layout(
        yaxis_title="Cumulative P&L ($)",
        **layout,
        height=350,
    )
    st.plotly_chart(eq_fig, use_container_width=True)

# PnL by ticker
with chart_col2:
    st.subheader("📊 P&L by Ticker")
    pnl_by_ticker = df.groupby("ticker")["pnl"].sum().reset_index()
    pnl_by_ticker = pnl_by_ticker.sort_values("pnl", ascending=False)
    bar_colors = ["#10B981" if v >= 0 else "#EF4444" for v in pnl_by_ticker["pnl"]]
    bar_fig = go.Figure(
        go.Bar(
            x=pnl_by_ticker["ticker"],
            y=pnl_by_ticker["pnl"],
            marker_color=bar_colors,
        )
    )
    bar_fig.update_layout(
        yaxis_title="P&L ($)",
        **layout,
        height=350,
    )
    st.plotly_chart(bar_fig, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Win rate by setup type (if journal data available)
# ---------------------------------------------------------------------------
try:
    from src.portfolio.journal import get_journal_entries
    journal = get_journal_entries()

    if journal:
        st.subheader("🎯 Win Rate by Setup Type")
        journal_df = pd.DataFrame(journal)

        if "trade_id" in journal_df.columns and "setup_type" in journal_df.columns:
            merged = df.merge(
                journal_df[["trade_id", "setup_type"]].dropna(),
                left_on="id",
                right_on="trade_id",
                how="left",
            )
            if "setup_type" in merged.columns:
                setup_stats = (
                    merged.groupby("setup_type")["pnl"]
                    .agg(["count", lambda x: (x > 0).mean() * 100])
                    .reset_index()
                )
                setup_stats.columns = ["Setup", "Trades", "Win Rate %"]
                setup_stats = setup_stats.sort_values("Win Rate %", ascending=False)
                st.dataframe(setup_stats, use_container_width=True, hide_index=True)
except Exception:
    pass

# ---------------------------------------------------------------------------
# Trade history table
# ---------------------------------------------------------------------------
st.subheader("📋 Closed Trade History")
display_cols = [c for c in ["ticker", "entry_date", "exit_date", "entry_price", "exit_price", "shares", "pnl", "pnl_pct", "reason"] if c in df.columns]
st.dataframe(
    df[display_cols].rename(columns={
        "ticker": "Ticker",
        "entry_date": "Entry Date",
        "exit_date": "Exit Date",
        "entry_price": "Entry $",
        "exit_price": "Exit $",
        "shares": "Shares",
        "pnl": "P&L $",
        "pnl_pct": "P&L %",
        "reason": "Reason",
    }),
    use_container_width=True,
    hide_index=True,
)
