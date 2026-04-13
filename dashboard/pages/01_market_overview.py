"""
KešMani — Market Overview Page.

Displays market regime, benchmark performance, sector rotation,
and breadth analysis using the centralized theme system.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from dashboard.theme import (
    apply_theme, signal_badge_html, score_color, badge_html,
    plain_english_regime, plain_english_regime_action,
)

st.set_page_config(
    page_title="KešMani | Market Overview",
    page_icon="🌍",
    layout="wide",
)

apply_theme()

st.title("🌍 Market Overview")
st.caption("This page tells you whether today is a good day to be buying stocks.")
st.markdown("---")

# Collapsible jargon explainer
with st.expander("📖 What do these terms mean? (click to learn)", expanded=False):
    st.markdown(
        """
        <div class="km-explainer">
        <strong>📖 Quick glossary — no experience needed</strong>
        <ul style="margin-top:10px;">
          <li><strong>Market Regime</strong> — Is the overall market going up, down, or sideways? This tells you the "mood" of the market.</li>
          <li><strong>SPY / QQQ / IWM</strong> — These are "ETFs" that track groups of stocks. SPY = top 500 US companies. QQQ = tech companies. IWM = smaller companies. When these are green, the market is healthy.</li>
          <li><strong>Sector Rotation</strong> — Which industries (tech, healthcare, energy, etc.) are performing the best right now.</li>
          <li><strong>Market Breadth</strong> — How many stocks across the whole market have positive signals. A high % bullish = healthy market.</li>
          <li><strong>Health Score (0–100)</strong> — KešMani's rating for a stock or sector. Like a school grade: 80+ = excellent, 65–79 = good, below 50 = weak.</li>
        </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

account_size = st.session_state.get("account_size", 5000.0)

# Import scanner
try:
    from src.data.market_scanner import scan_market, get_sector_rotation
    from src.analysis.trade_advisor import analyze_market, _detect_market_regime
    from config.settings import SCAN_UNIVERSE
except ImportError as e:
    st.error(f"Import error: {e}")
    st.stop()

# Scan controls
col_refresh, col_quick = st.columns([1, 3])
with col_refresh:
    run_scan = st.button(
        "🔄 Refresh Market Data",
        type="primary",
        help="Fetches the latest prices for the key benchmarks (SPY, QQQ, IWM) and top tech stocks.",
    )

# Use cached results or scan benchmarks
if run_scan or "market_overview_scan" not in st.session_state:
    with st.spinner("Loading the latest market data..."):
        try:
            # Scan a representative subset for speed
            key_tickers = ["SPY", "QQQ", "IWM"] + SCAN_UNIVERSE.get("technology", [])[:5]
            results = scan_market(tickers=key_tickers, account_size=account_size)
            st.session_state["market_overview_scan"] = results
        except Exception as exc:
            st.error(f"Scan failed: {exc}")
            results = []
else:
    results = st.session_state.get("market_overview_scan", [])

if not results:
    st.markdown(
        """
        <div class="km-explainer">
          <strong>👋 No data loaded yet</strong><br><br>
          Click <strong>"Refresh Market Data"</strong> above to load the latest market information.
          This will fetch live prices for the major market benchmarks and show you the current market conditions.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# ---------------------------------------------------------------------------
# Market Regime Banner — Hero of the page
# ---------------------------------------------------------------------------
regime = _detect_market_regime(results)
regime_colors = {
    "BULLISH": "#10B981",
    "BEARISH": "#EF4444",
    "VOLATILE": "#F59E0B",
    "NEUTRAL": "#6B7280",
}
regime_emojis = {
    "BULLISH": "📈",
    "BEARISH": "📉",
    "VOLATILE": "⚡",
    "NEUTRAL": "➡️",
}
regime_color = regime_colors.get(regime, "#6B7280")
regime_emoji = regime_emojis.get(regime, "⬜")
regime_description = plain_english_regime(regime)
regime_action = plain_english_regime_action(regime)

st.markdown("### 🌡️ Current Market Conditions")
st.markdown(
    f"""
    <div style="background:{regime_color}18;border:2px solid {regime_color};
    border-radius:16px;padding:24px 32px;margin-bottom:20px;text-align:center;">
    <div style="font-size:3rem;margin-bottom:8px;">{regime_emoji}</div>
    <div style="font-size:2rem;font-weight:800;color:{regime_color};margin-bottom:6px;">{regime}</div>
    <div style="font-size:0.8rem;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;opacity:0.6;margin-bottom:12px;">Market Regime</div>
    <div style="font-size:1.05rem;max-width:560px;margin:0 auto 12px auto;">{regime_description}</div>
    <div style="font-size:0.95rem;font-weight:600;max-width:560px;margin:0 auto;
         padding:10px 20px;background:{regime_color}20;border-radius:8px;">{regime_action}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Benchmark Performance Cards
# ---------------------------------------------------------------------------
st.markdown("### 📊 Market Thermometers (SPY, QQQ, IWM)")
st.caption(
    "These 3 ETFs act as the market's thermometers. "
    "When they're all green, the market is healthy. When they're red, be cautious."
)

benchmark_tickers = ["SPY", "QQQ", "IWM"]
benchmark_labels = {
    "SPY": "S&P 500 — Top 500 US companies",
    "QQQ": "Nasdaq — Tech-heavy index",
    "IWM": "Russell 2000 — Small companies",
}
benchmark_results = {r["ticker"]: r for r in results if r["ticker"] in benchmark_tickers}

cols = st.columns(len(benchmark_tickers))
for i, ticker in enumerate(benchmark_tickers):
    with cols[i]:
        sig = benchmark_results.get(ticker)
        if sig:
            score = sig.get("composite_score", 50)
            signal = sig.get("signal", "HOLD")
            entry = sig.get("entry") or sig.get("indicators", {}).get("current_price", 0)
            day_chg = sig.get("indicators", {}).get("day_change_pct", 0.0)
            color = score_color(score)
            chg_color = "#10B981" if day_chg >= 0 else "#EF4444"
            chg_arrow = "▲" if day_chg >= 0 else "▼"
            st.markdown(
                f"""
                <div class="km-card" style="text-align:center;">
                  <div style="font-size:1.2rem;font-weight:700;">{ticker}</div>
                  <div style="font-size:0.78rem;opacity:0.65;margin-bottom:8px;">{benchmark_labels[ticker]}</div>
                  <div style="font-size:1.8rem;font-weight:800;">${entry:,.2f}</div>
                  <div style="color:{chg_color};font-size:0.95rem;font-weight:600;margin:4px 0;">{chg_arrow} {day_chg:+.2f}% today</div>
                  <div style="font-size:0.85rem;color:{color};font-weight:600;margin-top:6px;">Health Score: {score:.0f}/100</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(signal_badge_html(signal), unsafe_allow_html=True)
        else:
            st.markdown(
                f"""
                <div class="km-card" style="text-align:center;">
                  <div style="font-size:1.2rem;font-weight:700;">{ticker}</div>
                  <div style="font-size:0.78rem;opacity:0.65;margin-bottom:8px;">{benchmark_labels[ticker]}</div>
                  <div style="opacity:0.5;">Data not available</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.markdown("---")

# ---------------------------------------------------------------------------
# Sector Rotation Heatmap
# ---------------------------------------------------------------------------
st.markdown("### 🔥 Which Industries Are Hottest Right Now?")
st.caption(
    "A high score (green) means stocks in that industry are performing well. "
    "Focus your search on the green sectors for the best opportunities."
)

try:
    rotation = get_sector_rotation(account_size=account_size)
    if rotation:
        # Display as colored grid
        n_cols = 3
        rows = [rotation[i:i+n_cols] for i in range(0, min(len(rotation), 12), n_cols)]
        for row in rows:
            cols = st.columns(n_cols)
            for j, sector_data in enumerate(row):
                with cols[j]:
                    avg = sector_data["avg_score"]
                    color = score_color(avg)
                    if avg >= 70:
                        temp_label = "Hot 🔥"
                    elif avg >= 50:
                        temp_label = "Warm ✅"
                    else:
                        temp_label = "Weak ❄️"
                    st.markdown(
                        f"""
                        <div class="km-card-compact" style="border-left:4px solid {color};">
                        <div style="font-weight:700;font-size:0.95rem;">{sector_data['sector']}</div>
                        <div style="font-size:1.4rem;font-weight:800;color:{color};">Score: {avg:.0f}/100 — {temp_label}</div>
                        <div style="font-size:0.78rem;opacity:0.65;margin-top:2px;">
                        {sector_data['ticker_count']} stocks tracked ·
                        {sector_data['strong_buys']} strong buys · {sector_data['buys']} buys
                        </div>
                        <div style="font-size:0.78rem;margin-top:2px;">Top performer: <b>{sector_data['best_ticker']}</b></div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
    else:
        st.markdown(
            """
            <div class="km-explainer">
              <strong>📊 Sector data not available yet</strong><br>
              Run a full market scan from the <em>Market Scanner</em> page first, then come back here to see which industries are performing best.
            </div>
            """,
            unsafe_allow_html=True,
        )
except Exception as exc:
    st.warning(f"Sector rotation unavailable: {exc}")

st.markdown("---")

# ---------------------------------------------------------------------------
# Market Breadth
# ---------------------------------------------------------------------------
st.markdown("### 📈 What Is the Market Doing Overall?")
total = len(results)
if total > 0:
    buys = sum(1 for r in results if r.get("signal") in ("STRONG BUY", "BUY"))
    strong_buys = sum(1 for r in results if r.get("signal") == "STRONG BUY")
    sells = sum(1 for r in results if r.get("signal") in ("SELL", "AVOID"))
    holds = total - buys - sells
    buy_pct = buys / total * 100

    # Interpretation
    if buy_pct >= 60:
        breadth_interp = "The majority of stocks have positive signals. Strong conditions for buying. ✅"
    elif buy_pct >= 40:
        breadth_interp = "Mixed signals — be selective. Focus only on the highest-confidence setups."
    else:
        breadth_interp = "Most stocks are under pressure. Consider waiting or using smaller position sizes. ⚠️"

    st.caption(
        f"Right now, {buy_pct:.0f}% of tracked stocks have positive signals. {breadth_interp}"
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "📈 Going Up (Bullish)",
            f"{buys} stocks ({buys/total*100:.0f}%)",
            help="Number of stocks with BUY or STRONG BUY signals — these are the opportunities.",
        )
    with col2:
        st.metric(
            "🚀 Very Bullish",
            f"{strong_buys} ({strong_buys/total*100:.0f}%)",
            help="Stocks with STRONG BUY signal — the system's highest-confidence opportunities.",
        )
    with col3:
        st.metric(
            "⏳ Waiting (Neutral)",
            f"{holds} ({holds/total*100:.0f}%)",
            help="Stocks with HOLD signal — not strong enough to act on right now.",
        )
    with col4:
        st.metric(
            "📉 Going Down (Bearish)",
            f"{sells} ({sells/total*100:.0f}%)",
            help="Stocks with SELL or AVOID signal — stay away from these.",
        )

    # Visual breadth bar
    buy_pct = buys / total * 100
    sell_pct = sells / total * 100
    hold_pct = holds / total * 100
    st.markdown(
        f"""
        <div style="border-radius:6px;overflow:hidden;height:24px;display:flex;margin:8px 0;">
        <div style="width:{buy_pct:.1f}%;background:#10B981;"></div>
        <div style="width:{hold_pct:.1f}%;background:#6B7280;"></div>
        <div style="width:{sell_pct:.1f}%;background:#EF4444;"></div>
        </div>
        <div style="display:flex;gap:20px;font-size:0.85rem;margin-bottom:16px;">
        <span style="color:#10B981;">■ Going Up {buy_pct:.0f}%</span>
        <span style="color:#6B7280;">■ Waiting {hold_pct:.0f}%</span>
        <span style="color:#EF4444;">■ Going Down {sell_pct:.0f}%</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# What Should I Do Today? action panel
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("### 🎯 What Should I Do Today?")

if total > 0:
    buy_pct_calc = buys / total * 100
    action_lines = []
    if regime == "BULLISH" and buy_pct_calc >= 50:
        action_lines.append("✅ **Market conditions look favorable.** You can actively look for BUY and STRONG BUY opportunities.")
        action_lines.append("📋 Head to **Trade Recommendations** to see today's best setups with complete trade plans.")
        action_lines.append("💡 Use normal position sizes (the system will calculate shares for you).")
    elif regime == "BEARISH" or buy_pct_calc < 30:
        action_lines.append("⚠️ **Market conditions are weak.** Be cautious with new positions.")
        action_lines.append("🛡️ If you have open positions, make sure your stop losses are in place.")
        action_lines.append("💡 Consider waiting for conditions to improve before opening new trades.")
    elif regime == "VOLATILE":
        action_lines.append("⚡ **Market is choppy.** Only take the highest-confidence setups (85%+ confidence).")
        action_lines.append("📉 Use smaller position sizes than usual — reduce risk per trade.")
        action_lines.append("🔍 Focus on the sectors with the highest scores in the chart above.")
    else:
        action_lines.append("🤔 **Mixed conditions.** Be selective — only the best setups are worth taking right now.")
        action_lines.append("📋 Look for STRONG BUY signals with high confidence scores in Trade Recommendations.")
        action_lines.append("💡 When in doubt, wait. Patience is a trading skill.")

    for line in action_lines:
        st.markdown(line)

