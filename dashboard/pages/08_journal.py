"""
Page 8: Trade Journal — KešMani Dashboard

Add trade journal entries, browse history, and filter by ticker,
setup type, and date.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import pandas as pd

from src.portfolio.journal import (
    add_journal_entry,
    get_journal_entries,
    delete_journal_entry,
    VALID_SETUP_TYPES,
)
from config.settings import ALL_TICKERS

st.set_page_config(page_title="KešMani | Trade Journal", page_icon="📓", layout="wide")

from dashboard.theme import apply_theme
apply_theme()

st.title("📓 Trade Journal — KešMani")
st.caption("Document your trades, review setups, and learn from every position.")

# ---------------------------------------------------------------------------
# Add new journal entry
# ---------------------------------------------------------------------------
with st.expander("➕ Add Journal Entry", expanded=True):
    with st.form("journal_form"):
        j1, j2 = st.columns(2)
        with j1:
            j_ticker = st.selectbox("Ticker", ALL_TICKERS)
            j_setup = st.selectbox(
                "Setup Type",
                sorted(VALID_SETUP_TYPES),
                help="Classification of the trade setup",
            )
            j_emotions = st.text_input(
                "Emotions / Mindset",
                placeholder="e.g. confident, disciplined, FOMO…",
            )
        with j2:
            j_tags = st.text_input(
                "Tags (comma-separated)",
                placeholder="e.g. breakout, earnings, momentum",
            )
            j_trade_id = st.text_input(
                "Position ID (optional)",
                placeholder="Link to open/closed position",
            )

        j_notes = st.text_area(
            "Trade Notes",
            placeholder=(
                "Describe your rationale, what you saw in the chart, "
                "what went well, and what you would do differently…"
            ),
            height=120,
        )

        submitted = st.form_submit_button("📝 Save Entry", type="primary")
        if submitted:
            if not j_notes.strip():
                st.error("Please enter some trade notes before saving.")
            else:
                tags = [t.strip() for t in j_tags.split(",") if t.strip()]
                entry = add_journal_entry(
                    ticker=j_ticker,
                    notes=j_notes,
                    setup_type=j_setup,
                    emotions=j_emotions,
                    tags=tags,
                    trade_id=j_trade_id or None,
                )
                st.success(f"✅ Journal entry saved for {j_ticker} ({j_setup})")

st.divider()

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
st.subheader("🔍 Browse Journal")

f1, f2, f3 = st.columns(3)
with f1:
    filter_ticker = st.text_input("Filter by Ticker", placeholder="e.g. NVDA")
with f2:
    filter_setup = st.selectbox("Filter by Setup", ["All"] + sorted(VALID_SETUP_TYPES))
with f3:
    filter_date = st.date_input("From Date", value=None)

# ---------------------------------------------------------------------------
# Journal table
# ---------------------------------------------------------------------------
entries = get_journal_entries(
    ticker=filter_ticker.upper() if filter_ticker else None,
    date_from=filter_date.isoformat() if filter_date else None,
    setup_type=filter_setup if filter_setup != "All" else None,
)

if not entries:
    st.info("No journal entries found. Add your first entry above!")
else:
    st.caption(f"{len(entries)} entries")
    for entry in entries:
        tags_str = " ".join(f"`{t}`" for t in entry.get("tags", []))
        with st.expander(
            f"**{entry['ticker']}** — {entry['setup_type']} — {entry['date']}",
            expanded=False,
        ):
            col_left, col_right = st.columns([3, 1])
            with col_left:
                st.markdown(f"**Notes:** {entry['notes']}")
                if entry.get("emotions"):
                    st.markdown(f"**Emotions:** {entry['emotions']}")
                if tags_str:
                    st.markdown(f"**Tags:** {tags_str}")
                if entry.get("trade_id"):
                    st.markdown(f"**Position ID:** `{entry['trade_id']}`")
            with col_right:
                if st.button("🗑️ Delete", key=f"del_{entry['id']}"):
                    if delete_journal_entry(entry["id"]):
                        st.success("Entry deleted.")
                        st.rerun()
