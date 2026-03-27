"""
Page 5: Daily Brief — KešMani Dashboard

Renders the full daily morning briefing and provides a one-click
email send button.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from src.reports.daily_report import build_daily_report, format_text_report, format_html_report
from src.reports.email_sender import send_report_email
from config.settings import PORTFOLIO_SETTINGS
from src.utils.helpers import fmt_currency, fmt_pct, signal_emoji

st.set_page_config(page_title="KešMani | Daily Brief", page_icon="📋", layout="wide")

from dashboard.theme import apply_theme
apply_theme()

st.title("📋 Daily Trading Brief — KešMani")
st.caption("Your personalised morning briefing with entry/stop/target recommendations")

# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------
col_a, col_b = st.columns([3, 1])
with col_a:
    account_size = st.number_input(
        "Account Size ($)",
        min_value=100.0,
        value=float(PORTFOLIO_SETTINGS["starting_capital"]),
        step=100.0,
    )
with col_b:
    generate_btn = st.button("🔄 Generate Report", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Build report
# ---------------------------------------------------------------------------
if generate_btn or "daily_report" not in st.session_state:
    with st.spinner("Building your daily briefing…"):
        report = build_daily_report(account_size=account_size)
        st.session_state["daily_report"] = report

report = st.session_state.get("daily_report")
if not report:
    st.stop()

# ---------------------------------------------------------------------------
# Market overview section
# ---------------------------------------------------------------------------
st.subheader(f"📅 {report['date']}")

regime = report.get("regime", "NEUTRAL")
regime_color = {"BULLISH": "#00cc44", "BEARISH": "#cc0000", "NEUTRAL": "#ffcc00"}.get(regime, "#888")
st.markdown(
    f'<div style="display:inline-block;background:{regime_color}22;border:1px solid {regime_color};'
    f'border-radius:6px;padding:6px 16px;color:{regime_color};font-weight:bold;font-size:1.1em;">'
    f'Market Regime: {regime}</div>',
    unsafe_allow_html=True,
)

bench_cols = st.columns(len(report.get("benchmarks", [])) or 1)
for col, b in zip(bench_cols, report.get("benchmarks", [])):
    chg = b.get("day_change_pct", 0)
    col.metric(b.get("ticker", ""), fmt_currency(b.get("current_price")), fmt_pct(chg))

st.divider()

# ---------------------------------------------------------------------------
# Top setups
# ---------------------------------------------------------------------------
st.subheader("🎯 Top Watchlist Setups")
setups = report.get("top_setups", [])
if setups:
    for i, s in enumerate(setups, 1):
        with st.container():
            c1, c2, c3, c4, c5, c6 = st.columns([1, 2, 2, 2, 2, 3])
            c1.markdown(f"**#{i}**")
            c2.markdown(f"**{s['ticker']}**  \n{signal_emoji(s['signal'])} {s['signal']}")
            c3.metric("Entry", fmt_currency(s.get("entry")))
            c4.metric("Stop", fmt_currency(s.get("stop_loss")))
            c5.metric("Target 1", fmt_currency(s.get("target_1")))
            c6.markdown(f"*{s.get('reasoning', '')}*")
            st.divider()
else:
    st.info("No strong setups today. Market conditions may not be favourable.")

# ---------------------------------------------------------------------------
# Open positions
# ---------------------------------------------------------------------------
st.subheader("💼 Open Position Updates")
positions = report.get("portfolio", {}).get("positions", [])
if positions:
    for p in positions:
        pnl_pct = p.get("unrealized_pnl_pct", 0)
        action = "⚠️ AT STOP — Review exit" if p.get("at_stop") else (
            "💰 TARGET HIT — Take partial profits" if p.get("at_target_1") else "✅ HOLD"
        )
        st.markdown(
            f"**{p['ticker']}** — {fmt_pct(pnl_pct)} unrealized P&L | {action}"
        )
else:
    st.info("No open positions.")

st.divider()

# ---------------------------------------------------------------------------
# Risk dashboard
# ---------------------------------------------------------------------------
st.subheader("🌡️ Risk Dashboard")
heat = report.get("heat", {})
heat_pct = heat.get("total_heat_pct", 0)
max_heat = heat.get("max_heat_pct", 8)
within = heat.get("within_limit", True)
col_h1, col_h2 = st.columns(2)
col_h1.metric("Portfolio Heat", f"{heat_pct:.1f}%", f"Max: {max_heat:.0f}%")
col_h2.markdown(f"Status: {'✅ Within limit' if within else '🚨 OVER LIMIT'}")

st.divider()

# ---------------------------------------------------------------------------
# Catalysts
# ---------------------------------------------------------------------------
st.subheader("📅 Upcoming Catalysts")
earnings = report.get("catalysts", {}).get("earnings", [])
for e in earnings[:8]:
    icon = "⚠️" if e.get("warning") else "📅"
    date_str = (
        e["earnings_date"].strftime("%b %d")
        if hasattr(e["earnings_date"], "strftime")
        else str(e["earnings_date"])
    )
    st.markdown(f"{icon} **{e['ticker']}** — Earnings in {e['days_until']} days ({date_str})")

if not earnings:
    st.info("No earnings in the next 14 days.")

st.divider()

# ---------------------------------------------------------------------------
# Recommended next steps
# ---------------------------------------------------------------------------
st.subheader("✅ Recommended Next Steps")
for step in report.get("next_steps", []):
    st.markdown(f"- {step}")

st.divider()

# ---------------------------------------------------------------------------
# Email send
# ---------------------------------------------------------------------------
st.subheader("📧 Send Report via Email")
col_email, col_status = st.columns([2, 3])
with col_email:
    recipient_override = st.text_input("Recipient Email (leave blank for default)", value="")
    send_btn = st.button("📧 Send Daily Report", type="primary")

if send_btn:
    html = format_html_report(report)
    recipient = recipient_override if recipient_override else None
    with st.spinner("Sending email…"):
        success = send_report_email(html, recipient=recipient)
    if success:
        col_status.success("✅ Report sent successfully!")
    else:
        col_status.error(
            "❌ Email failed. Check SMTP credentials in .env file. "
            "See the README for Gmail App Password setup instructions."
        )

st.divider()

# ---------------------------------------------------------------------------
# Raw text report (expandable)
# ---------------------------------------------------------------------------
with st.expander("📄 View Plain Text Report"):
    text_report = format_text_report(report)
    st.code(text_report, language=None)
