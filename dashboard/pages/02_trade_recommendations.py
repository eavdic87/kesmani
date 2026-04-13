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
)

st.set_page_config(
    page_title="KešMani | Trade Recommendations",
    page_icon="🎯",
    layout="wide",
)

apply_theme()

st.title("🎯 Trade Recommendations")
st.caption("Scan the market and find trade setups. Use the confidence filter below to control how many results you see.")
st.markdown("---")

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
with st.expander("⚙️ Scan Controls", expanded=False):
    col1, col2, col3 = st.columns(3)
    with col1:
        timeframe = st.selectbox(
            "Timeframe",
            options=["swing", "day", "position"],
            index=0,
            format_func=lambda x: {"swing": "🔵 Swing (2-14 days)", "day": "⚡ Day Trade", "position": "📅 Position (weeks)"}[x],
        )
    with col2:
        sector_options = ["All Sectors"] + sorted(SCAN_UNIVERSE.keys())
        sector_filter = st.selectbox("Sector Filter", sector_options)
    with col3:
        min_conf = st.slider(
            "Minimum Confidence %",
            min_value=0,
            max_value=95,
            value=50,
            step=5,
            help="Lower this to see more trade ideas. Higher = fewer but stronger signals. 75%+ is considered high confidence.",
        )

run_scan = st.button("🚀 Generate Recommendations", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Scan & generate recommendations
# ---------------------------------------------------------------------------
cache_key = f"trade_recs_{timeframe}_{sector_filter}"
if run_scan or cache_key not in st.session_state:
    with st.spinner("🔍 Scanning market and generating VP-level recommendations..."):
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
    st.info(
        f"No recommendations found with confidence ≥ {min_conf}%. "
        "Try lowering the confidence threshold or changing the sector filter."
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
    f'<b style="color:{rc};">Market: {regime}</b> — {summary}</div>',
    unsafe_allow_html=True,
)

# Risk warnings
warnings = analysis.get("risk_warnings", [])
for w in warnings:
    st.warning(w)

st.markdown(f"**{len(recommendations)} Setup{'s' if len(recommendations) != 1 else ''} Found** (confidence ≥ {min_conf}%)")
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

    color = confidence_color(confidence)

    # Card header
    st.markdown(
        f"""
        <div class="km-card" style="border-top:4px solid {color};">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <div>
            <span style="font-size:1.5rem;font-weight:700;">{ticker}</span>
            <span style="margin-left:8px;font-size:0.8rem;opacity:0.6;">{sector}</span>
        </div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
            {{signal_badge_html(signal)}}
            {{urgency_badge_html(urgency)}}
        </div>
        </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Confidence bar
    render_confidence_bar(confidence)

    # Key levels
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📥 Entry", f"${entry:,.2f}")
    with col2:
        st.metric("🛑 Stop Loss", f"${stop:,.2f}", delta=f"-${entry-stop:,.2f}", delta_color="inverse")
    with col3:
        st.metric("🎯 Target 1", f"${t1:,.2f}", delta=f"+${t1-entry:,.2f}")
    with col4:
        st.metric("🏆 Target 2", f"${t2:,.2f}", delta=f"+${t2-entry:,.2f}")

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("📦 Shares", shares)
    with col6:
        st.metric("💰 Total Cost", f"${total_cost:,.2f}")
    with col7:
        st.metric("⚡ Risk", f"${risk_d:,.2f}", delta_color="inverse")
    with col8:
        st.metric("📊 R:R Ratio", f"{rr:.1f}:1")

    # Full plan expander
    with st.expander("📋 View Full Trade Plan"):
        st.markdown("#### 💡 VP Reasoning")
        st.markdown(rec.get("reasoning", "N/A"))

        catalyst = rec.get("catalyst", "")
        if catalyst:
            st.markdown(f"**🔥 Catalyst:** {catalyst}")

        st.markdown("#### 📋 Exit Plan")
        st.markdown(rec.get("exit_plan", "N/A"))

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### 📝 Broker Steps")
            for i, step in enumerate(rec.get("broker_steps", []), 1):
                st.markdown(f"{i}. {{step}}")

        with col_b:
            st.markdown("#### ✅ Pre-Trade Checklist")
            for item in rec.get("pre_trade_checklist", []):
                st.markdown(f"- {{item}}")

        warn_list = rec.get("warnings", [])
        if warn_list:
            st.markdown("#### ⚠️ Warnings")
            for w in warn_list:
                st.warning(w)

        # Add to portfolio button
        if st.button(f"➕ Add {{ticker}} to Portfolio", key=f"add_{{ticker}}_{{urgency}}"):
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
                st.success(f"✅ {{ticker}} added to portfolio monitor!")
            except Exception as exc:
                st.error(f"Failed to add position: {exc}")

    st.markdown("---")

with tab_day:
    if day_recs:
        for rec in day_recs:
            _render_recommendation(rec)
    else:
        st.info("No day trade recommendations meet the current confidence threshold.")

with tab_swing:
    if swing_recs:
        for rec in swing_recs:
            _render_recommendation(rec)
    else:
        st.info("No swing trade recommendations found. Run a scan to generate recommendations.")

with tab_all:
    for rec in all_recs:
        _render_recommendation(rec)