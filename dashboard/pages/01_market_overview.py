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
from dashboard.theme import apply_theme, signal_badge_html, score_color, badge_html

st.set_page_config(
    page_title="KešMani | Market Overview",
    page_icon="🌍",
    layout="wide",
)

apply_theme()

st.title("🌍 Market Overview")
st.caption("Market regime, benchmarks, sector rotation, and breadth analysis.")
st.markdown("---")

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
    run_scan = st.button("🔄 Scan Benchmarks", type="primary")

# Use cached results or scan benchmarks
if run_scan or "market_overview_scan" not in st.session_state:
    with st.spinner("Scanning benchmarks and key sectors..."):
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
    st.info("Click **Scan Benchmarks** to load market data.")
    st.stop()

# ---------------------------------------------------------------------------
# Market Regime Banner
# ---------------------------------------------------------------------------
regime = _detect_market_regime(results)
regime_colors = {
    "BULLISH": "#10B981",
    "BEARISH": "#EF4444",
    "VOLATILE": "#F59E0B",
    "NEUTRAL": "#6B7280",
}
regime_emojis = {
    "BULLISH": "🟢",
    "BEARISH": "🔴",
    "VOLATILE": "🟡",
    "NEUTRAL": "⚪",
}
regime_color = regime_colors.get(regime, "#6B7280")
regime_emoji = regime_emojis.get(regime, "⚪")

st.markdown(
    f"""
    <div style="background:{regime_color}20;border:2px solid {regime_color};
    border-radius:12px;padding:16px 24px;margin-bottom:16px;">
    <span style="font-size:1.5rem;font-weight:700;color:{regime_color};">
    {regime_emoji} Market Regime: {regime}
    </span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Benchmark Performance Cards
# ---------------------------------------------------------------------------
st.subheader("📊 Benchmark Performance")
benchmark_tickers = ["SPY", "QQQ", "IWM"]
benchmark_results = {r["ticker"]: r for r in results if r["ticker"] in benchmark_tickers}

cols = st.columns(len(benchmark_tickers))
for i, ticker in enumerate(benchmark_tickers):
    with cols[i]:
        sig = benchmark_results.get(ticker)
        if sig:
            score = sig.get("composite_score", 50)
            signal = sig.get("signal", "HOLD")
            entry = sig.get("entry") or sig.get("indicators", {}).get("current_price", 0)
            color = score_color(score)
            st.metric(
                label=f"**{ticker}**",
                value=f"${entry:,.2f}" if entry else "N/A",
                delta=f"Score: {score:.0f}",
            )
            st.markdown(signal_badge_html(signal), unsafe_allow_html=True)
        else:
            st.metric(label=ticker, value="N/A")

st.markdown("---")

# ---------------------------------------------------------------------------
# Sector Rotation Heatmap
# ---------------------------------------------------------------------------
st.subheader("🔥 Sector Rotation")
st.caption("Sectors ranked by average composite score across all scanned tickers.")

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
                    st.markdown(
                        f"""
                        <div class="km-card-compact" style="border-left:4px solid {color};">
                        <div style="font-weight:600;font-size:0.9rem;">{sector_data['sector']}</div>
                        <div style="font-size:1.3rem;font-weight:700;color:{color};">{avg:.0f}</div>
                        <div style="font-size:0.75rem;opacity:0.7;">
                        {sector_data['ticker_count']} tickers · 
                        {sector_data['strong_buys']} SB · {sector_data['buys']} B
                        </div>
                        <div style="font-size:0.75rem;">Top: <b>{sector_data['best_ticker']}</b></div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
    else:
        st.info("Sector rotation data not available. Run a full market scan first.")
except Exception as exc:
    st.warning(f"Sector rotation unavailable: {exc}")

st.markdown("---")

# ---------------------------------------------------------------------------
# Market Breadth
# ---------------------------------------------------------------------------
st.subheader("📈 Market Breadth")
total = len(results)
if total > 0:
    buys = sum(1 for r in results if r.get("signal") in ("STRONG BUY", "BUY"))
    strong_buys = sum(1 for r in results if r.get("signal") == "STRONG BUY")
    sells = sum(1 for r in results if r.get("signal") in ("SELL", "AVOID"))
    holds = total - buys - sells

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🟢 Bullish", f"{buys} ({buys/total*100:.0f}%)")
    with col2:
        st.metric("🔥 Strong Buy", f"{strong_buys} ({strong_buys/total*100:.0f}%)")
    with col3:
        st.metric("⚪ Hold/Neutral", f"{holds} ({holds/total*100:.0f}%)")
    with col4:
        st.metric("🔴 Bearish", f"{sells} ({sells/total*100:.0f}%)")

    # Visual breadth bar
    buy_pct = buys / total * 100
    sell_pct = sells / total * 100
    hold_pct = holds / total * 100
    st.markdown(
        f"""
        <div style="border-radius:6px;overflow:hidden;height:20px;display:flex;margin:8px 0;">
        <div style="width:{buy_pct:.1f}%;background:#10B981;"></div>
        <div style="width:{hold_pct:.1f}%;background:#6B7280;"></div>
        <div style="width:{sell_pct:.1f}%;background:#EF4444;"></div>
        </div>
        <div style="display:flex;gap:16px;font-size:0.8rem;margin-bottom:16px;">
        <span style="color:#10B981;">■ Bullish {buy_pct:.0f}%</span>
        <span style="color:#6B7280;">■ Neutral {hold_pct:.0f}%</span>
        <span style="color:#EF4444;">■ Bearish {sell_pct:.0f}%</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
