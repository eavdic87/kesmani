"""
Page 7: Execution Planner — KešMani Dashboard

Dedicated page for generating and reviewing a complete trade execution
plan for any stock.  Covers order type, limit price, position sizing,
broker click-through instructions, pre-trade checklist, and risk/reward
visual.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from config.settings import ALL_TICKERS, FULL_UNIVERSE, PORTFOLIO_SETTINGS
from src.utils.helpers import fmt_currency, fmt_pct, signal_color, signal_emoji

st.set_page_config(
    page_title="KešMani | Execution Planner",
    page_icon="🎯",
    layout="wide",
)

from dashboard.theme import apply_theme
apply_theme()

# ---------------------------------------------------------------------------
# Sidebar — stock selection & account size
# ---------------------------------------------------------------------------
with st.sidebar:
    st.subheader("🎯 Execution Planner")

    # Allow picking from scanner results or manual entry
    scanner_results = st.session_state.get("scanner_results", [])
    scanner_tickers = [r["ticker"] for r in scanner_results] if scanner_results else []

    input_method = st.radio(
        "Stock Source",
        ["Manual Entry", "From Scanner Results"],
        index=0,
    )

    if input_method == "From Scanner Results" and scanner_tickers:
        ticker = st.selectbox("Select Ticker (from scan)", scanner_tickers)
    else:
        ticker = st.text_input(
            "Ticker Symbol",
            value=st.session_state.get("planner_ticker", "AAPL"),
            max_chars=10,
        ).upper().strip()

    account_size = st.number_input(
        "Account Size ($)",
        min_value=100.0,
        value=float(st.session_state.get("account_size", PORTFOLIO_SETTINGS["starting_capital"])),
        step=100.0,
    )
    st.session_state["account_size"] = account_size

    generate_btn = st.button("🎯 Generate Execution Plan", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------
st.title("🎯 Trade Execution Planner — KešMani")
st.caption(
    "Enter a ticker and account size to receive a complete, VP-level execution guide. "
    "Covers order type, limit price, broker steps, risk management, and warnings."
)

# ---------------------------------------------------------------------------
# Generate plan
# ---------------------------------------------------------------------------
if generate_btn or (ticker and f"plan_{ticker}" not in st.session_state):
    st.session_state["planner_ticker"] = ticker

    with st.spinner(f"Scoring {ticker} and building execution plan…"):
        try:
            from src.analysis.screener import score_ticker
            from src.analysis.signals import generate_signal
            from src.analysis.execution import generate_execution_plan

            # Check if we already have scanner results for this ticker
            existing = None
            for r in st.session_state.get("scanner_results", []):
                if r["ticker"] == ticker:
                    existing = r
                    break

            if existing:
                signal = existing
            else:
                score_result = score_ticker(ticker)
                signal = generate_signal(score_result, account_size)

            plan = generate_execution_plan(signal, account_size)
            st.session_state[f"plan_{ticker}"] = (signal, plan)

        except Exception as exc:
            st.error(f"Failed to generate plan for {ticker}: {exc}")
            st.stop()

plan_data = st.session_state.get(f"plan_{ticker}")
if not plan_data:
    st.info("Enter a ticker and click **Generate Execution Plan** to begin.")
    st.stop()

signal, plan = plan_data
ind = signal.get("indicators", {})

# ---------------------------------------------------------------------------
# Hero card
# ---------------------------------------------------------------------------
sig_val = signal.get("signal", "HOLD")
color = signal_color(sig_val)
entry = signal.get("entry")
stop = signal.get("stop_loss")
t1 = signal.get("target_1")
t2 = signal.get("target_2")
shares = plan.get("position_size_shares", 0)
total_cost = plan.get("position_size_dollars", 0.0)
risk_d = plan.get("total_risk_dollars", 0.0)
rr = signal.get("rr_ratio")

st.markdown(
    f"""
    <div style="background:#161b22;border:2px solid {color};border-radius:12px;
                padding:20px;margin-bottom:20px;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div>
          <span style="font-size:2em;font-weight:bold;">{ticker}</span>
          &nbsp;
          <span style="color:{color};font-size:1.3em;font-weight:bold;">
            {signal_emoji(sig_val)} {sig_val}
          </span>
        </div>
        <div style="text-align:right;color:#8b949e;">
          Score: <b style="color:#c9d1d9;">{signal.get('composite_score', 0):.0f}/100</b>
          &nbsp;|&nbsp; Sector: <b style="color:#c9d1d9;">{signal.get('sector', 'N/A')}</b>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Key metrics grid
# ---------------------------------------------------------------------------
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Order Type", plan.get("order_type", "N/A"))
m2.metric("Limit Price", fmt_currency(plan.get("limit_price")))
m3.metric("Shares", shares)
m4.metric("Total Cost", fmt_currency(total_cost))
m5.metric("Max Risk $", fmt_currency(risk_d))
m6.metric("R:R Ratio", f"{rr:.1f}:1" if rr else "N/A")

st.divider()

# ---------------------------------------------------------------------------
# Risk / Reward visual bar
# ---------------------------------------------------------------------------
st.subheader("📊 Risk / Reward Visualizer")

if entry and stop and t1:
    import plotly.graph_objects as go

    risk_pts = entry - stop
    reward_1 = t1 - entry
    reward_2 = (t2 - entry) if t2 else reward_1 * 1.5

    bar_labels = ["Stop Loss", "Entry", "Target 1", "Target 2"]
    bar_prices = [stop, entry, t1, t2 if t2 else t1 + reward_2]
    bar_colors = ["#cc0000", "#ffcc00", "#66cc00", "#00cc44"]

    fig = go.Figure()
    for i, (lbl, price, clr) in enumerate(zip(bar_labels, bar_prices, bar_colors)):
        fig.add_trace(
            go.Scatter(
                x=[price, price],
                y=[0, 1],
                mode="lines+text",
                name=lbl,
                line=dict(color=clr, width=3, dash="dash" if lbl == "Entry" else "solid"),
                text=["", f"{lbl}<br>{fmt_currency(price)}"],
                textposition="top center",
                textfont=dict(color=clr, size=12),
            )
        )

    # Shaded risk zone
    fig.add_vrect(x0=stop, x1=entry, fillcolor="#cc0000", opacity=0.15,
                  annotation_text="RISK", annotation_position="top left")
    # Shaded reward zone
    fig.add_vrect(x0=entry, x1=t1, fillcolor="#66cc00", opacity=0.15,
                  annotation_text="TARGET 1", annotation_position="top right")

    fig.update_layout(
        height=180,
        showlegend=False,
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font=dict(color="#c9d1d9"),
        xaxis=dict(showgrid=False, title="Price ($)"),
        yaxis=dict(visible=False),
        margin=dict(l=10, r=10, t=30, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Risk/reward chart not available — price levels missing.")

st.divider()

# ---------------------------------------------------------------------------
# Order reasoning & timing
# ---------------------------------------------------------------------------
st.subheader("📋 Execution Details")

d1, d2 = st.columns(2)
with d1:
    st.markdown("**Order Reasoning**")
    st.info(plan.get("order_reasoning", "N/A"))
    st.markdown("**Stop-Loss Type**")
    st.markdown(f"`{plan.get('stop_loss_type', 'N/A').replace('_', ' ').upper()}` at {fmt_currency(plan.get('stop_loss_price'))}")

with d2:
    st.markdown("**Entry Timing**")
    st.info(plan.get("timing", "N/A"))
    st.markdown("**Partial Profit Plan**")
    st.success(plan.get("partial_profit_plan", "N/A"))

# Scale-in plan
if plan.get("scale_in_plan"):
    st.markdown("**Scale-In Plan** (large position — split into tranches)")
    for t in plan["scale_in_plan"]:
        st.markdown(
            f"- **Tranche {t['tranche']}** ({t['pct']}): {t['shares']} shares "
            f"@ ~${t['price']:,.2f} — *{t['trigger']}*"
        )

st.divider()

# ---------------------------------------------------------------------------
# Broker steps
# ---------------------------------------------------------------------------
st.subheader("🖥️ Step-by-Step Broker Instructions")
st.caption("Follow these steps exactly in your brokerage app (Fidelity, Schwab, TD Ameritrade, IBKR, Robinhood, etc.)")

for i, step in enumerate(plan.get("broker_steps", []), 1):
    st.markdown(f"**{i}.** {step}")

st.divider()

# ---------------------------------------------------------------------------
# Pre-trade checklist (interactive checkboxes)
# ---------------------------------------------------------------------------
st.subheader("✅ Pre-Trade Checklist")
st.caption("Work through every item before placing the order.")

checklist_items = plan.get("checklist", [])
all_checked = True
for item in checklist_items:
    checked = st.checkbox(item, key=f"chk_{ticker}_{item[:30]}")
    if not checked:
        all_checked = False

if checklist_items:
    if all_checked:
        st.success("✅ All checklist items confirmed. You're cleared to trade!")
    else:
        st.warning("⚠️ Complete all checklist items before entering the trade.")

st.divider()

# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------
warnings = plan.get("warnings", [])
if warnings:
    st.subheader("⚠️ Warnings")
    for w in warnings:
        if "No major warnings" in w:
            st.success(w)
        else:
            st.warning(w)

st.divider()

# ---------------------------------------------------------------------------
# Copy trade plan
# ---------------------------------------------------------------------------
st.subheader("📋 Copy Trade Plan")

plan_text = f"""
KESMANI TRADE EXECUTION PLAN
=============================
Ticker:       {ticker}
Signal:       {sig_val}
Score:        {signal.get('composite_score', 0):.0f}/100
Sector:       {signal.get('sector', 'N/A')}
Generated:    {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M ET')}

ORDER
-----
Order Type:   {plan.get('order_type')}
Limit Price:  {fmt_currency(plan.get('limit_price'))}
Shares:       {shares}
Total Cost:   {fmt_currency(total_cost)}

LEVELS
------
Entry:        {fmt_currency(entry)}
Stop Loss:    {fmt_currency(plan.get('stop_loss_price'))} ({plan.get('stop_loss_type', '').replace('_', ' ')})
Target 1:     {fmt_currency(t1)}
Target 2:     {fmt_currency(t2)}
Max Risk $:   {fmt_currency(risk_d)}
R:R Ratio:    {f"{rr:.1f}:1" if rr else "N/A"}

TIMING
------
{plan.get('timing', 'N/A')}

PARTIAL PROFIT PLAN
-------------------
{plan.get('partial_profit_plan', 'N/A')}

BROKER STEPS
------------
""".strip()

for i, step in enumerate(plan.get("broker_steps", []), 1):
    plan_text += f"\n{i}. {step}"

plan_text += "\n\nCHECKLIST\n---------"
for item in checklist_items:
    plan_text += f"\n{item}"

plan_text += "\n\nWARNINGS\n--------"
for w in warnings:
    plan_text += f"\n{w}"

plan_text += "\n\n⚠️  This is not financial advice. All trading carries risk."

st.text_area("Trade Plan (copy & paste)", plan_text, height=300)
