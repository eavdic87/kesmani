"""
KešMani — Centralized theme and design system.

Provides light/dark mode colors, CSS injection, and UI helper functions.
All dashboard pages import from this single source for consistent styling.
"""

import streamlit as st

# ---------------------------------------------------------------------------
# Color palettes
# ---------------------------------------------------------------------------

LIGHT = {
    "bg": "#FFFFFF",
    "surface": "#F8F9FA",
    "border": "#E9ECEF",
    "text_primary": "#212529",
    "text_secondary": "#6C757D",
    "accent": "#2563EB",
    "success": "#10B981",
    "danger": "#EF4444",
    "warning": "#F59E0B",
    "hold": "#6B7280",
    "card_shadow": "0 1px 3px rgba(0,0,0,0.10), 0 1px 2px rgba(0,0,0,0.06)",
}

DARK = {
    "bg": "#0F172A",
    "surface": "#1E293B",
    "border": "#334155",
    "text_primary": "#F1F5F9",
    "text_secondary": "#94A3B8",
    "accent": "#3B82F6",
    "success": "#10B981",
    "danger": "#EF4444",
    "warning": "#F59E0B",
    "hold": "#6B7280",
    "card_shadow": "0 1px 3px rgba(0,0,0,0.40), 0 1px 2px rgba(0,0,0,0.30)",
}

# Signal color mapping
_SIGNAL_COLORS = {
    "STRONG BUY": {"light": "#10B981", "dark": "#10B981"},
    "BUY": {"light": "#34D399", "dark": "#34D399"},
    "HOLD": {"light": "#6B7280", "dark": "#9CA3AF"},
    "SELL": {"light": "#EF4444", "dark": "#EF4444"},
    "AVOID": {"light": "#B91C1C", "dark": "#DC2626"},
}

# Confidence tier colors
_CONFIDENCE_COLORS = {
    "very_high": "#10B981",   # 95+
    "high": "#34D399",        # 85-94
    "good": "#F59E0B",        # 75-84
}


def get_theme() -> dict:
    """Return the active theme palette based on session_state dark_mode."""
    if st.session_state.get("dark_mode", False):
        return DARK
    return LIGHT


def apply_theme() -> None:
    """Inject CSS for the active theme into the Streamlit app."""
    t = get_theme()
    is_dark = st.session_state.get("dark_mode", False)
    sidebar_bg = t["surface"] if not is_dark else "#0F172A"

    css = f"""
    <style>
    /* ── Base ── */
    .stApp {{
        background-color: {t["bg"]};
        color: {t["text_primary"]};
    }}
    [data-testid="stSidebar"] {{
        background-color: {sidebar_bg};
        border-right: 1px solid {t["border"]};
    }}
    [data-testid="stSidebar"] * {{
        color: {t["text_primary"]} !important;
    }}

    /* ── Cards ── */
    .km-card {{
        background: {t["surface"]};
        border: 1px solid {t["border"]};
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: {t["card_shadow"]};
    }}
    .km-card-compact {{
        background: {t["surface"]};
        border: 1px solid {t["border"]};
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 8px;
    }}

    /* ── Metrics ── */
    div[data-testid="metric-container"] {{
        background-color: {t["surface"]};
        border: 1px solid {t["border"]};
        border-radius: 12px;
        padding: 16px;
        box-shadow: {t["card_shadow"]};
    }}
    .stMetric label {{
        color: {t["text_secondary"]} !important;
        font-size: 0.85rem !important;
    }}
    .stMetric [data-testid="metric-value"] {{
        color: {t["text_primary"]} !important;
    }}

    /* ── Badges ── */
    .km-badge {{
        display: inline-block;
        padding: 3px 10px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }}
    .km-badge-strong-buy {{ background: #10B981; color: white; }}
    .km-badge-buy {{ background: #34D399; color: white; }}
    .km-badge-hold {{ background: #6B7280; color: white; }}
    .km-badge-sell {{ background: #EF4444; color: white; }}
    .km-badge-avoid {{ background: #B91C1C; color: white; }}

    /* ── Urgency badges ── */
    .km-urgency-now {{ background: #EF4444; color: white; animation: pulse 1.5s infinite; }}
    .km-urgency-today {{ background: #F59E0B; color: white; }}
    .km-urgency-this-week {{ background: #3B82F6; color: white; }}
    .km-urgency-watch {{ background: #6B7280; color: white; }}

    @keyframes pulse {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.6; }}
    }}

    /* ── Data table ── */
    .stDataFrame {{
        border: 1px solid {t["border"]};
        border-radius: 8px;
    }}

    /* ── Buttons ── */
    .stButton > button {{
        border-radius: 8px;
        font-weight: 600;
    }}

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {{
        background-color: {t["surface"]};
        border-radius: 8px;
        padding: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        color: {t["text_secondary"]};
    }}
    .stTabs [aria-selected="true"] {{
        color: {t["accent"]};
    }}

    /* ── Expander ── */
    .streamlit-expanderHeader {{
        background-color: {t["surface"]};
        border-radius: 8px;
    }}

    /* ── Progress bars ── */
    .stProgress > div > div > div > div {{
        background-color: {t["accent"]};
    }}

    /* ── Selectbox, inputs ── */
    .stSelectbox > div, .stMultiSelect > div {{
        background-color: {t["surface"]};
    }}

    /* ── Headers ── */
    h1, h2, h3 {{
        color: {t["text_primary"]};
    }}
    p, li {{
        color: {t["text_secondary"]};
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def signal_color(signal: str, mode: str = "bg") -> str:
    """
    Return the color associated with a trading signal.

    Parameters
    ----------
    signal:
        One of STRONG BUY, BUY, HOLD, SELL, AVOID.
    mode:
        "bg" → background hex, "text" → text hex.
    """
    is_dark = st.session_state.get("dark_mode", False)
    key = "dark" if is_dark else "light"
    colors = _SIGNAL_COLORS.get(signal.upper(), {"light": "#6B7280", "dark": "#9CA3AF"})
    return colors[key]


def score_color(score: float) -> str:
    """Return a color hex based on a 0–100 composite score."""
    if score >= 80:
        return "#10B981"
    if score >= 65:
        return "#34D399"
    if score >= 50:
        return "#F59E0B"
    if score >= 40:
        return "#EF4444"
    return "#B91C1C"


def confidence_color(confidence: float) -> str:
    """Return a color hex based on confidence percentage (75–100)."""
    if confidence >= 95:
        return _CONFIDENCE_COLORS["very_high"]
    if confidence >= 85:
        return _CONFIDENCE_COLORS["high"]
    return _CONFIDENCE_COLORS["good"]


def confidence_label(confidence: float) -> str:
    """Return a text label for a confidence level."""
    if confidence >= 95:
        return "Very High"
    if confidence >= 85:
        return "High"
    return "Good"


def card_css(extra_classes: str = "") -> str:
    """Return the CSS class string for a KešMani card."""
    return f"km-card {extra_classes}".strip()


def badge_html(text: str, color: str, text_color: str = "white") -> str:
    """
    Return raw HTML for a styled pill badge.

    Parameters
    ----------
    text:
        Badge label.
    color:
        Background color (hex or CSS color).
    text_color:
        Text color.
    """
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:9999px;'
        f'background:{color};color:{text_color};font-size:0.75rem;font-weight:600;'
        f'letter-spacing:0.05em;text-transform:uppercase;">{text}</span>'
    )


def signal_badge_html(signal: str) -> str:
    """Return a color-coded HTML badge for a trading signal."""
    css_class_map = {
        "STRONG BUY": "km-badge km-badge-strong-buy",
        "BUY": "km-badge km-badge-buy",
        "HOLD": "km-badge km-badge-hold",
        "SELL": "km-badge km-badge-sell",
        "AVOID": "km-badge km-badge-avoid",
    }
    css_class = css_class_map.get(signal.upper(), "km-badge km-badge-hold")
    return f'<span class="{css_class}">{signal}</span>'


def urgency_badge_html(urgency: str) -> str:
    """Return an HTML urgency badge."""
    css_class_map = {
        "NOW": "km-badge km-urgency-now",
        "TODAY": "km-badge km-urgency-today",
        "THIS_WEEK": "km-badge km-urgency-this-week",
        "WATCH": "km-badge km-urgency-watch",
    }
    css_class = css_class_map.get(urgency.upper(), "km-badge km-urgency-watch")
    label = urgency.replace("_", " ")
    return f'<span class="{css_class}">{label}</span>'


def render_score_bar(score: float, label: str = "") -> None:
    """Render a colored progress bar for a score (0–100)."""
    color = score_color(score)
    st.markdown(
        f"""
        <div style="margin-bottom:4px;">
            <span style="font-size:0.8rem;color:var(--text-secondary);">{label}</span>
            <span style="float:right;font-size:0.8rem;font-weight:600;color:{color};">{score:.0f}</span>
        </div>
        <div style="background:#E9ECEF;border-radius:4px;height:6px;margin-bottom:12px;">
            <div style="width:{score}%;background:{color};height:6px;border-radius:4px;"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_confidence_bar(confidence: float) -> None:
    """Render a confidence progress bar."""
    color = confidence_color(confidence)
    label = confidence_label(confidence)
    pct = min(confidence, 100.0)
    st.markdown(
        f"""
        <div style="margin-bottom:4px;">
            <span style="font-size:0.8rem;">Confidence</span>
            <span style="float:right;font-size:0.8rem;font-weight:600;color:{color};">{pct:.0f}% — {label}</span>
        </div>
        <div style="background:#E9ECEF;border-radius:4px;height:8px;margin-bottom:12px;">
            <div style="width:{pct}%;background:{color};height:8px;border-radius:4px;"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def market_status_html(is_open: bool) -> str:
    """Return HTML for the market status indicator."""
    if is_open:
        return (
            '<span style="display:inline-flex;align-items:center;gap:6px;">'
            '<span style="width:10px;height:10px;border-radius:50%;background:#10B981;'
            'display:inline-block;animation:pulse 2s infinite;"></span>'
            '<span style="color:#10B981;font-weight:600;font-size:0.85rem;">Market Open</span>'
            '</span>'
        )
    return (
        '<span style="display:inline-flex;align-items:center;gap:6px;">'
        '<span style="width:10px;height:10px;border-radius:50%;background:#EF4444;'
        'display:inline-block;"></span>'
        '<span style="color:#EF4444;font-weight:600;font-size:0.85rem;">Market Closed</span>'
        '</span>'
    )


def data_quality_dot(quality: int) -> str:
    """Return an HTML colored dot for data quality score (0–100)."""
    if quality >= 80:
        color, label = "#10B981", "Good"
    elif quality >= 60:
        color, label = "#F59E0B", "Fair"
    else:
        color, label = "#EF4444", "Poor"
    return (
        f'<span style="display:inline-flex;align-items:center;gap:4px;">'
        f'<span style="width:8px;height:8px;border-radius:50%;background:{color};display:inline-block;"></span>'
        f'<span style="font-size:0.8rem;color:{color};">{label} ({quality})</span>'
        f'</span>'
    )
