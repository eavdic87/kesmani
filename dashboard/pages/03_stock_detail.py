"""
Page 3: Stock Detail — KešMani Dashboard

Interactive candlestick chart with all technical overlays,
fundamentals sidebar, and signal summary.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from src.data.market_data import fetch_ohlcv
from src.data.fundamentals import fetch_fundamentals
from src.analysis.technical import compute_all_indicators
from src.analysis.screener import score_ticker
from src.analysis.signals import generate_signal
from src.utils.helpers import fmt_currency, fmt_pct, fmt_large_number, fmt_ratio
from dashboard.components.charts import candlestick_chart
from dashboard.components.metrics import signal_summary_card
from config.settings import ALL_TICKERS, BENCHMARK_TICKERS, PORTFOLIO_SETTINGS

st.set_page_config(page_title="KešMani | Stock Detail", page_icon="📊", layout="wide")

from dashboard.theme import apply_theme
apply_theme()

st.title("📊 Stock Detail — KešMani")

# ---------------------------------------------------------------------------
# Ticker selector
# ---------------------------------------------------------------------------
all_tickers = ALL_TICKERS
default_idx = all_tickers.index("NVDA") if "NVDA" in all_tickers else 0
selected = st.selectbox("Select Ticker", options=all_tickers, index=default_idx)

account_size = st.sidebar.number_input(
    "Account Size ($)",
    min_value=100.0,
    value=float(PORTFOLIO_SETTINGS["starting_capital"]),
    step=100.0,
)

# Chart options
with st.sidebar:
    st.subheader("⚙️ Chart Options")
    show_sma = st.checkbox("Show SMAs", value=True)
    show_ema = st.checkbox("Show EMAs", value=True)
    show_bb = st.checkbox("Show Bollinger Bands", value=True)
    show_vol = st.checkbox("Show Volume", value=True)
    show_rsi = st.checkbox("Show RSI", value=True)
    show_macd = st.checkbox("Show MACD", value=True)

# ---------------------------------------------------------------------------
# Fetch data & compute indicators
# ---------------------------------------------------------------------------
with st.spinner(f"Loading {selected}…"):
    df = fetch_ohlcv(selected)
    indicators = compute_all_indicators(df) if not df.empty else {}
    fundamentals = fetch_fundamentals(selected)
    score = score_ticker(selected)
    signal_data = generate_signal(score, account_size)

if df.empty:
    st.error(f"No data available for {selected}.")
    st.stop()

# ---------------------------------------------------------------------------
# Layout: chart (left) + fundamentals sidebar (right)
# ---------------------------------------------------------------------------
col_chart, col_info = st.columns([3, 1])

with col_chart:
    fig = candlestick_chart(
        df, selected,
        show_sma=show_sma,
        show_ema=show_ema,
        show_bollinger=show_bb,
        show_volume=show_vol,
        show_rsi=show_rsi,
        show_macd=show_macd,
    )
    st.plotly_chart(fig, use_container_width=True)

with col_info:
    st.markdown("### 📌 Signal")
    signal_summary_card(signal_data)

    st.markdown("### 📐 Key Indicators")
    ind_data = {
        "RSI (14)": f"{indicators.get('rsi', 0):.1f}" if indicators.get("rsi") else "N/A",
        "Trend": indicators.get("trend", "N/A"),
        "Vol Ratio": f"{indicators.get('volume_ratio', 1.0):.1f}x",
        "MACD Signal": indicators.get("macd_crossover", "none").replace("_", " ").title(),
        "BB Squeeze": "Yes ⚡" if indicators.get("bb_squeeze") else "No",
        "52W High": fmt_currency(indicators.get("sma_200")),
        "Support": fmt_currency(indicators.get("support")),
        "Resistance": fmt_currency(indicators.get("resistance")),
    }
    for k, v in ind_data.items():
        st.metric(k, v)

    st.markdown("### 🏢 Fundamentals")
    fund_data = {
        "Company": fundamentals.get("company_name", selected),
        "Sector": fundamentals.get("sector", "N/A"),
        "Market Cap": fmt_large_number(fundamentals.get("market_cap")),
        "P/E (TTM)": fmt_ratio(fundamentals.get("pe_ratio")),
        "Forward P/E": fmt_ratio(fundamentals.get("forward_pe")),
        "PEG Ratio": fmt_ratio(fundamentals.get("peg_ratio")),
        "EPS Growth YoY": fmt_pct(
            (fundamentals.get("eps_growth_yoy") or 0) * 100 if fundamentals.get("eps_growth_yoy") else None
        ),
        "Revenue Growth": fmt_pct(
            (fundamentals.get("revenue_growth") or 0) * 100 if fundamentals.get("revenue_growth") else None
        ),
        "Profit Margin": fmt_pct(
            (fundamentals.get("profit_margin") or 0) * 100 if fundamentals.get("profit_margin") else None
        ),
        "Beta": f"{fundamentals.get('beta', 0):.2f}" if fundamentals.get("beta") else "N/A",
    }
    for k, v in fund_data.items():
        if k == "Company":
            st.caption(f"**{v}**")
        else:
            st.markdown(f"**{k}:** {v}")
