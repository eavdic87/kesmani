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
    initial_sidebar_state="auto",
)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
st.session_state["dark_mode"] = True
if "account_size" not in st.session_state:
    from config.settings import ACCOUNT_SIZE
    st.session_state["account_size"] = ACCOUNT_SIZE
if "colorblind_mode" not in st.session_state:
    st.session_state["colorblind_mode"] = False

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

    # Color-blind mode
    cb_mode = st.toggle(
        "👁️ Color-blind Mode",
        value=st.session_state.get("colorblind_mode", False),
        key="_cb_toggle",
        help="Switches signal colors to blue/orange (deuteranopia-friendly)",
    )
    if cb_mode != st.session_state.get("colorblind_mode", False):
        st.session_state["colorblind_mode"] = cb_mode
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
# Helper: cache freshness
# ---------------------------------------------------------------------------
from config.settings import CACHE_DIR
import time as _t

def _get_cache_freshness() -> str:
    """Return a string describing how fresh the cached data is."""
    try:
        cache_files = list(CACHE_DIR.glob("*.parquet"))
        if not cache_files:
            return "No cached data"
        latest_mtime = max(f.stat().st_mtime for f in cache_files)
        dt = datetime.fromtimestamp(latest_mtime)
        age_minutes = (_t.time() - latest_mtime) / 60
        if age_minutes < 1:
            age_str = "just now"
        elif age_minutes < 60:
            age_str = f"{int(age_minutes)}m ago"
        else:
            age_str = f"{int(age_minutes/60)}h ago"
        return f"{dt.strftime('%H:%M:%S')} ({age_str})"
    except Exception:
        return "Unknown"

# ---------------------------------------------------------------------------
# Home page content
# ---------------------------------------------------------------------------
# First-visit banner
if not st.session_state.get("onboarding_dismissed"):
    st.markdown(
        """
        <div style="background:linear-gradient(135deg,#2563EB,#7C3AED);border-radius:14px;
                    padding:20px 28px;margin-bottom:20px;color:white;display:flex;
                    align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
          <div>
            <div style="font-size:1.4rem;font-weight:800;margin-bottom:4px;">👋 First time here? Start here →</div>
            <div style="opacity:0.9;font-size:0.95rem;">KešMani helps you find good stocks to buy, tells you exactly how many shares to get, and warns you when it's time to sell.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("✅ Got it — don't show this again", key="dismiss_onboarding"):
        st.session_state["onboarding_dismissed"] = True
        st.rerun()

st.markdown(
    "<h1 style='font-size:2.5rem;margin-bottom:0;'>📈 KešMani</h1>"
    "<p style='font-size:1.1rem;opacity:0.7;margin-top:4px;'>Your personal Trading Intelligence System — built for everyone, not just experts.</p>",
    unsafe_allow_html=True,
)
st.markdown("---")

# ── Live status bar ────────────────────────────────────────────────────────
from config.settings import SCAN_UNIVERSE as _SU
_total_tracked = sum(len(v) for v in _SU.values())
status_col1, status_col2, status_col3, status_col4 = st.columns(4)
with status_col1:
    st.markdown(market_status_html(is_open), unsafe_allow_html=True)
with status_col2:
    freshness_status = _get_cache_freshness()
    st.caption(f"🕐 Last data: **{freshness_status}**")
with status_col3:
    st.caption(f"📊 Stocks tracked: **{_total_tracked}+**")
with status_col4:
    acct_display = f"${st.session_state.get('account_size', 5000):,.0f}"
    st.caption(f"💰 Your account: **{acct_display}**")

st.markdown("---")

# ── Where do you want to start? ───────────────────────────────────────────
st.markdown("### 🗺️ Where do you want to start?")
st.caption("Follow these steps in order for the best experience.")

step_col1, step_col2, step_col3 = st.columns(3)

with step_col1:
    st.markdown(
        """
        <div class="km-card" style="border-top:4px solid #3B82F6;text-align:center;">
        <div style="font-size:2rem;margin-bottom:8px;">🌍</div>
        <div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;opacity:0.6;margin-bottom:4px;">Step 1</div>
        <h3 style="margin:0 0 8px 0;">Check the Market First</h3>
        <p>See if today is a good day to be buying stocks, or if you should wait.</p>
        <p style="font-size:0.82rem;font-style:italic;opacity:0.7;">→ Market Overview page</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with step_col2:
    st.markdown(
        """
        <div class="km-card" style="border-top:4px solid #10B981;text-align:center;">
        <div style="font-size:2rem;margin-bottom:8px;">🎯</div>
        <div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;opacity:0.6;margin-bottom:4px;">Step 2</div>
        <h3 style="margin:0 0 8px 0;">Find Stocks to Buy</h3>
        <p>The system will find the best opportunities right now and tell you exactly how many shares to buy and where to set your safety net.</p>
        <p style="font-size:0.82rem;font-style:italic;opacity:0.7;">→ Trade Recommendations page</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with step_col3:
    st.markdown(
        """
        <div class="km-card" style="border-top:4px solid #8B5CF6;text-align:center;">
        <div style="font-size:2rem;margin-bottom:8px;">💼</div>
        <div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;opacity:0.6;margin-bottom:4px;">Step 3</div>
        <h3 style="margin:0 0 8px 0;">Track What You Own</h3>
        <p>See how your stocks are doing and get alerts when it's time to sell.</p>
        <p style="font-size:0.82rem;font-style:italic;opacity:0.7;">→ Portfolio Monitor page</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── How KešMani Works ─────────────────────────────────────────────────────
with st.expander("📖 How KešMani Works — 4 simple steps", expanded=False):
    st.markdown(
        """
        <div class="km-step">
          <div class="km-step-number">1</div>
          <div class="km-step-body"><strong>Check if the market is in good shape</strong><br>
          Go to <em>Market Overview</em>. If the regime is BULLISH, it's a good time to look for buys.
          If it's BEARISH, be cautious.</div>
        </div>
        <div class="km-step">
          <div class="km-step-number">2</div>
          <div class="km-step-body"><strong>Find stocks the system rates highly</strong><br>
          Go to <em>Trade Recommendations</em>. Click "Find Me Good Stocks to Buy". The system scans 80+ stocks and shows you the best setups.</div>
        </div>
        <div class="km-step">
          <div class="km-step-number">3</div>
          <div class="km-step-body"><strong>Review the trade plan — entry, stop loss, how many shares</strong><br>
          Each recommendation card shows the buy price, your safety net (stop loss), and exactly how many shares to buy based on your account size.</div>
        </div>
        <div class="km-step">
          <div class="km-step-number">4</div>
          <div class="km-step-body"><strong>Track your positions and act on alerts</strong><br>
          After you buy, add the stock to <em>Portfolio Monitor</em>. KešMani will alert you when it hits your target (take profits!) or stop loss (sell to limit losses).</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Additional tools ───────────────────────────────────────────────────────
st.markdown("### 🔧 More Tools")
extra_col1, extra_col2, extra_col3 = st.columns(3)

with extra_col1:
    st.markdown(
        """
        <div class="km-card" style="border-top:4px solid #F59E0B;text-align:center;">
        <div style="font-size:2rem;margin-bottom:8px;">🔎</div>
        <h3 style="margin:0 0 8px 0;">Search the Whole Market</h3>
        <p>Browse 200+ stocks across every industry. Filter by sector, signal, or price.</p>
        <p style="font-size:0.82rem;font-style:italic;opacity:0.7;">→ Market Scanner page</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with extra_col2:
    st.markdown(
        """
        <div class="km-card" style="border-top:4px solid #6B7280;text-align:center;">
        <div style="font-size:2rem;margin-bottom:8px;">📊</div>
        <h3 style="margin:0 0 8px 0;">Dive Into Any Stock</h3>
        <p>Detailed charts, RSI, MACD, and Bollinger Bands for any ticker you want to investigate.</p>
        <p style="font-size:0.82rem;font-style:italic;opacity:0.7;">→ Stock Detail page</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with extra_col3:
    st.markdown(
        """
        <div class="km-card" style="border-top:4px solid #EC4899;text-align:center;">
        <div style="font-size:2rem;margin-bottom:8px;">📋</div>
        <h3 style="margin:0 0 8px 0;">Daily Market Brief</h3>
        <p>Auto-generated morning report with market regime, top picks, and key levels to watch.</p>
        <p style="font-size:0.82rem;font-style:italic;opacity:0.7;">→ Daily Brief page</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")
st.markdown(
    """
    > ⚠️ **Important:** KešMani gives you information and analysis — it does **not** guarantee profits.
    > All investing carries risk and you could lose money. The system's recommendations are for
    > informational purposes only. Always make your own decisions, start with small amounts while
    > you learn, and never invest money you can't afford to lose.
    """
)

st.markdown("---")
st.caption("⚠️ For informational purposes only. Not financial advice.")
