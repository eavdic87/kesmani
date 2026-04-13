"""
Page 6: Market Scanner — KešMani Dashboard

Full-market scanner that covers 200+ tickers across all sectors.
Filters by sector, signal type, score, and price range.
Shows sector rotation heatmap, top picks, and detailed execution plans.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from config.settings import PORTFOLIO_SETTINGS, SCAN_UNIVERSE, SECTOR_LABELS, TICKER_SECTORS
from src.utils.helpers import fmt_currency, fmt_pct, signal_color, signal_emoji

st.set_page_config(
    page_title="KešMani | Market Scanner",
    page_icon="🔎",
    layout="wide",
)

from dashboard.theme import apply_theme, get_theme, jargon_tooltip
apply_theme()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.subheader("🔎 Search Filters")
    st.caption("Use these filters to narrow down which stocks you want to see.")

    account_size = st.number_input(
        "Your Account Size ($)",
        min_value=100.0,
        value=float(st.session_state.get("account_size", PORTFOLIO_SETTINGS["starting_capital"])),
        step=100.0,
        key="scanner_account_size",
        help="Enter your account size so the system can calculate how many shares to recommend for each stock.",
    )
    st.session_state["account_size"] = account_size

    all_categories = sorted(SCAN_UNIVERSE.keys())
    selected_sectors = st.multiselect(
        "Industry / Sector",
        options=all_categories,
        default=[],
        help="Leave blank to search everything, or pick specific industries you're interested in. Example: Technology, Healthcare.",
    )

    signal_opts = ["STRONG BUY", "BUY", "HOLD", "SELL", "AVOID"]
    selected_signals = st.multiselect(
        "Signal Filter",
        options=signal_opts,
        default=[],
        help="STRONG BUY and BUY are the ones worth looking at if you want to buy something. Leave blank to show all.",
    )

    min_score = st.slider(
        "Minimum Health Score",
        0, 100, 0,
        help="Score of 65+ is a good signal. 80+ is excellent. Think of it like a school grade — higher is better.",
    )

    col_p1, col_p2 = st.columns(2)
    min_price = col_p1.number_input(
        "Min Price ($)",
        min_value=0.0,
        value=0.0,
        step=1.0,
        help="Filter out stocks cheaper than this price.",
    )
    max_price = col_p2.number_input(
        "Max Price ($)",
        min_value=0.0,
        value=0.0,
        step=1.0,
        help="0 = no maximum. Set a price to filter out expensive stocks.",
    )

    afford_only = st.toggle(
        "Only stocks I can afford",
        value=False,
        help="This hides very expensive stocks where even 1 share would cost more than 5% of your account. Useful for smaller accounts.",
    )

    sort_by = st.selectbox(
        "Sort Results By",
        [
            "Best Opportunity (Score)",
            "Most Momentum (RSI)",
            "Unusual Volume",
            "Price (Low to High)",
            "Best Day Today",
        ],
        help="Choose how to order the results. 'Best Opportunity' shows the highest-scored stocks first.",
    )

    scan_btn = st.button(
        "🔍 Search the Market Now",
        type="primary",
        use_container_width=True,
        help="Scans 200+ stocks across all industries. May take 30–60 seconds. "
             "Select specific industries above to speed up the scan.",
    )

# ---------------------------------------------------------------------------
# Title & description
# ---------------------------------------------------------------------------
st.title("🔎 Market Scanner")
st.caption("Search the entire market — 200+ stocks across every industry.")
st.markdown(
    """
    <div class="km-explainer">
      <strong>What does this page do?</strong><br>
      Use this to find stocks across any industry. The system will score each one and show you the best opportunities.
      Unlike Trade Recommendations (which shows only the top picks), this page shows <em>everything</em> — so you can
      do your own research and explore.
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Run scan
# ---------------------------------------------------------------------------
_SORT_KEY_MAP = {
    "Best Opportunity (Score)": ("composite_score", True),
    "Most Momentum (RSI)": ("rsi", False),
    "Unusual Volume": ("volume_ratio", True),
    "Price (Low to High)": ("price", False),
    "Best Day Today": ("day_change_pct", True),
}

if scan_btn or "scanner_results" not in st.session_state:
    from src.data.market_scanner import scan_market
    from config.settings import FULL_UNIVERSE, SCAN_UNIVERSE

    # Build ticker list from selected sectors / full universe
    if selected_sectors:
        tickers: list[str] = []
        seen: set[str] = set()
        for cat in selected_sectors:
            for t in SCAN_UNIVERSE.get(cat, []):
                if t not in seen:
                    seen.add(t)
                    tickers.append(t)
    else:
        tickers = FULL_UNIVERSE

    sectors_to_scan = selected_sectors if selected_sectors else list(SCAN_UNIVERSE.keys())
    all_results: list[dict] = []
    seen_tickers: set[str] = set()

    with st.status("🔍 Searching the market…", expanded=True) as scan_status:
        st.write("📡 Fetching live market data…")
        progress_bar = st.progress(0, text="Starting up…")

        for i, cat in enumerate(sectors_to_scan):
            st.write(f"📊 Analyzing: **{cat}** ({i + 1}/{len(sectors_to_scan)})")
            progress_bar.progress((i + 1) / len(sectors_to_scan), text=f"Scanning {cat}…")
            cat_tickers = [t for t in SCAN_UNIVERSE.get(cat, []) if t not in seen_tickers]
            if not cat_tickers:
                continue
            try:
                chunk = scan_market(
                    tickers=cat_tickers,
                    account_size=account_size,
                    min_score=0.0,
                )
                for r in chunk:
                    if r["ticker"] not in seen_tickers:
                        seen_tickers.add(r["ticker"])
                        all_results.append(r)
            except Exception as exc:
                st.warning(f"Scan failed for {cat}: {exc}")

        st.write(f"✅ Done — {len(all_results)} stocks analyzed.")
        scan_status.update(label="✅ Scan complete!", state="complete", expanded=False)

    st.session_state["scanner_results"] = all_results
    st.session_state["scanner_account_size_used"] = account_size

raw_results: list[dict] = st.session_state.get("scanner_results", [])

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------
_SECTOR_MAP: dict[str, str] = {**TICKER_SECTORS, **SECTOR_LABELS}

filtered = raw_results[:]

if selected_sectors:
    sector_labels_selected = {
        t
        for cat in selected_sectors
        for t in SCAN_UNIVERSE.get(cat, [])
    }
    filtered = [r for r in filtered if r["ticker"] in sector_labels_selected]

if selected_signals:
    filtered = [r for r in filtered if r["signal"] in selected_signals]

filtered = [r for r in filtered if r["composite_score"] >= min_score]

if min_price > 0:
    filtered = [r for r in filtered if (r.get("entry") or 0) >= min_price]
if max_price > 0:
    filtered = [r for r in filtered if (r.get("entry") or 0) <= max_price]

if afford_only and account_size > 0:
    filtered = [r for r in filtered if (r.get("entry") or 0) <= account_size * 0.05]

# Sort
sort_key, sort_desc = _SORT_KEY_MAP.get(sort_by, ("composite_score", True))

def _sort_val(s: dict) -> float:
    if sort_key == "composite_score":
        return s.get("composite_score", 0.0)
    if sort_key == "rsi":
        return s.get("indicators", {}).get("rsi", 50.0) or 50.0
    if sort_key == "volume_ratio":
        return s.get("indicators", {}).get("volume_ratio", 1.0) or 1.0
    if sort_key == "price":
        return s.get("entry") or 0.0
    if sort_key == "day_change_pct":
        return s.get("indicators", {}).get("day_change_pct", 0.0) or 0.0
    return 0.0

filtered = sorted(filtered, key=_sort_val, reverse=sort_desc)

# ---------------------------------------------------------------------------
# Quick Stats Row — plain English labels
# ---------------------------------------------------------------------------
strong_buys = sum(1 for s in filtered if s["signal"] == "STRONG BUY")
buys = sum(1 for s in filtered if s["signal"] == "BUY")
avg_score = (
    sum(s["composite_score"] for s in filtered) / len(filtered) if filtered else 0.0
)

# Best / worst sector
from src.data.market_scanner import get_sector_rotation
sector_rotation = st.session_state.get("sector_rotation")
if scan_btn or sector_rotation is None:
    try:
        sector_rotation = get_sector_rotation(account_size=account_size)
        st.session_state["sector_rotation"] = sector_rotation
    except Exception:
        sector_rotation = []

best_sector = sector_rotation[0]["sector"] if sector_rotation else "N/A"
worst_sector = sector_rotation[-1]["sector"] if sector_rotation else "N/A"

qs_cols = st.columns(6)
qs_cols[0].metric(
    "Stocks Analyzed",
    len(filtered),
    help="Total number of stocks shown after applying your filters.",
)
qs_cols[1].metric(
    "🚀 Excellent Opportunities",
    strong_buys,
    help="Stocks with STRONG BUY signal — the system's highest-confidence picks.",
)
qs_cols[2].metric(
    "✅ Good Opportunities",
    buys,
    help="Stocks with BUY signal — solid opportunities worth considering.",
)
qs_cols[3].metric(
    "Average Health Score",
    f"{avg_score:.1f}",
    help="The average composite score across all filtered stocks. 65+ is healthy.",
)
qs_cols[4].metric(
    "🔥 Hottest Industry",
    best_sector,
    help="The sector with the highest average score right now — where the best opportunities are concentrated.",
)
qs_cols[5].metric(
    "❄️ Weakest Industry",
    worst_sector,
    help="The sector with the lowest average score — consider avoiding stocks in this sector for now.",
)

st.divider()

# ---------------------------------------------------------------------------
# Top Picks Banner (top 5)
# ---------------------------------------------------------------------------
top5 = [s for s in filtered if s["signal"] in ("STRONG BUY", "BUY")][:5]
if top5:
    st.subheader("🏆 Today's Top 5 Picks")
    st.caption("The system's highest-scored stocks right now, based on all available signals.")
    t = get_theme()
    pick_cols = st.columns(len(top5))
    for col, pick in zip(pick_cols, top5):
        sector_label = pick.get("sector") or _SECTOR_MAP.get(pick["ticker"], "")
        color = signal_color(pick["signal"])
        col.markdown(
            f"""
            <div style="background:{t['surface']};border:1px solid {color};border-radius:10px;
                        padding:14px;text-align:center;">
              <div style="font-size:1.4em;font-weight:800;">{pick['ticker']}</div>
              <div style="color:{color};font-weight:700;margin:4px 0;">{signal_emoji(pick['signal'])} {pick['signal']}</div>
              <div style="font-size:0.8em;opacity:0.65;margin-bottom:6px;">{sector_label}</div>
              <div style="font-size:1rem;font-weight:600;">Health Score: <b>{pick['composite_score']:.0f}/100</b></div>
              <div style="margin-top:4px;">Buy at: <b>{fmt_currency(pick.get('entry'))}</b></div>
              <div style="font-size:0.8em;opacity:0.7;margin-top:2px;">Stop: {fmt_currency(pick.get('stop_loss'))} | Target: {fmt_currency(pick.get('target_1'))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("")

# ---------------------------------------------------------------------------
# Sector Rotation Heatmap — Plotly Treemap
# ---------------------------------------------------------------------------
if sector_rotation:
    st.subheader("🌡️ Industry Heatmap")
    st.caption(
        "Bigger = more stocks in that industry. "
        "Greener = more buying opportunities right now. Click a sector to explore."
    )
    import plotly.express as px
    from dashboard.components.charts import get_chart_layout

    # Color scale: respects color-blind mode
    _is_cb = st.session_state.get("colorblind_mode", False)
    if _is_cb:
        # Blue (low) → orange (high) — deuteranopia-safe
        _color_scale = [[0, "#C04000"], [0.5, "#F59E0B"], [1.0, "#0075DC"]]
    else:
        _color_scale = [[0, "#EF4444"], [0.5, "#F59E0B"], [1.0, "#10B981"]]

    treemap_data = {
        "sector": [sr["sector"] for sr in sector_rotation],
        "avg_score": [sr["avg_score"] for sr in sector_rotation],
        "ticker_count": [sr["ticker_count"] for sr in sector_rotation],
        "strong_buys": [sr["strong_buys"] for sr in sector_rotation],
        "buys": [sr["buys"] for sr in sector_rotation],
        "best_ticker": [sr["best_ticker"] for sr in sector_rotation],
        "label": [
            f"{sr['sector']}<br>Score: {sr['avg_score']:.0f}<br>"
            f"🚀{sr['strong_buys']} ✅{sr['buys']}"
            for sr in sector_rotation
        ],
    }

    tree_fig = px.treemap(
        treemap_data,
        path=["sector"],
        values="ticker_count",
        color="avg_score",
        color_continuous_scale=_color_scale,
        color_continuous_midpoint=50,
        custom_data=["avg_score", "strong_buys", "buys", "best_ticker"],
        title="",
    )
    tree_fig.update_traces(
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Health Score: %{customdata[0]:.1f}/100<br>"
            "Strong Buys: %{customdata[1]}<br>"
            "Buys: %{customdata[2]}<br>"
            "Best Stock: %{customdata[3]}"
            "<extra></extra>"
        ),
        texttemplate="%{label}<br>%{value} stocks",
    )
    layout = get_chart_layout()
    tree_fig.update_layout(
        height=400,
        paper_bgcolor=layout["paper_bgcolor"],
        font_color=layout["font"]["color"],
        margin=dict(l=10, r=10, t=10, b=10),
        coloraxis_showscale=True,
    )
    st.plotly_chart(tree_fig, use_container_width=True)
    st.caption("💡 Green sectors have the most buying opportunities right now. Focus your research there.")
    st.markdown("")

st.divider()

# ---------------------------------------------------------------------------
# Full Results Table
# ---------------------------------------------------------------------------
st.subheader(f"📊 All Results ({len(filtered)} stocks)")

if not filtered:
    st.markdown(
        """
        <div class="km-explainer">
          <strong>No stocks match your current filters</strong><br><br>
          Try loosening your search criteria:
          <ul style="margin-top:8px;">
            <li>Remove the signal filter (or select more signal types)</li>
            <li>Lower the Minimum Health Score to 0</li>
            <li>Deselect the industry filter to search all sectors</li>
            <li>Click "Search the Market Now" to run a fresh scan</li>
          </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    from src.analysis.execution import generate_execution_plan

    for sig in filtered:
        ind = sig.get("indicators", {})
        ticker = sig["ticker"]
        signal_val = sig["signal"]
        score = sig["composite_score"]
        entry = sig.get("entry")
        stop = sig.get("stop_loss")
        t1 = sig.get("target_1")
        t2 = sig.get("target_2")
        rsi_val = ind.get("rsi")
        trend = ind.get("trend", "N/A")
        vol_ratio = ind.get("volume_ratio", 1.0)
        day_chg = ind.get("day_change_pct")
        sector_label = sig.get("sector") or _SECTOR_MAP.get(ticker, "")
        shares = sig.get("position_shares", 0)
        position_val = sig.get("position_value", 0.0)
        risk_d = sig.get("risk_amount", 0.0)
        color = signal_color(signal_val)

        # Score label
        if score >= 80:
            score_label = "Excellent 🚀"
        elif score >= 65:
            score_label = "Good ✅"
        elif score >= 50:
            score_label = "Fair 🔶"
        else:
            score_label = "Weak ❄️"

        expander_label = (
            f"{signal_emoji(signal_val)} {ticker} — {signal_val} | "
            f"Health Score: {score:.0f}/100 ({score_label}) | "
            f"Price: {fmt_currency(entry)} | {sector_label}"
        )

        with st.expander(expander_label):
            # Reasoning first — most important for beginners
            if sig.get("reasoning"):
                st.markdown(
                    f"""
                    <div class="km-explainer">
                      <strong>💡 Why the system flagged this stock:</strong><br>
                      {sig['reasoning']}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Row 1: key metrics — plain English
            r1_cols = st.columns(8)
            r1_cols[0].metric(
                "Recommendation",
                signal_val,
                help="The system's recommendation for this stock.",
            )
            r1_cols[1].metric(
                "Health Score",
                f"{score:.0f}/100",
                help=jargon_tooltip("composite score"),
            )
            r1_cols[2].metric(
                "Buy At",
                fmt_currency(entry),
                help="The target price to place your buy order.",
            )
            r1_cols[3].metric(
                "Sell If Drops To",
                fmt_currency(stop),
                help=jargon_tooltip("stop loss"),
            )
            r1_cols[4].metric(
                "First Target",
                fmt_currency(t1),
                help=jargon_tooltip("target"),
            )
            r1_cols[5].metric(
                "Full Target",
                fmt_currency(t2),
            )
            r1_cols[6].metric(
                "RSI (Momentum)",
                f"{rsi_val:.1f}" if rsi_val else "N/A",
                help=jargon_tooltip("RSI"),
            )
            r1_cols[7].metric(
                "Volume Surge",
                f"{vol_ratio:.2f}x" if vol_ratio else "N/A",
                help="How much higher today's trading volume is compared to the average. 2x = twice the normal volume.",
            )

            # Row 2: position info
            r2_cols = st.columns(4)
            r2_cols[0].metric(
                "Shares to Buy",
                shares,
                help=f"Based on your ${account_size:,.0f} account, risking 2% per trade.",
            )
            r2_cols[1].metric(
                "Total Cost",
                fmt_currency(position_val),
                help="Total amount you'd spend to buy these shares.",
            )
            r2_cols[2].metric(
                "Max You Could Lose",
                fmt_currency(risk_d),
                help="Your maximum loss if the stop loss triggers.",
            )
            r2_cols[3].metric(
                "Trend Direction",
                trend,
                help="Is the stock in an uptrend, downtrend, or sideways trend?",
            )

            # Earnings / VIX warnings
            if sig.get("earnings_warning"):
                st.warning("⚠️ Earnings report expected within 7 days — stock could move sharply in either direction. Use extra caution.")
            if sig.get("vix_adjusted"):
                st.warning(sig["vix_adjusted"])

            # Execution plan
            st.markdown("---")
            st.markdown("#### 📋 How to Execute This Trade")
            try:
                plan = generate_execution_plan(sig, account_size)

                ep_cols = st.columns(3)
                ep_cols[0].metric(
                    "How to Place the Order",
                    plan["order_type"],
                    help="Limit order = you set the exact price. Market order = you buy at whatever the current price is. Limit orders are safer.",
                )
                ep_cols[1].metric("Limit Price", fmt_currency(plan["limit_price"]))
                ep_cols[2].metric("Entry Strategy", plan["entry_strategy"].replace("_", " ").title())

                st.caption(f"🕐 **Best time to enter:** {plan['timing']}")
                st.caption(f"🛡️ **Stop Loss Type:** {plan['stop_loss_type'].replace('_', ' ').title()} at {fmt_currency(plan['stop_loss_price'])}")
                st.caption(f"💰 **Profit Taking Plan:** {plan['partial_profit_plan']}")

                # Scale-in plan
                if plan.get("scale_in_plan"):
                    st.markdown("**Buying in Stages (Scale-In Plan):**")
                    for t in plan["scale_in_plan"]:
                        st.markdown(
                            f"- Stage {t['tranche']} ({t['pct']}): **{t['shares']} shares** "
                            f"at ~${t['price']:,.2f} — trigger: {t['trigger']}"
                        )

                # Broker steps
                with st.expander("🖥️ How to buy this stock (step by step)"):
                    st.caption("These steps work for most online brokers (Fidelity, Schwab, TD Ameritrade, etc.)")
                    for j, step in enumerate(plan["broker_steps"], 1):
                        st.markdown(f"**{j}.** {step}")

                # Checklist
                with st.expander("✅ Check these things before buying"):
                    for item in plan["checklist"]:
                        st.markdown(item)

                # Warnings
                if plan["warnings"] and not all("No major warnings" in w for w in plan["warnings"]):
                    with st.expander("⚠️ Warnings"):
                        for w in plan["warnings"]:
                            st.markdown(w)

            except Exception as exc:
                st.error(f"Could not generate execution plan: {exc}")

