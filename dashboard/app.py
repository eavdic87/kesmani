"""
Kesmani Trading Intelligence System — Main Streamlit Application.

Run with:
    streamlit run dashboard/app.py

The dashboard uses a dark trading terminal theme with a sidebar for
navigation.  Each page is a separate module in dashboard/pages/.
"""

import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is on the Python path so all imports resolve correctly
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from src.utils.helpers import setup_logging

# Configure logging once at app startup
setup_logging()

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Kesmani | Trading Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Global dark-theme CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Dark trading terminal theme */
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .css-1d391kg { background-color: #161b22; }
    [data-testid="stSidebar"] { background-color: #161b22; }
    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown p { color: #c9d1d9; }
    .stMetric label { color: #8b949e !important; }
    .stMetric .metric-container { background: #161b22; border-radius: 8px; padding: 10px; }
    div[data-testid="metric-container"] { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px; }
    .stDataFrame { border: 1px solid #30363d; }
    .stSelectbox > div { background-color: #161b22; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 📈 Kesmani")
    st.markdown("**Trading Intelligence System**")
    st.markdown("---")

    # Persistent account size input
    from config.settings import PORTFOLIO_SETTINGS
    account_size = st.number_input(
        "💰 Account Size ($)",
        min_value=100.0,
        value=float(st.session_state.get("account_size", PORTFOLIO_SETTINGS["starting_capital"])),
        step=100.0,
        key="sidebar_account_size",
    )
    st.session_state["account_size"] = account_size

    st.markdown("---")
    st.markdown(
        """
        **Navigation**
        Use the pages listed below to explore the dashboard.

        - 🌍 Market Overview
        - 🔍 Stock Screener
        - 📊 Stock Detail
        - 💼 Portfolio
        - 📋 Daily Report
        - 🔎 Market Scanner *(new)*
        - 🎯 Execution Planner *(new)*
        """
    )
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

    # Last refresh timestamp
    last_ts = st.session_state.get("last_refresh_ts")
    if last_ts:
        ts_str = datetime.fromtimestamp(last_ts).strftime("%H:%M:%S")
        st.caption(f"Last refresh: {ts_str}")

    st.caption("⚠️ For informational purposes only. Not financial advice.")

# ---------------------------------------------------------------------------
# Home page content
# ---------------------------------------------------------------------------
st.title("📈 Kesmani Trading Intelligence System")
st.markdown(
    """
    Welcome to **Kesmani** — your personal AI-powered trading intelligence platform.

    Use the **sidebar navigation** to explore:

    | Page | Description |
    |---|---|
    | 🌍 Market Overview | Live market regime, index performance, sector rotation |
    | 🔍 Stock Screener | Composite-scored watchlist with BUY/SELL/HOLD signals |
    | 📊 Stock Detail | Candlestick charts, indicators, entry/stop/target levels |
    | 💼 Portfolio | Position tracker, P&L, risk heat gauge |
    | 📋 Daily Report | Full morning briefing with one-click email delivery |
    | 🔎 Market Scanner | **NEW** — Scan 200+ tickers across all sectors in real time |
    | 🎯 Execution Planner | **NEW** — Full VP-level trade execution guide with broker steps |

    ---

    > ⚠️ **Disclaimer:** Kesmani is a trading tool, not financial advice.
    > All trading carries risk. Never risk more than you can afford to lose.
    """
)
