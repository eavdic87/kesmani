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
from dashboard.components.cards import render_alert_badge, render_action_needed_card, render_explainer_card
from config.settings import ALL_TICKERS, PORTFOLIO_SETTINGS

st.set_page_config(page_title="KešMani | Portfolio", page_icon="💼", layout="wide")

from dashboard.theme import apply_theme
apply_theme()

st.title("💼 Your Portfolio")
st.caption("Track everything you own and know when to act.")
st.markdown("---")

# ---------------------------------------------------------------------------
# Load portfolio
# ---------------------------------------------------------------------------
portfolio = get_portfolio_summary()
positions = portfolio.get("positions", [])
account_size = portfolio.get("net_worth", PORTFOLIO_SETTINGS["starting_capital"])

# ---------------------------------------------------------------------------
# Alert banners — plain English
# ---------------------------------------------------------------------------
alerts = get_all_alerts(positions)
stop_alerts = alerts.get("stop", [])
target_alerts = alerts.get("target", [])

if stop_alerts:
    for a in stop_alerts:
        render_action_needed_card(
            ticker=a["ticker"],
            message=f"**{a['ticker']}** has hit your stop loss price. You set this as your safety net to limit losses.",
            action="👉 Consider selling now to protect your account from further losses.",
            color="#EF4444",
        )

if target_alerts:
    for a in target_alerts:
        render_action_needed_card(
            ticker=a["ticker"],
            message=f"🎉 **{a['ticker']}** has reached your profit target. The trade is working!",
            action="👉 Consider taking some or all of your profits now.",
            color="#10B981",
        )

# ---------------------------------------------------------------------------
# Summary metrics — plain English labels
# ---------------------------------------------------------------------------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(
    "Total Account Value",
    fmt_currency(portfolio.get("net_worth")),
    help="The total value of your account — cash + all open positions combined.",
)
c2.metric(
    "Available Cash",
    fmt_currency(portfolio.get("cash")),
    help="Money that's not currently invested. This is what you have available to buy more stocks.",
)
c3.metric(
    "Currently Invested",
    fmt_currency(portfolio.get("total_invested")),
    help="The total amount you've put into stocks that you currently own.",
)
c4.metric(
    "Profit/Loss on Open Positions",
    fmt_currency(portfolio.get("total_unrealized_pnl")),
    delta=fmt_pct(portfolio.get("total_unrealized_pnl_pct")),
    help="This is what you'd gain or lose if you sold all your open positions right now.",
)
c5.metric(
    "Locked-in Profit/Loss",
    fmt_currency(portfolio.get("total_realized_pnl")),
    help="Gains and losses from trades you've already closed. This money is either in your pocket or already gone.",
)

st.divider()

# ---------------------------------------------------------------------------
# Portfolio allocation pie + sector exposure + heat gauge
# ---------------------------------------------------------------------------
col_pie, col_sector, col_heat = st.columns([2, 2, 1])

with col_pie:
    st.subheader("💰 How Your Money Is Split")
    st.caption("A diversified portfolio should not have more than 25% in any single stock.")
    if positions:
        st.plotly_chart(portfolio_pie(positions), use_container_width=True)
    else:
        render_explainer_card(
            "No positions yet",
            "Once you add stocks to your portfolio, you'll see a pie chart showing how your money is divided across your holdings.",
        )

with col_sector:
    st.subheader("🏢 Which Industries You're Invested In")
    st.caption("Spreading your money across different industries reduces your overall risk.")
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
        render_explainer_card(
            "No positions yet",
            "Your sector exposure chart will appear here once you have open positions.",
        )

with col_heat:
    st.subheader("🌡️ Risk Level")
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
        st.markdown(f"**{ph['ticker']}**: {ph['heat_pct']:.2f}% at risk ({fmt_currency(ph['risk_dollars'])})")

st.divider()

# ---------------------------------------------------------------------------
# Trailing stop controls
# ---------------------------------------------------------------------------
if positions:
    with st.expander("🎯 Trailing Stop Manager"):
        st.markdown(
            """
            <div class="km-beginner-tip">
              💡 A <strong>trailing stop</strong> automatically moves your stop loss up as the stock rises —
              locking in profits while still giving the stock room to grow. It's one of the most powerful
              tools to protect your gains without having to watch the screen all day.
            </div>
            """,
            unsafe_allow_html=True,
        )
        ts_col1, ts_col2, ts_col3 = st.columns(3)
        with ts_col1:
            use_ts = st.toggle(
                "Enable Trailing Stops",
                value=False,
                help="When enabled, your stop losses will automatically move up as stocks rise, locking in more profit.",
            )
        with ts_col2:
            ts_method = st.radio(
                "Method",
                ["Percentage", "ATR-based"],
                horizontal=True,
                help="Percentage = fixed % below the high price. ATR-based = adapts to how volatile the stock is (more advanced).",
            )
        with ts_col3:
            if ts_method == "Percentage":
                trail_pct = st.slider(
                    "Trail %",
                    2.0, 20.0, 8.0, 0.5,
                    help="The stop loss will stay this % below the highest price the stock has reached.",
                ) / 100
                atr_mult = 2.0
            else:
                trail_pct = 0.08
                atr_mult = st.slider(
                    "ATR Multiplier",
                    1.0, 4.0, 2.0, 0.1,
                    help="Multiplier for the Average True Range. Higher = wider stop, more room to breathe.",
                )

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
                st.success(f"Updated trailing stops on {changes} position(s). Your stop losses are now locked in higher.")
                st.rerun()
            else:
                st.info("No stop losses needed updating right now.")

st.divider()

# ---------------------------------------------------------------------------
# Open positions table
# ---------------------------------------------------------------------------
st.subheader("📋 Your Open Positions")
positions_table(positions)

# Close / update position forms
if positions:
    with st.expander("⚙️ Manage a Position"):
        pos_options = {f"{p['ticker']} ({p['id']})": p["id"] for p in positions}
        sel_label = st.selectbox(
            "Select Position to Manage",
            list(pos_options.keys()),
            help="Choose which stock position you want to update or close.",
        )
        sel_id = pos_options[sel_label]

        action = st.radio(
            "What do you want to do?",
            ["Update Stop Loss", "Close Position"],
            horizontal=True,
        )

        if action == "Update Stop Loss":
            new_stop = st.number_input(
                "New Stop Loss Price ($)",
                min_value=0.01,
                step=0.01,
                help="Enter the new price at which you want to sell if the stock falls. Must be below the current price.",
            )
            if st.button("💾 Save New Stop Loss"):
                if update_stop_loss(sel_id, new_stop):
                    st.success("✅ Stop loss updated. Your position is now protected at the new level.")
                    st.rerun()

        else:
            exit_price = st.number_input(
                "Exit Price ($) — What price did you sell at?",
                min_value=0.01,
                step=0.01,
                help="Enter the price you sold your shares at.",
            )
            reason = st.selectbox(
                "Why are you closing this position?",
                ["target", "stop", "manual", "other"],
                format_func=lambda x: {
                    "target": "🎯 Hit my profit target",
                    "stop": "🛑 Hit stop loss",
                    "manual": "✋ Manual decision",
                    "other": "📝 Other reason",
                }[x],
            )
            if st.button("🔒 Close This Position", type="primary"):
                result = remove_position(sel_id, exit_price, reason)
                if result:
                    pnl = result.get("pnl", 0)
                    if pnl > 0:
                        st.success(f"✅ Position closed. You made **{fmt_currency(pnl)}** profit on this trade! 🎉")
                    else:
                        st.info(f"Position closed. Loss on this trade: {fmt_currency(pnl)}.")
                    st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Add new position form
# ---------------------------------------------------------------------------
st.subheader("➕ Record a New Stock Purchase")
st.caption(
    "Use this to record a stock you just bought. "
    "This lets KešMani track your profit/loss and alert you when to act."
)

with st.form("add_position_form"):
    f_col1, f_col2 = st.columns(2)
    with f_col1:
        f_ticker = st.selectbox(
            "Stock Symbol (Ticker)",
            ALL_TICKERS,
            help="The ticker symbol of the stock you bought. Example: AAPL for Apple, MSFT for Microsoft.",
        )
        f_entry = st.number_input(
            "Price You Paid Per Share ($)",
            min_value=0.01,
            step=0.01,
            help="The price you paid when you bought this stock.",
        )
        f_shares = st.number_input(
            "Number of Shares You Bought",
            min_value=0.001,
            step=0.001,
            format="%.3f",
            help="How many shares did you buy? Can be fractional (e.g., 1.5 shares).",
        )
        f_fractional = st.checkbox(
            "I bought fractional shares",
            value=False,
            help="Check this if your broker supports fractional shares (e.g., Robinhood, Fidelity).",
        )
    with f_col2:
        f_stop = st.number_input(
            "Your Stop Loss Price ($)",
            min_value=0.01,
            step=0.01,
            help="The price at which you'll sell to limit your loss. Must be below your entry price.",
        )
        f_target1 = st.number_input(
            "First Profit Target Price ($)",
            min_value=0.01,
            step=0.01,
            help="Where you plan to take your first profits. KešMani will alert you when the stock reaches this price.",
        )
        f_target2 = st.number_input(
            "Second Profit Target ($, optional)",
            min_value=0.0,
            step=0.01,
            help="Optional: your ultimate price target if you want to hold for bigger gains.",
        )
    f_notes = st.text_input(
        "Notes (optional)",
        help="Any notes about why you bought this stock. This is just for your reference.",
    )

    submitted = st.form_submit_button("✅ Add This Position", type="primary")
    if submitted:
        if f_entry > 0 and f_stop > 0 and f_entry > f_stop:
            exceeds = would_exceed_heat_limit(
                [{"ticker": p["ticker"], "shares": p["shares"],
                  "entry_price": p["entry_price"], "stop_loss": p["stop_loss"]} for p in positions],
                account_size, f_entry, f_stop, f_shares
            )
            if exceeds:
                st.warning(
                    "⚠️ Adding this position would push your portfolio heat above the safe limit. "
                    "Consider buying fewer shares to stay within your 2% risk limit."
                )
            add_position(
                f_ticker, f_entry, f_shares, f_stop,
                f_target1 if f_target1 > 0 else None,
                f_target2 if f_target2 > 0 else None,
                f_notes,
                fractional=f_fractional,
            )
            shares_disp = f"{f_shares:.3f}" if f_fractional else f"{int(f_shares)}"
            st.success(f"✅ Added {shares_disp} shares of {f_ticker} at {fmt_currency(f_entry)}. KešMani will now track this position for you.")
            st.rerun()
        else:
            st.error("❌ Please check your prices: your entry price must be higher than your stop loss price.")

st.divider()

# ---------------------------------------------------------------------------
# Position sizing calculator
# ---------------------------------------------------------------------------
st.subheader("🧮 How Many Shares Should I Buy?")
st.caption(
    "Enter your account size, the stock's price, and where you'd put your stop loss. "
    "KešMani will calculate how many shares to buy so you never risk more than 2% of your account on one trade."
)

with st.expander("Open the Calculator"):
    ps_col1, ps_col2 = st.columns(2)
    with ps_col1:
        ps_account = st.number_input(
            "Your Account Size ($)",
            value=float(account_size),
            step=100.0,
            key="ps_account",
            help="The total value of your trading account.",
        )
        ps_entry = st.number_input(
            "Stock Price / Entry Price ($)",
            min_value=0.01,
            step=0.01,
            key="ps_entry",
            help="The current price of the stock (or the price you plan to buy at).",
        )
    with ps_col2:
        ps_stop = st.number_input(
            "Your Stop Loss Price ($)",
            min_value=0.01,
            step=0.01,
            key="ps_stop",
            help="The price at which you'd sell to cut your loss.",
        )
        ps_risk_pct = st.slider(
            "Max % of Account to Risk",
            0.5, 3.0, 2.0, 0.1,
            key="ps_risk",
            help="Most professional traders risk 1–2% per trade. 2% is a good starting point.",
        ) / 100

    if ps_entry > ps_stop > 0:
        try:
            sizing = calculate_position_size(ps_account, ps_entry, ps_stop, ps_risk_pct)
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Shares to Buy", sizing["shares"], help="Buy exactly this many shares.")
            s2.metric("Total Cost", fmt_currency(sizing["position_value"]), help="The total amount you'll spend.")
            s3.metric("Max You Could Lose", fmt_currency(sizing["risk_amount"]), help=f"Your maximum loss = {ps_risk_pct*100:.1f}% of your account.")
            s4.metric("Risk Per Share", fmt_currency(sizing["risk_per_share"]), help="How much you lose per share if the stop loss triggers.")
        except ValueError as e:
            st.error(str(e))

st.divider()

# ---------------------------------------------------------------------------
# Risk-of-ruin calculator
# ---------------------------------------------------------------------------
st.subheader("🛡️ Is My Trading Strategy Safe?")
st.caption(
    "This calculator checks if your trading approach could wipe out your account over time. "
    "You want the Risk of Ruin to be below 1%."
)

with st.expander("Open the Safety Checker"):
    st.markdown(
        """
        <div class="km-beginner-tip">
          💡 <strong>What is Risk of Ruin?</strong> It's the mathematical probability that a series of losing trades
          could wipe out your account entirely. Even good traders have losing streaks — this tool helps you
          make sure your position sizing is safe enough to survive them.
        </div>
        """,
        unsafe_allow_html=True,
    )
    rr_col1, rr_col2 = st.columns(2)
    with rr_col1:
        rr_win_rate = st.slider(
            "Win Rate (%)",
            10, 90, 55, 1,
            key="rr_wr",
            help="What % of your trades are profitable? A 55% win rate is solid for most traders.",
        ) / 100
        rr_avg_win = st.slider(
            "Average Win (% of account)",
            0.5, 10.0, 2.0, 0.1,
            key="rr_aw",
            help="On winning trades, how much do you typically make as a % of your account?",
        ) / 100
    with rr_col2:
        rr_avg_loss = st.slider(
            "Average Loss (% of account)",
            0.5, 10.0, 1.0, 0.1,
            key="rr_al",
            help="On losing trades, how much do you typically lose? Should be less than your average win.",
        ) / 100
        rr_risk_per_trade = st.slider(
            "Risk Per Trade (%)",
            0.5, 5.0, 2.0, 0.1,
            key="rr_rpt",
            help="How much of your account do you risk on each trade? Keep this at 2% or less.",
        ) / 100

    ror = calculate_risk_of_ruin(rr_win_rate, rr_avg_win, rr_avg_loss, rr_risk_per_trade)
    ror_pct = ror * 100
    expectancy = rr_win_rate * rr_avg_win - (1 - rr_win_rate) * rr_avg_loss

    rr_r1, rr_r2, rr_r3 = st.columns(3)
    rr_r1.metric(
        "Risk of Ruin",
        f"{ror_pct:.2f}%",
        help="The probability of losing your entire account. Keep this below 1%.",
    )
    rr_r2.metric(
        "Expected Return Per Trade",
        f"{expectancy*100:.3f}%",
        help="On average, how much do you expect to make per trade? Positive = good.",
    )
    rr_r3.metric(
        "Profit Factor",
        f"{(rr_win_rate*rr_avg_win)/((1-rr_win_rate)*rr_avg_loss):.2f}x" if rr_avg_loss > 0 else "∞",
        help="Total winnings divided by total losses. Above 1.5 is solid. Above 2 is excellent.",
    )

    if ror_pct < 1:
        st.success("✅ Your risk parameters look safe. Risk of ruin is very low. Keep trading with these settings.")
    elif ror_pct < 5:
        st.warning("⚠️ Moderate risk. Consider reducing position size or improving your win rate before trading live.")
    else:
        st.error("🚨 High risk of ruin! Your current parameters could wipe out your account. Reduce position size or risk per trade immediately.")

st.divider()

# ---------------------------------------------------------------------------
# Trade history
# ---------------------------------------------------------------------------
st.subheader("📜 Past Trades")
st.caption("A record of all trades you've closed. Green = profitable, Red = loss.")
st.markdown(
    """
    <div class="km-beginner-tip">
      💡 <em>Profit/Loss (P&amp;L)</em> shows what you actually made or lost when you closed each trade.
      Positive numbers (green) = you made money. Negative numbers (red) = you lost money.
    </div>
    """,
    unsafe_allow_html=True,
)
closed_trades_table(portfolio.get("closed_trades", []))

