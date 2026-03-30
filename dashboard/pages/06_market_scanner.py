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

from dashboard.theme import apply_theme
apply_theme()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.subheader("🔎 Scanner Filters")

    account_size = st.number_input(
        "Account Size ($)",
        min_value=100.0,
        value=float(st.session_state.get("account_size", PORTFOLIO_SETTINGS["starting_capital"])),
        step=100.0,
        key="scanner_account_size",
    )
    st.session_state["account_size"] = account_size

    all_categories = sorted(SCAN_UNIVERSE.keys())
    selected_sectors = st.multiselect(
        "Sector / Category",
        options=all_categories,
        default=[],
        help="Leave empty to scan ALL sectors",
    )

    signal_opts = ["STRONG BUY", "BUY", "HOLD", "SELL", "AVOID"]
    selected_signals = st.multiselect(
        "Signal Filter",
        options=signal_opts,
        default=[],
        help="Leave empty to show all signals",
    )

    min_score = st.slider("Minimum Composite Score", 0, 100, 0)

    col_p1, col_p2 = st.columns(2)
    min_price = col_p1.number_input("Min Price ($)", min_value=0.0, value=0.0, step=1.0)
    max_price = col_p2.number_input("Max Price ($)", min_value=0.0, value=0.0, step=1.0,
                                     help="0 = no limit")

    afford_only = st.toggle("Only stocks I can afford", value=False,
                             help="Hides stocks where 1 share > 5% of account")

    sort_by = st.selectbox(
        "Sort By",
        ["Composite Score", "RSI", "Volume Ratio", "Price", "Day Change %"],
    )

    scan_btn = st.button(
        "🔎 Scan Full Market",
        type="primary",
        use_container_width=True,
        help="Scans 200+ tickers across all sectors. May take 30–60 seconds. "
             "Narrow to specific sectors above to speed up the scan.",
    )

# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------
st.title("🔎 Full Market Scanner — KešMani")
st.caption("Real-time scan of 200+ tickers across all sectors. Powered by KešMani.")

# ---------------------------------------------------------------------------
# Run scan
# ---------------------------------------------------------------------------
_SORT_KEY_MAP = {
    "Composite Score": ("composite_score", True),
    "RSI": ("rsi", False),
    "Volume Ratio": ("volume_ratio", True),
    "Price": ("price", False),
    "Day Change %": ("day_change_pct", True),
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

    with st.status("🔎 Scanning market…", expanded=True) as scan_status:
        st.write("📡 Fetching market data in parallel…")
        progress_bar = st.progress(0, text="Initializing…")

        for i, cat in enumerate(sectors_to_scan):
            st.write(f"📊 Analyzing sector: **{cat}** ({i + 1}/{len(sectors_to_scan)})")
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

        st.write(f"✅ Scan complete — {len(all_results)} tickers analyzed.")
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
# Quick Stats Row
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
qs_cols[0].metric("Total Scanned", len(filtered))
qs_cols[1].metric("🚀 Strong Buys", strong_buys)
qs_cols[2].metric("✅ Buys", buys)
qs_cols[3].metric("Avg Score", f"{avg_score:.1f}")
qs_cols[4].metric("🔥 Best Sector", best_sector)
qs_cols[5].metric("❄️ Worst Sector", worst_sector)

st.divider()

# ---------------------------------------------------------------------------
# Top Picks Banner (top 5)
# ---------------------------------------------------------------------------
top5 = [s for s in filtered if s["signal"] in ("STRONG BUY", "BUY")][:5]
if top5:
    st.subheader("🏆 Top Picks")
    pick_cols = st.columns(len(top5))
    for col, pick in zip(pick_cols, top5):
        sector_label = pick.get("sector") or _SECTOR_MAP.get(pick["ticker"], "")
        color = signal_color(pick["signal"])
        col.markdown(
            f"""
            <div style="background:#161b22;border:1px solid {color};border-radius:10px;
                        padding:12px;text-align:center;">
              <div style="font-size:1.4em;font-weight:bold;">{pick['ticker']}</div>
              <div style="color:{color};font-weight:bold;">{signal_emoji(pick['signal'])} {pick['signal']}</div>
              <div style="font-size:0.85em;color:#8b949e;">{sector_label}</div>
              <div style="font-size:1.1em;">Score: <b>{pick['composite_score']:.0f}</b></div>
              <div>Entry: <b>{fmt_currency(pick.get('entry'))}</b></div>
              <div style="color:#aaa;font-size:0.8em;">Stop: {fmt_currency(pick.get('stop_loss'))} | T1: {fmt_currency(pick.get('target_1'))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("")

# ---------------------------------------------------------------------------
# Sector Rotation Heatmap — Plotly Treemap
# ---------------------------------------------------------------------------
if sector_rotation:
    st.subheader("🌡️ Sector Rotation Heatmap")
    import plotly.express as px
    from dashboard.components.charts import get_chart_layout

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
        color_continuous_scale=[[0, "#EF4444"], [0.5, "#F59E0B"], [1.0, "#10B981"]],
        color_continuous_midpoint=50,
        custom_data=["avg_score", "strong_buys", "buys", "best_ticker"],
        title="",
    )
    tree_fig.update_traces(
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Avg Score: %{customdata[0]:.1f}<br>"
            "Strong Buys: %{customdata[1]}<br>"
            "Buys: %{customdata[2]}<br>"
            "Best: %{customdata[3]}"
            "<extra></extra>"
        ),
        texttemplate="%{label}<br>%{value} tickers",
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
    st.markdown("")

st.divider()

# ---------------------------------------------------------------------------
# Full Results Table
# ---------------------------------------------------------------------------
st.subheader(f"📊 Scan Results ({len(filtered)} tickers)")

if not filtered:
    st.info("No results match your filters. Try broadening the criteria.")
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

        with st.expander(f"{signal_emoji(signal_val)} {ticker} — {signal_val} | Score: {score:.0f} | {fmt_currency(entry)} | {sector_label}"):
            # Row 1: key metrics
            r1_cols = st.columns(8)
            r1_cols[0].metric("Signal", signal_val)
            r1_cols[1].metric("Score", f"{score:.0f}")
            r1_cols[2].metric("Entry", fmt_currency(entry))
            r1_cols[3].metric("Stop", fmt_currency(stop))
            r1_cols[4].metric("Target 1", fmt_currency(t1))
            r1_cols[5].metric("Target 2", fmt_currency(t2))
            r1_cols[6].metric("RSI", f"{rsi_val:.1f}" if rsi_val else "N/A")
            r1_cols[7].metric("Vol Ratio", f"{vol_ratio:.2f}x" if vol_ratio else "N/A")

            # Row 2: position info
            r2_cols = st.columns(4)
            r2_cols[0].metric("Shares to Buy", shares)
            r2_cols[1].metric("Total Cost", fmt_currency(position_val))
            r2_cols[2].metric("Risk $", fmt_currency(risk_d))
            r2_cols[3].metric("Trend", trend)

            # Reasoning
            if sig.get("reasoning"):
                st.caption(f"📝 {sig['reasoning']}")

            # Earnings / VIX warnings
            if sig.get("earnings_warning"):
                st.warning("⚠️ Earnings expected within 7 days — use caution.")
            if sig.get("vix_adjusted"):
                st.warning(sig["vix_adjusted"])

            # Execution plan
            st.markdown("---")
            st.markdown("#### 📋 Execution Plan")
            try:
                plan = generate_execution_plan(sig, account_size)

                ep_cols = st.columns(3)
                ep_cols[0].metric("Order Type", plan["order_type"])
                ep_cols[1].metric("Limit Price", fmt_currency(plan["limit_price"]))
                ep_cols[2].metric("Entry Strategy", plan["entry_strategy"].replace("_", " ").title())

                st.caption(f"🕐 **Timing:** {plan['timing']}")
                st.caption(f"🛡️ **Stop Type:** {plan['stop_loss_type'].replace('_', ' ').title()} at {fmt_currency(plan['stop_loss_price'])}")
                st.caption(f"💰 **Partial Profit Plan:** {plan['partial_profit_plan']}")

                # Scale-in plan
                if plan.get("scale_in_plan"):
                    st.markdown("**Scale-In Tranches:**")
                    for t in plan["scale_in_plan"]:
                        st.markdown(
                            f"- Tranche {t['tranche']} ({t['pct']}): **{t['shares']} shares** "
                            f"at ~${t['price']:,.2f} — {t['trigger']}"
                        )

                # Broker steps
                with st.expander("🖥️ Step-by-Step Broker Instructions"):
                    for j, step in enumerate(plan["broker_steps"], 1):
                        st.markdown(f"**{j}.** {step}")

                # Checklist
                with st.expander("✅ Pre-Trade Checklist"):
                    for item in plan["checklist"]:
                        st.markdown(item)

                # Warnings
                if plan["warnings"] and not all("No major warnings" in w for w in plan["warnings"]):
                    with st.expander("⚠️ Warnings"):
                        for w in plan["warnings"]:
                            st.markdown(w)

            except Exception as exc:
                st.error(f"Could not generate execution plan: {exc}")
