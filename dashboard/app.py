"""
Kesmani Trading Intelligence System — Main Streamlit Application.

Run with:
    streamlit run dashboard/app.py

The dashboard uses a dark trading terminal theme with a sidebar for
navigation.  Each page is a separate module in dashboard/pages/.
"""

import sys
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
    st.markdown(
        """
        **Navigation**
        Use the pages listed below to explore the dashboard.

        - 🌍 Market Overview
        - 🔍 Stock Screener
        - 📊 Stock Detail
        - 💼 Portfolio
        - 📋 Daily Report
        """
    )
    st.markdown("---")
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

    ---

    > ⚠️ **Disclaimer:** Kesmani is a trading tool, not financial advice.
    > All trading carries risk. Never risk more than you can afford to lose.
    """
)
