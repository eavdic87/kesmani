"""
Page 2: Stock Screener — Kesmani Dashboard

Displays the scored watchlist with composite signals, filtering, and sorting.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from src.analysis.screener import run_screener
from src.analysis.signals import generate_all_signals
from src.utils.helpers import fmt_currency, fmt_pct, signal_emoji
from dashboard.components.tables import screener_table
from config.settings import ALL_TICKERS, BENCHMARK_TICKERS, PORTFOLIO_SETTINGS, TICKER_SECTORS

st.set_page_config(page_title="Stock Screener | Kesmani", page_icon="🔍", layout="wide")

st.title("🔍 Stock Screener")
st.caption("Composite-scored watchlist with BUY/SELL/HOLD signals")

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.subheader("⚙️ Screener Filters")
    account_size = st.number_input(
        "Account Size ($)",
        min_value=100.0,
        value=float(st.session_state.get("account_size", PORTFOLIO_SETTINGS["starting_capital"])),
        step=100.0,
    )
    st.session_state["account_size"] = account_size

    # Sector filter
    all_sectors = sorted(set(TICKER_SECTORS.values()))
    selected_sectors = st.multiselect(
        "Filter by Sector",
        options=all_sectors,
        default=[],
        help="Leave empty to show all sectors",
    )

    signal_filter = st.multiselect(
        "Filter by Signal",
        options=["STRONG BUY", "BUY", "HOLD", "SELL", "AVOID"],
        default=[],
        help="Leave empty to show all signals",
    )

    # Price range filter
    col_p1, col_p2 = st.columns(2)
    min_price = col_p1.number_input("Min Price ($)", min_value=0.0, value=0.0, step=1.0)
    max_price = col_p2.number_input("Max Price ($)", min_value=0.0, value=0.0, step=1.0,
                                     help="0 = no limit")

    min_score = st.slider("Minimum Score", 0, 100, 0)
    run_btn = st.button("🔄 Run Screener", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Run screener
# ---------------------------------------------------------------------------
if run_btn or "screener_signals" not in st.session_state:
    tickers = [t for t in ALL_TICKERS if t not in BENCHMARK_TICKERS]
    with st.spinner(f"Screening {len(tickers)} tickers…"):
        results = run_screener(tickers)
        signals = generate_all_signals(results, account_size)
        # Attach sector labels
        for s in signals:
            s.setdefault("sector", TICKER_SECTORS.get(s["ticker"], "Unknown"))
        st.session_state["screener_signals"] = signals

signals = st.session_state.get("screener_signals", [])

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------
filtered = [s for s in signals if s["composite_score"] >= min_score]
if selected_sectors:
    filtered = [s for s in filtered if s.get("sector") in selected_sectors]
if signal_filter:
    filtered = [s for s in filtered if s["signal"] in signal_filter]
if min_price > 0:
    filtered = [s for s in filtered if (s.get("entry") or 0) >= min_price]
if max_price > 0:
    filtered = [s for s in filtered if (s.get("entry") or 0) <= max_price]

# ---------------------------------------------------------------------------
# Summary cards
# ---------------------------------------------------------------------------
strong_buys = sum(1 for s in filtered if s["signal"] == "STRONG BUY")
buys = sum(1 for s in filtered if s["signal"] == "BUY")
avoids = sum(1 for s in filtered if s["signal"] == "AVOID")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Screened", len(filtered))
c2.metric("🚀 Strong Buy", strong_buys)
c3.metric("✅ Buy", buys)
c4.metric("🚫 Avoid", avoids)

st.divider()

# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------
st.subheader(f"Results ({len(filtered)} tickers)")
screener_table(filtered)

# ---------------------------------------------------------------------------
# Top setups detail (with Execution Plan button)
# ---------------------------------------------------------------------------
top = [s for s in filtered if s["signal"] in ("STRONG BUY", "BUY")][:5]
if top:
    st.divider()
    st.subheader("🎯 Top Setups — Detail")
    for s in top:
        sector_label = s.get("sector", TICKER_SECTORS.get(s["ticker"], ""))
        with st.expander(
            f"{signal_emoji(s['signal'])} {s['ticker']} — {s['signal']} "
            f"(Score: {s['composite_score']:.0f}) | {sector_label}"
        ):
            cols = st.columns(5)
            cols[0].metric("Entry", fmt_currency(s.get("entry")))
            cols[1].metric("Stop Loss", fmt_currency(s.get("stop_loss")))
            cols[2].metric("Target 1", fmt_currency(s.get("target_1")))
            cols[3].metric("R:R", f"{s.get('rr_ratio', 'N/A')}:1")
            cols[4].metric("Sector", sector_label)
            st.caption(s.get("reasoning", ""))

            if s["signal"] in ("STRONG BUY", "BUY"):
                if st.button(f"🎯 View Execution Plan for {s['ticker']}", key=f"exec_{s['ticker']}"):
                    st.session_state["planner_ticker"] = s["ticker"]
                    st.session_state[f"plan_{s['ticker']}"] = None  # force regenerate
                    st.switch_page("pages/07_execution_planner.py")
