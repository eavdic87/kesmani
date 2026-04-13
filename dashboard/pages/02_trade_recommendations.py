"""
KešMani — Trade Recommendations Page.

The crown jewel of KešMani — VP-level trade recommendations with
complete execution plans, entry/stop/target levels, and broker steps.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from dashboard.theme import (
    apply_theme, signal_badge_html, urgency_badge_html,
    render_confidence_bar, render_score_bar, score_color, confidence_color,
    plain_english_signal, jargon_tooltip,
)

st.set_page_config(
    page_title="KešMani | Trade Recommendations",
    page_icon="🎯",
    layout="wide",
)

apply_theme()

st.title("🎯 Trade Recommendations")
st.caption(
    "These are the best stock opportunities the system found right now. "
    "Each card tells you exactly what to buy, how many shares, and where to set your safety net."
)
st.markdown("---")

# Collapsible "How to read a trade card" explainer
with st.expander("📖 How to read a trade card — click here if you're new", expanded=False):
    st.markdown(
        """
        <div class="km-explainer">
          <strong>📖 What each number means</strong>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px;">
            <div>
              <p><strong>📥 Buy at (Entry Price)</strong><br>The price you aim to buy at. Place a limit order at this price.</p>
              <p><strong>🛑 Sell if it drops to (Stop Loss)</strong><br>Your safety net. If the stock falls to this price, sell immediately to limit your loss.</p>
              <p><strong>🎯 First profit target</strong><br>Where to take your first batch of profits. Many traders sell half their position here.</p>
              <p><strong>🏆 Full target</strong><br>The ultimate price target where you'd sell the rest of your position.</p>
            </div>
            <div>
              <p><strong>📊 Reward vs. Risk (R:R)</strong><br>How much you could earn vs. how much you could lose. 2:1 means for every $1 at risk, you could make $2. Always aim for 2:1 or better.</p>
              <p><strong>🎯 System Confidence</strong><br>How sure the system is about this trade. 85%+ is high confidence. We recommend only taking trades above 75%.</p>
              <p><strong>📦 Shares to buy</strong><br>How many shares to buy based on your account size, risking no more than 2% of your account.</p>
              <p><strong>⚡ Max you could lose</strong><br>Your maximum dollar loss if the stop loss triggers. This is your worst case.</p>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

account_size = st.session_state.get("account_size", 5000.0)

try:
    from src.data.market_scanner import scan_market
    from src.analysis.trade_advisor import generate_trade_recommendations, analyze_market
    from config.settings import SCAN_UNIVERSE, FULL_UNIVERSE
except ImportError as e:
    st.error(f"Import error: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------
with st.expander("⚙️ Scan Settings", expanded=False):
    col1, col2, col3 = st.columns(3)
    with col1:
        timeframe = st.selectbox(
            "Trading Style",
            options=["swing", "day", "position"],
            index=0,
            format_func=lambda x: {
                "swing": "🔵 Swing Trade (hold 2–14 days)",
                "day": "⚡ Day Trade (buy and sell same day)",
                "position": "📅 Position Trade (hold weeks to months)",
            }[x],
            help="Swing trading is the most beginner-friendly. Day trading requires you to monitor your screen all day.",
        )
    with col2:
        sector_options = ["All Sectors"] + sorted(SCAN_UNIVERSE.keys())
        sector_filter = st.selectbox(
            "Industry Filter",
            sector_options,
            help="Leave on 'All Sectors' to scan everything, or pick an industry you're interested in.",
        )
    with col3:
        min_conf = st.slider(
            "Minimum Confidence %",
            min_value=75,
            max_value=95,
            value=75,
            step=5,
            help="We recommend keeping this at 75% or higher for safety. Higher = fewer but better trades.",
        )

run_scan = st.button("🔍 Find Me Good Stocks to Buy", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Scan & generate recommendations
# ---------------------------------------------------------------------------
cache_key = f"trade_recs_{timeframe}_{sector_filter}"
if run_scan or cache_key not in st.session_state:
    with st.spinner("🔍 Scanning the market for the best opportunities right now..."):
        try:
            # Determine tickers
            if sector_filter != "All Sectors":
                tickers = SCAN_UNIVERSE.get(sector_filter, FULL_UNIVERSE[:50])
            else:
                tickers = FULL_UNIVERSE[:80]  # Top 80 for speed

            scan_results = scan_market(
                tickers=tickers,
                account_size=account_size,
                signal_filter=["STRONG BUY", "BUY"],
            )
            recommendations = generate_trade_recommendations(
                scan_results,
                account_size=account_size,
                timeframe=timeframe,
            )
            analysis = analyze_market(scan_results, account_size=account_size)
            st.session_state[cache_key] = {
                "recommendations": recommendations,
                "analysis": analysis,
            }
        except Exception as exc:
            st.error(f"Scan failed: {exc}")
            st.stop()
else:
    cached = st.session_state.get(cache_key, {})
    recommendations = cached.get("recommendations", [])
    analysis = cached.get("analysis", {})

# Filter by min confidence
recommendations = [r for r in recommendations if r.get("confidence", 0) >= min_conf]

if not recommendations:
    st.markdown(
        """
        <div class="km-explainer">
          <strong>🔍 No recommendations found with your current settings</strong><br><br>
          This usually means the market doesn't have enough high-quality setups right now. A few things to try:
          <ul style="margin-top:8px;">
            <li>Lower the <strong>Minimum Confidence %</strong> from 80% to 75%</li>
            <li>Change the <strong>Industry Filter</strong> to "All Sectors"</li>
            <li>Switch to a different <strong>Trading Style</strong></li>
            <li>Wait for better market conditions (check Market Overview first)</li>
          </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# ---------------------------------------------------------------------------
# Market regime banner
# ---------------------------------------------------------------------------
regime = analysis.get("market_regime", "NEUTRAL")
summary = analysis.get("market_summary", "")
regime_color_map = {"BULLISH": "#10B981", "BEARISH": "#EF4444", "VOLATILE": "#F59E0B", "NEUTRAL": "#6B7280"}
rc = regime_color_map.get(regime, "#6B7280")
st.markdown(
    f'<div style="background:{rc}15;border-left:4px solid {rc};border-radius:8px;padding:12px 16px;margin-bottom:16px;">'
    f'<b style="color:{rc};">Market today: {regime}</b> — {summary}</div>',
    unsafe_allow_html=True,
)

# Risk warnings
warnings = analysis.get("risk_warnings", [])
for w in warnings:
    st.warning(w)

st.markdown(f"**🎯 {len(recommendations)} high-confidence setup{'s' if len(recommendations) != 1 else ''} found**")
st.caption(f"Based on your account size of ${account_size:,.0f}. All share counts are pre-calculated for you.")
st.markdown("---")

# ---------------------------------------------------------------------------
# Tabs by timeframe
# ---------------------------------------------------------------------------
day_recs = [r for r in recommendations if r["timeframe"] == "day_trade"]
swing_recs = [r for r in recommendations if r["timeframe"] == "swing_trade"]
all_recs = recommendations

tab_day, tab_swing, tab_all = st.tabs([
    f"⚡ Day Trades ({len(day_recs)})",
    f"🔵 Swing Trades ({len(swing_recs)})",
    f"📋 All ({len(all_recs)})",
])

def _render_recommendation(rec: dict) -> None:
    """Render a single trade recommendation card."""
    ticker = rec["ticker"]
    signal = rec["signal"]
    confidence = rec["confidence"]
    urgency = rec["urgency"]
    sector = rec.get("sector", "")
    entry = rec.get("entry_price", 0)
    stop = rec.get("stop_loss", 0)
    t1 = rec.get("target_1", 0)
    t2 = rec.get("target_2", 0)
    shares = rec.get("shares", 0)
    total_cost = rec.get("total_cost", 0)
    risk_d = rec.get("risk_dollars", 0)
    reward_d = rec.get("reward_dollars", 0)
    rr = rec.get("risk_reward_ratio", 0)
    plain_sig = plain_english_signal(signal)

    color = confidence_color(confidence)

    # Card header — Trade at a Glance
    st.markdown(
        f"""
        <div class="km-card" style="border-top:4px solid {color};">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;">
          <div>
            <span style="font-size:1.8rem;font-weight:800;">{ticker}</span>
            <span style="margin-left:10px;font-size:0.85rem;opacity:0.6;">{sector}</span>
            <div style="margin-top:8px;">
              {signal_badge_html(signal)}
              &nbsp;&nbsp;
              {urgency_badge_html(urgency)}
            </div>
          </div>
          <div style="text-align:center;">
            <div style="font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;opacity:0.6;margin-bottom:4px;">System Confidence</div>
            <div style="font-size:2.2rem;font-weight:800;color:{color};">{confidence:.0f}%</div>
            <div style="font-size:0.75rem;opacity:0.7;">out of 100%</div>
          </div>
        </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Key levels — plain English labels
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "📥 Buy at",
            f"${entry:,.2f}",
            help="This is the target price to place your buy order at. Use a Limit order at this price.",
        )
    with col2:
        st.metric(
            "🛑 Sell if it drops to",
            f"${stop:,.2f}",
            delta=f"-${entry-stop:,.2f} max loss per share",
            delta_color="inverse",
            help="Your safety net (stop loss). If the price drops here, sell immediately to protect yourself.",
        )
    with col3:
        st.metric(
            "🎯 First profit target",
            f"${t1:,.2f}",
            delta=f"+${t1-entry:,.2f} potential gain per share",
            help="Where to take your first profits. Many traders sell 50% of their position here.",
        )
    with col4:
        st.metric(
            "🏆 Full target",
            f"${t2:,.2f}",
            delta=f"+${t2-entry:,.2f} per share",
            help="The ultimate price target for this trade.",
        )

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric(
            "📦 Buy this many shares",
            shares,
            help=f"Based on your ${account_size:,.0f} account, risking no more than 2% per trade.",
        )
    with col6:
        st.metric(
            "💰 You'll spend",
            f"${total_cost:,.2f}",
            help="Total cost to buy the shares (shares × entry price).",
        )
    with col7:
        st.metric(
            "⚡ Max you could lose",
            f"${risk_d:,.2f}",
            help="This is your maximum loss if the stop loss triggers. It's capped at ~2% of your account.",
            delta_color="inverse",
        )
    with col8:
        st.metric(
            "📊 Reward vs. Risk",
            f"{rr:.1f}:1",
            help=jargon_tooltip("R:R ratio"),
        )

    # Full plan expander
    with st.expander("📋 See the full trade plan"):
        st.markdown("#### 💡 Why the system likes this stock")
        st.markdown(rec.get("reasoning", "N/A"))

        catalyst = rec.get("catalyst", "")
        if catalyst:
            st.markdown(f"**🔥 What's driving this:** {catalyst}")

        st.markdown("#### 📋 Exit Plan")
        st.markdown(rec.get("exit_plan", "N/A"))

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### 📝 Step-by-step: How to place this trade")
            st.caption("These steps work for most online brokers (Fidelity, Schwab, TD Ameritrade, etc.)")
            for i, step in enumerate(rec.get("broker_steps", []), 1):
                st.markdown(f"{i}. {step}")

        with col_b:
            st.markdown("#### ✅ Before you buy, check these things")
            for item in rec.get("pre_trade_checklist", []):
                st.markdown(f"- {item}")

        warn_list = rec.get("warnings", [])
        if warn_list:
            st.markdown("#### ⚠️ Warnings")
            for w in warn_list:
                st.warning(w)

        # Add to portfolio button
        if st.button(f"➕ I bought this — track it in my portfolio", key=f"add_{ticker}_{urgency}"):
            try:
                from src.portfolio.position_monitor import add_position
                add_position(
                    ticker=ticker,
                    entry_price=entry,
                    shares=shares,
                    stop_loss=stop,
                    target_1=t1,
                    target_2=t2,
                    trade_type=rec.get("timeframe", "swing").replace("_trade", ""),
                    notes=rec.get("catalyst", ""),
                )
                st.success(f"✅ {ticker} added to your portfolio tracker! Go to the Portfolio page to monitor it.")
            except Exception as exc:
                st.error(f"Failed to add position: {exc}")

    st.markdown("---")

with tab_day:
    if day_recs:
        for rec in day_recs:
            _render_recommendation(rec)
    else:
        st.markdown(
            """
            <div class="km-explainer">
              <strong>No day trade recommendations right now</strong><br>
              Day trading requires very specific conditions. Try switching to <strong>Swing Trade</strong> mode — it has more opportunities and is better for beginners.
            </div>
            """,
            unsafe_allow_html=True,
        )

with tab_swing:
    if swing_recs:
        for rec in swing_recs:
            _render_recommendation(rec)
    else:
        st.markdown(
            """
            <div class="km-explainer">
              <strong>No swing trade recommendations found</strong><br>
              Click <strong>"Find Me Good Stocks to Buy"</strong> above to run a fresh scan.
            </div>
            """,
            unsafe_allow_html=True,
        )

with tab_all:
    for rec in all_recs:
        _render_recommendation(rec)

