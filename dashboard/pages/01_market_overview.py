"""
Page 1: Market Overview — Kesmani Dashboard

Displays:
  - Market regime indicator
  - Benchmark ETF cards (SPY, QQQ, IWM)
  - Sector/group performance summary
  - Upcoming catalyst alerts
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from src.data.market_data import get_market_snapshot, get_price_summary
from src.data.news_catalysts import get_upcoming_catalysts
from src.utils.helpers import fmt_currency, fmt_pct
from dashboard.components.metrics import market_regime_card, benchmark_card
from config.settings import WATCHLIST, ALL_TICKERS, BENCHMARK_TICKERS

st.set_page_config(page_title="Market Overview | Kesmani", page_icon="🌍", layout="wide")

st.title("🌍 Market Overview")
st.caption("Live market regime, benchmark performance, and upcoming catalysts")

# ---------------------------------------------------------------------------
# Market regime & benchmarks
# ---------------------------------------------------------------------------
with st.spinner("Fetching market data…"):
    benchmarks = get_market_snapshot()

regime_changes = [b.get("day_change_pct", 0) for b in benchmarks if b]
avg_change = sum(regime_changes) / len(regime_changes) if regime_changes else 0
regime = "BULLISH" if avg_change > 0.3 else ("BEARISH" if avg_change < -0.3 else "NEUTRAL")

col_regime, col_spy, col_qqq, col_iwm = st.columns([2, 1, 1, 1])

with col_regime:
    market_regime_card(regime)

for col, snap in zip([col_spy, col_qqq, col_iwm], benchmarks):
    with col:
        if snap:
            benchmark_card(snap)

st.divider()

# ---------------------------------------------------------------------------
# Sector / group performance
# ---------------------------------------------------------------------------
st.subheader("📊 Watchlist Group Performance")

group_cols = st.columns(len(WATCHLIST))
for col, (group_name, tickers) in zip(group_cols, WATCHLIST.items()):
    with col:
        st.markdown(f"**{group_name.replace('_', ' ').title()}**")
        for ticker in tickers:
            snap = get_price_summary(ticker)
            if snap:
                chg = snap.get("day_change_pct", 0)
                color = "green" if chg >= 0 else "red"
                st.markdown(
                    f"{ticker}: :{color}[{fmt_pct(chg)}]"
                )
            else:
                st.caption(f"{ticker}: N/A")

st.divider()

# ---------------------------------------------------------------------------
# Catalyst alerts
# ---------------------------------------------------------------------------
st.subheader("📅 Upcoming Catalysts (next 14 days)")

with st.spinner("Checking earnings calendar…"):
    non_benchmark = [t for t in ALL_TICKERS if t not in BENCHMARK_TICKERS]
    catalysts = get_upcoming_catalysts(non_benchmark)

earnings = catalysts.get("earnings", [])
warnings = catalysts.get("warnings", [])

if warnings:
    st.warning(
        f"⚠️ **Earnings Warning:** {', '.join(w['ticker'] for w in warnings)} report within 7 days — "
        "consider sizing down or waiting for post-earnings reaction."
    )

if earnings:
    for e in earnings:
        icon = "⚠️" if e.get("warning") else "📅"
        date_str = (
            e["earnings_date"].strftime("%b %d, %Y")
            if hasattr(e["earnings_date"], "strftime")
            else str(e["earnings_date"])
        )
        st.markdown(f"{icon} **{e['ticker']}** — Earnings in **{e['days_until']} days** ({date_str})")
else:
    st.info("No earnings scheduled in the next 14 days for tracked tickers.")

st.divider()
st.subheader("📰 Key Economic Events to Monitor")
eco = catalysts.get("economic", [])
for event in eco:
    st.markdown(f"**{event['name']}** — {event['description']}")
