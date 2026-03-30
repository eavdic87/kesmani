"""
Page 4: Portfolio — KešMani Dashboard

Position management, live P&L, risk heat gauge, position sizing calculator,
stop/target alert banners, trailing stop controls, sector exposure chart,
risk-of-ruin calculator, and trade history.
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
from src.portfolio.alerts import get_all_alerts
from src.portfolio.trailing_stop import update_trailing_stops
from src.analysis.risk_manager import (
    calculate_position_size,
    calculate_portfolio_heat,
    would_exceed_heat_limit,
    calculate_risk_of_ruin,
)
from src.utils.helpers import fmt_currency, fmt_pct
from dashboard.components.charts import portfolio_pie, sector_bar_chart
from dashboard.components.tables import positions_table, closed_trades_table
from dashboard.components.metrics import heat_gauge
from dashboard.components.cards import render_alert_badge
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
# Alert banners
# ---------------------------------------------------------------------------
alerts = get_all_alerts(positions)
stop_alerts = alerts.get("stop", [])
target_alerts = alerts.get("target", [])

if stop_alerts:
    stop_tickers = " ".join(render_alert_badge("STOP", a["ticker"]) for a in stop_alerts)
    st.markdown(
        f'<div style="background:#7F1D1D;border:1px solid #EF4444;border-radius:10px;'
        f'padding:12px 16px;margin-bottom:12px;">'
        f'<b style="color:#FCA5A5;">🚨 STOP LOSS ALERT</b>&nbsp;&nbsp;{stop_tickers}'
        f'</div>',
        unsafe_allow_html=True,
    )

if target_alerts:
    target_badges = " ".join(
        render_alert_badge(a.get("alert_type", "TARGET_1"), a["ticker"]) for a in target_alerts
    )
    st.markdown(
        f'<div style="background:#064E3B;border:1px solid #10B981;border-radius:10px;'
        f'padding:12px 16px;margin-bottom:12px;">'
        f'<b style="color:#6EE7B7;">🎯 TARGET HIT</b>&nbsp;&nbsp;{target_badges}'
        f'</div>',
        unsafe_allow_html=True,
    )

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
# Portfolio allocation pie + sector exposure + heat gauge
# ---------------------------------------------------------------------------
col_pie, col_sector, col_heat = st.columns([2, 2, 1])

with col_pie:
    st.subheader("📊 Allocation")
    if positions:
        st.plotly_chart(portfolio_pie(positions), use_container_width=True)
    else:
        st.info("No open positions to display.")

with col_sector:
    st.subheader("🏢 Sector Exposure")
    if positions:
        from config.settings import TICKER_SECTORS
        total_val = sum(p.get("market_value", 0) for p in positions) or 1
        sector_map: dict[str, float] = {}
        for p in positions:
            sector = TICKER_SECTORS.get(p["ticker"], "Other")
            sector_map[sector] = sector_map.get(sector, 0) + p.get("market_value", 0)
        sector_data = [
            {"sector": s, "pct": round(v / total_val * 100, 1)}
            for s, v in sorted(sector_map.items(), key=lambda x: -x[1])
        ]
        st.plotly_chart(sector_bar_chart(sector_data), use_container_width=True)
    else:
        st.info("No positions to show sector data.")

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

    for ph in heat_data.get("position_heats", []):
        st.markdown(f"**{ph['ticker']}**: {ph['heat_pct']:.2f}% heat ({fmt_currency(ph['risk_dollars'])} at risk)")

st.divider()

# ---------------------------------------------------------------------------
# Trailing stop controls
# ---------------------------------------------------------------------------
if positions:
    with st.expander("🎯 Trailing Stop Manager"):
        ts_col1, ts_col2, ts_col3 = st.columns(3)
        with ts_col1:
            use_ts = st.toggle("Enable Trailing Stops", value=False)
        with ts_col2:
            ts_method = st.radio("Method", ["Percentage", "ATR-based"], horizontal=True)
        with ts_col3:
            if ts_method == "Percentage":
                trail_pct = st.slider("Trail %", 2.0, 20.0, 8.0, 0.5) / 100
                atr_mult = 2.0
            else:
                trail_pct = 0.08
                atr_mult = st.slider("ATR Multiplier", 1.0, 4.0, 2.0, 0.1)

        if use_ts and st.button("🔄 Update All Trailing Stops"):
            updated = update_trailing_stops(
                positions,
                trail_pct=trail_pct,
                use_atr=(ts_method == "ATR-based"),
                atr_multiplier=atr_mult,
            )
            changes = 0
            for orig, upd in zip(positions, updated):
                if upd["stop_loss"] != orig["stop_loss"]:
                    update_stop_loss(orig["id"], upd["stop_loss"])
                    changes += 1
            if changes:
                st.success(f"Updated trailing stops on {changes} position(s).")
                st.rerun()
            else:
                st.info("No stops needed updating.")

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
        f_shares = st.number_input("Shares", min_value=0.001, step=0.001, format="%.3f")
        f_fractional = st.checkbox("Fractional shares", value=False, help="Enable for brokers supporting fractional shares")
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
                f_ticker, f_entry, f_shares, f_stop,
                f_target1 if f_target1 > 0 else None,
                f_target2 if f_target2 > 0 else None,
                f_notes,
                fractional=f_fractional,
            )
            shares_disp = f"{f_shares:.3f}" if f_fractional else f"{int(f_shares)}"
            st.success(f"Added {shares_disp} shares of {f_ticker} @ {fmt_currency(f_entry)}")
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
# Risk-of-ruin calculator
# ---------------------------------------------------------------------------
st.subheader("☠️ Risk-of-Ruin Calculator")

with st.expander("Sanity-check your system parameters"):
    rr_col1, rr_col2 = st.columns(2)
    with rr_col1:
        rr_win_rate = st.slider("Win Rate (%)", 10, 90, 55, 1, key="rr_wr") / 100
        rr_avg_win = st.slider("Avg Win (% of account)", 0.5, 10.0, 2.0, 0.1, key="rr_aw") / 100
    with rr_col2:
        rr_avg_loss = st.slider("Avg Loss (% of account)", 0.5, 10.0, 1.0, 0.1, key="rr_al") / 100
        rr_risk_per_trade = st.slider("Risk per Trade (%)", 0.5, 5.0, 2.0, 0.1, key="rr_rpt") / 100

    ror = calculate_risk_of_ruin(rr_win_rate, rr_avg_win, rr_avg_loss, rr_risk_per_trade)
    ror_pct = ror * 100
    expectancy = rr_win_rate * rr_avg_win - (1 - rr_win_rate) * rr_avg_loss

    rr_r1, rr_r2, rr_r3 = st.columns(3)
    rr_r1.metric("Risk of Ruin", f"{ror_pct:.2f}%", delta=None)
    rr_r2.metric("Expectancy (per trade)", f"{expectancy*100:.3f}%")
    rr_r3.metric("Profit Factor", f"{(rr_win_rate*rr_avg_win)/((1-rr_win_rate)*rr_avg_loss):.2f}x" if rr_avg_loss > 0 else "∞")

    if ror_pct < 1:
        st.success("✅ Risk of ruin is very low. Your system looks well-calibrated.")
    elif ror_pct < 5:
        st.warning("⚠️ Moderate risk of ruin. Consider tightening your risk parameters.")
    else:
        st.error("🚨 High risk of ruin! Reduce position size or improve win rate before trading live.")

st.divider()

# ---------------------------------------------------------------------------
# Trade history
# ---------------------------------------------------------------------------
st.subheader("📜 Closed Trade History")
closed_trades_table(portfolio.get("closed_trades", []))
