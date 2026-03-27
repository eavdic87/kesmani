"""
Page 4: Portfolio — KešMani Dashboard

Position management, live P&L, risk heat gauge, position sizing calculator,
and trade history.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from src.portfolio.tracker import (
    add_position,
    remove_position,
    update_stop_loss,
    get_portfolio_summary,
)
from src.analysis.risk_manager import (
    calculate_position_size,
    calculate_portfolio_heat,
    would_exceed_heat_limit,
)
from src.utils.helpers import fmt_currency, fmt_pct
from dashboard.components.charts import portfolio_pie
from dashboard.components.tables import positions_table, closed_trades_table
from dashboard.components.metrics import heat_gauge
from config.settings import ALL_TICKERS, PORTFOLIO_SETTINGS

st.set_page_config(page_title="KešMani | Portfolio", page_icon="💼", layout="wide")

from dashboard.theme import apply_theme
apply_theme()

st.title("💼 Portfolio Tracker — KešMani")

# ---------------------------------------------------------------------------
# Load portfolio
# ---------------------------------------------------------------------------
portfolio = get_portfolio_summary()
positions = portfolio.get("positions", [])
account_size = portfolio.get("net_worth", PORTFOLIO_SETTINGS["starting_capital"])

# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Net Worth", fmt_currency(portfolio.get("net_worth")))
c2.metric("Cash", fmt_currency(portfolio.get("cash")))
c3.metric("Invested", fmt_currency(portfolio.get("total_invested")))
c4.metric(
    "Unrealized P&L",
    fmt_currency(portfolio.get("total_unrealized_pnl")),
    delta=fmt_pct(portfolio.get("total_unrealized_pnl_pct")),
)
c5.metric("Realized P&L", fmt_currency(portfolio.get("total_realized_pnl")))

st.divider()

# ---------------------------------------------------------------------------
# Portfolio allocation pie + heat gauge
# ---------------------------------------------------------------------------
col_pie, col_heat = st.columns([2, 1])

with col_pie:
    st.subheader("📊 Allocation")
    if positions:
        st.plotly_chart(portfolio_pie(positions), use_container_width=True)
    else:
        st.info("No open positions to display.")

with col_heat:
    st.subheader("🌡️ Risk Heat")
    heat_data = calculate_portfolio_heat(
        [
            {"ticker": p["ticker"], "shares": p["shares"],
             "entry_price": p["entry_price"], "stop_loss": p["stop_loss"]}
            for p in positions
        ],
        account_size,
    )
    heat_gauge(heat_data.get("total_heat_pct", 0), heat_data.get("max_heat_pct", 8))

    # Per-position heat
    for ph in heat_data.get("position_heats", []):
        st.markdown(f"**{ph['ticker']}**: {ph['heat_pct']:.2f}% heat ({fmt_currency(ph['risk_dollars'])} at risk)")

st.divider()

# ---------------------------------------------------------------------------
# Open positions table
# ---------------------------------------------------------------------------
st.subheader("📋 Open Positions")
positions_table(positions)

# Close / update position forms
if positions:
    with st.expander("⚙️ Manage Position"):
        pos_options = {f"{p['ticker']} ({p['id']})": p["id"] for p in positions}
        sel_label = st.selectbox("Select Position", list(pos_options.keys()))
        sel_id = pos_options[sel_label]

        action = st.radio("Action", ["Update Stop Loss", "Close Position"], horizontal=True)

        if action == "Update Stop Loss":
            new_stop = st.number_input("New Stop Loss ($)", min_value=0.01, step=0.01)
            if st.button("Update Stop"):
                if update_stop_loss(sel_id, new_stop):
                    st.success("Stop loss updated.")
                    st.rerun()

        else:
            exit_price = st.number_input("Exit Price ($)", min_value=0.01, step=0.01)
            reason = st.selectbox("Reason", ["target", "stop", "manual", "other"])
            if st.button("Close Position", type="primary"):
                result = remove_position(sel_id, exit_price, reason)
                if result:
                    pnl = result.get("pnl", 0)
                    st.success(f"Position closed. P&L: {fmt_currency(pnl)}")
                    st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Add new position form
# ---------------------------------------------------------------------------
st.subheader("➕ Add New Position")

with st.form("add_position_form"):
    f_col1, f_col2 = st.columns(2)
    with f_col1:
        f_ticker = st.selectbox("Ticker", ALL_TICKERS)
        f_entry = st.number_input("Entry Price ($)", min_value=0.01, step=0.01)
        f_shares = st.number_input("Shares", min_value=1, step=1)
    with f_col2:
        f_stop = st.number_input("Stop Loss ($)", min_value=0.01, step=0.01)
        f_target1 = st.number_input("Target 1 ($)", min_value=0.01, step=0.01)
        f_target2 = st.number_input("Target 2 ($, optional)", min_value=0.0, step=0.01)
    f_notes = st.text_input("Notes (optional)")

    submitted = st.form_submit_button("Add Position", type="primary")
    if submitted:
        if f_entry > 0 and f_stop > 0 and f_entry > f_stop:
            exceeds = would_exceed_heat_limit(
                [{"ticker": p["ticker"], "shares": p["shares"],
                  "entry_price": p["entry_price"], "stop_loss": p["stop_loss"]} for p in positions],
                account_size, f_entry, f_stop, f_shares
            )
            if exceeds:
                st.warning("⚠️ This position would exceed your max portfolio heat limit. Consider reducing size.")
            add_position(
                f_ticker, f_entry, int(f_shares), f_stop,
                f_target1 if f_target1 > 0 else None,
                f_target2 if f_target2 > 0 else None,
                f_notes,
            )
            st.success(f"Added {int(f_shares)} shares of {f_ticker} @ {fmt_currency(f_entry)}")
            st.rerun()
        else:
            st.error("Invalid inputs: entry price must be greater than stop loss.")

st.divider()

# ---------------------------------------------------------------------------
# Position sizing calculator
# ---------------------------------------------------------------------------
st.subheader("🧮 Position Sizing Calculator")

with st.expander("Calculate position size"):
    ps_col1, ps_col2 = st.columns(2)
    with ps_col1:
        ps_account = st.number_input("Account Size ($)", value=float(account_size), step=100.0, key="ps_account")
        ps_entry = st.number_input("Entry Price ($)", min_value=0.01, step=0.01, key="ps_entry")
    with ps_col2:
        ps_stop = st.number_input("Stop Loss ($)", min_value=0.01, step=0.01, key="ps_stop")
        ps_risk_pct = st.slider("Risk % of Account", 0.5, 3.0, 2.0, 0.1, key="ps_risk") / 100

    if ps_entry > ps_stop > 0:
        try:
            sizing = calculate_position_size(ps_account, ps_entry, ps_stop, ps_risk_pct)
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Shares", sizing["shares"])
            s2.metric("Position Value", fmt_currency(sizing["position_value"]))
            s3.metric("Risk Amount", fmt_currency(sizing["risk_amount"]))
            s4.metric("Risk per Share", fmt_currency(sizing["risk_per_share"]))
        except ValueError as e:
            st.error(str(e))

st.divider()

# ---------------------------------------------------------------------------
# Trade history
# ---------------------------------------------------------------------------
st.subheader("📜 Closed Trade History")
closed_trades_table(portfolio.get("closed_trades", []))
