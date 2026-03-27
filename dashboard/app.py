"""
KešMani Trading Intelligence System — Main Streamlit Application.

Run with:
    streamlit run dashboard/app.py

The dashboard uses a modern card-based design with light/dark mode toggle.
Each page is a separate module in dashboard/pages/.
"""

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from src.utils.helpers import setup_logging
from dashboard.theme import apply_theme, market_status_html

setup_logging()

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="KešMani | Trading Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = False
if "account_size" not in st.session_state:
    from config.settings import ACCOUNT_SIZE
    st.session_state["account_size"] = ACCOUNT_SIZE

# Apply active theme CSS
apply_theme()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        "<h2 style='margin-bottom:0;'>📈 KešMani</h2>"
        "<p style='margin-top:0;font-size:0.8rem;opacity:0.7;'>Trading Intelligence</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # Dark/Light mode toggle
    dark = st.toggle("🌙 Dark Mode", value=st.session_state["dark_mode"], key="_dm_toggle")
    if dark != st.session_state["dark_mode"]:
        st.session_state["dark_mode"] = dark
        st.rerun()

    st.markdown("---")

    # Account size input
    from config.settings import ACCOUNT_SIZE
    account_size = st.number_input(
        "💰 Account Size ($)",
        min_value=100.0,
        value=float(st.session_state.get("account_size", ACCOUNT_SIZE)),
        step=100.0,
        key="sidebar_account_size",
    )
    st.session_state["account_size"] = account_size

    st.markdown("---")

    # Market status
    try:
        from src.data.data_provider import get_provider
        is_open = get_provider().is_market_open()
    except Exception:
        is_open = False
    st.markdown(market_status_html(is_open), unsafe_allow_html=True)

    # Last refresh
    last_ts = st.session_state.get("last_refresh_ts")
    if last_ts:
        ts_str = datetime.fromtimestamp(last_ts).strftime("%H:%M:%S")
        st.caption(f"🕐 Last scan: {ts_str}")

    st.markdown("---")

    # Auto-refresh toggle
    auto_refresh = st.toggle("🔄 Auto-Refresh", value=False, key="auto_refresh")
    if auto_refresh:
        refresh_interval = st.selectbox(
            "Interval",
            options=["5 minutes", "15 minutes", "30 minutes"],
            index=1,
        )
        interval_seconds = {"5 minutes": 300, "15 minutes": 900, "30 minutes": 1800}[refresh_interval]
        import time as _time
        last_refresh = st.session_state.get("last_refresh_ts", 0)
        if _time.time() - last_refresh > interval_seconds:
            st.session_state["last_refresh_ts"] = _time.time()
            st.rerun()

    st.markdown("---")
    st.caption("⚠️ For informational purposes only. Not financial advice.")

# ---------------------------------------------------------------------------
# Home page content
# ---------------------------------------------------------------------------
st.markdown(
    "<h1 style='font-size:2.5rem;margin-bottom:0;'>📈 KešMani</h1>"
    "<p style='font-size:1.1rem;opacity:0.7;margin-top:4px;'>Trading Intelligence System</p>",
    unsafe_allow_html=True,
)
st.markdown("---")

# Quick navigation cards
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
        <div class="km-card">
        <h3>🌍 Market Overview</h3>
        <p>Market regime, benchmark performance, sector rotation heatmap, and breadth analysis.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        """
        <div class="km-card">
        <h3>🎯 Trade Recommendations</h3>
        <p>VP-level trade setups with entry, stop, targets, and step-by-step execution guides.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        """
        <div class="km-card">
        <h3>🔎 Market Scanner</h3>
        <p>Full 200+ ticker universe scan with sector, signal, and score filtering.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

col4, col5, col6 = st.columns(3)

with col4:
    st.markdown(
        """
        <div class="km-card">
        <h3>📊 Stock Detail</h3>
        <p>Candlestick charts, RSI, MACD, Bollinger Bands, and signal analysis for any ticker.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col5:
    st.markdown(
        """
        <div class="km-card">
        <h3>💼 Portfolio Monitor</h3>
        <p>Live P&amp;L tracking, stop/target alerts, trailing stops, and portfolio heat gauge.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col6:
    st.markdown(
        """
        <div class="km-card">
        <h3>📋 Daily Brief</h3>
        <p>Auto-generated morning report with market regime, top picks, and key levels to watch.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")
st.markdown(
    """
    > ⚠️ **Disclaimer:** KešMani is a trading intelligence tool, not financial advice.
    > All trading carries risk. Never risk more than you can afford to lose.
    > Always do your own research before entering any trade.
    """
)
