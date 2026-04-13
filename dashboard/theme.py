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

# Signal color mapping — standard palette
_SIGNAL_COLORS = {
    "STRONG BUY": {"light": "#10B981", "dark": "#10B981"},
    "BUY": {"light": "#34D399", "dark": "#34D399"},
    "HOLD": {"light": "#6B7280", "dark": "#9CA3AF"},
    "SELL": {"light": "#EF4444", "dark": "#EF4444"},
    "AVOID": {"light": "#B91C1C", "dark": "#DC2626"},
}

# Color-blind friendly palette (blue/orange — deuteranopia-safe)
_CB_SIGNAL_COLORS = {
    "STRONG BUY": {"light": "#0075DC", "dark": "#3B9EF5"},
    "BUY": {"light": "#4DA6FF", "dark": "#74BAFF"},
    "HOLD": {"light": "#6B7280", "dark": "#9CA3AF"},
    "SELL": {"light": "#FF6F20", "dark": "#FF8C47"},
    "AVOID": {"light": "#C04000", "dark": "#E05010"},
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

    /* ── Mobile responsive sidebar ── */
    @media (max-width: 768px) {{
        [data-testid="stSidebar"] {{
            width: 100% !important;
        }}
        [data-testid="stSidebar"] .stSelectbox,
        [data-testid="stSidebar"] .stNumberInput,
        [data-testid="stSidebar"] .stSlider {{
            width: 100% !important;
        }}
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

    /* ── Hero card — the most important element on each page ── */
    .km-hero-card {{
        background: {t["surface"]};
        border: 2px solid {t["accent"]};
        border-radius: 16px;
        padding: 28px 32px;
        margin-bottom: 20px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        text-align: center;
    }}

    /* ── Explainer / "What does this mean?" box ── */
    .km-explainer {{
        background: #EFF6FF;
        border: 1px solid #BFDBFE;
        border-left: 4px solid #3B82F6;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 16px;
        color: #1E3A5F;
    }}

    /* ── Numbered step guide ── */
    .km-step {{
        background: {t["surface"]};
        border: 1px solid {t["border"]};
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 10px;
        display: flex;
        align-items: flex-start;
        gap: 14px;
    }}
    .km-step-number {{
        background: {t["accent"]};
        color: white;
        border-radius: 50%;
        width: 32px;
        height: 32px;
        min-width: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 1rem;
    }}
    .km-step-body {{
        flex: 1;
    }}

    /* ── Beginner tip ── */
    .km-beginner-tip {{
        background: #FFFBEB;
        border: 1px solid #FDE68A;
        border-left: 4px solid #F59E0B;
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 12px;
        font-style: italic;
        color: #78350F;
    }}

    /* ── Inline colored highlights ── */
    .km-highlight-green {{
        color: #10B981;
        font-weight: 600;
    }}
    .km-highlight-red {{
        color: #EF4444;
        font-weight: 600;
    }}
    .km-highlight-yellow {{
        color: #F59E0B;
        font-weight: 600;
    }}

    /* ── Action needed card ── */
    .km-action-card {{
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 12px;
        border: 2px solid;
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
        padding: 6px 16px;
        border-radius: 9999px;
        font-size: 0.9rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }}
    .km-badge-strong-buy {{ background: #10B981; color: white; }}
    .km-badge-buy {{ background: #34D399; color: white; }}
    .km-badge-hold {{ background: #6B7280; color: white; }}
    .km-badge-sell {{ background: #EF4444; color: white; }}
    .km-badge-avoid {{ background: #B91C1C; color: white; }}

    /* ── Signal tag block (badge + subtitle) ── */
    .km-signal-tag {{
        display: inline-block;
        text-align: center;
    }}
    .km-signal-subtitle {{
        display: block;
        font-size: 0.75rem;
        color: {t["text_secondary"]};
        margin-top: 4px;
        font-style: italic;
    }}

    /* ── Urgency badges — only NOW pulses ── */
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
    is_cb = st.session_state.get("colorblind_mode", False)
    key = "dark" if is_dark else "light"
    palette = _CB_SIGNAL_COLORS if is_cb else _SIGNAL_COLORS
    colors = palette.get(signal.upper(), {"light": "#6B7280", "dark": "#9CA3AF"})
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
    """Return a color-coded HTML badge for a trading signal, with a plain-English subtitle."""
    css_class_map = {
        "STRONG BUY": "km-badge km-badge-strong-buy",
        "BUY": "km-badge km-badge-buy",
        "HOLD": "km-badge km-badge-hold",
        "SELL": "km-badge km-badge-sell",
        "AVOID": "km-badge km-badge-avoid",
    }
    css_class = css_class_map.get(signal.upper(), "km-badge km-badge-hold")
    subtitle = plain_english_signal(signal)
    return (
        f'<span class="km-signal-tag">'
        f'<span class="{css_class}">{signal}</span>'
        f'<span class="km-signal-subtitle">{subtitle}</span>'
        f'</span>'
    )


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


# ---------------------------------------------------------------------------
# Plain-English helper functions
# ---------------------------------------------------------------------------

def plain_english_signal(signal: str) -> str:
    """Return a beginner-friendly description of a trading signal."""
    descriptions = {
        "STRONG BUY": "The system is very confident this stock is heading up 🚀",
        "BUY": "Looks good — the system likes this stock 👍",
        "HOLD": "Wait and see — not the right moment to act ⏳",
        "SELL": "Consider selling if you own this stock 📉",
        "AVOID": "Skip this one — too risky right now 🚫",
    }
    return descriptions.get(signal.upper(), "Signal unavailable")


def plain_english_regime(regime: str) -> str:
    """Return a beginner-friendly description of the market regime."""
    descriptions = {
        "BULLISH": "The overall market is healthy and going up. Good conditions for buying stocks.",
        "BEARISH": "The market is declining. Be cautious — consider smaller positions or waiting.",
        "NEUTRAL": "The market is going sideways. Mixed signals — be selective.",
        "VOLATILE": "The market is choppy and unpredictable. Higher risk right now — use smaller positions.",
    }
    return descriptions.get(regime.upper(), "Market regime data unavailable.")


def plain_english_regime_action(regime: str) -> str:
    """Return plain-English action guidance for a given market regime."""
    actions = {
        "BULLISH": "✅ You can look for buying opportunities with normal position sizes.",
        "BEARISH": "⚠️ Be careful. Consider using smaller position sizes or waiting for conditions to improve.",
        "NEUTRAL": "🤔 Be selective. Only take the highest-confidence setups.",
        "VOLATILE": "🛡️ Use smaller positions than usual. The market is unpredictable right now.",
    }
    return actions.get(regime.upper(), "Review market conditions before trading.")


def jargon_tooltip(term: str) -> str:
    """Return a plain-English explanation of a trading term, suitable for a help= tooltip."""
    tooltips = {
        "RSI": (
            "RSI (Relative Strength Index): A number from 0–100 showing momentum. "
            "Above 70 = stock may be overbought (could fall soon). "
            "Below 30 = stock may be oversold (could rise soon). 50 is neutral."
        ),
        "MACD": (
            "MACD: A momentum indicator that shows when a stock's trend is getting stronger or weaker. "
            "When the MACD line crosses above the signal line, it's a bullish sign."
        ),
        "Bollinger Bands": (
            "Bollinger Bands: Lines drawn above and below a stock's price. "
            "When the price touches the upper band, the stock may be overbought. "
            "When it touches the lower band, it may be oversold."
        ),
        "composite score": (
            "Composite Score (0–100): KešMani's overall rating for a stock. "
            "Think of it like a school grade — 80+ is excellent, 65–79 is good, below 50 is weak."
        ),
        "stop loss": (
            "Stop Loss: A price where you automatically sell to limit your loss. "
            "Example: if you buy at $100 and set a stop loss at $95, you sell if the price drops to $95, "
            "limiting your loss to $5 per share."
        ),
        "target": (
            "Profit Target: The price where you plan to sell and take your profit. "
            "Setting a target helps you stick to your plan instead of getting greedy."
        ),
        "R:R ratio": (
            "Reward-to-Risk Ratio: How much you could earn vs. how much you could lose. "
            "A 2:1 ratio means for every $1 you risk, you could make $2. "
            "Look for trades with at least 2:1 or better."
        ),
        "portfolio heat": (
            "Portfolio Heat: The total percentage of your account you could lose if all your stop losses "
            "trigger at the same time. Keep this below 6–8% to protect your account."
        ),
        "portfolio_heat": (
            "Portfolio Heat: The total percentage of your account you could lose if all your stop losses "
            "trigger at the same time. Keep this below 6–8% to protect your account."
        ),
    }
    return tooltips.get(term, f"Plain-English explanation for '{term}' coming soon.")
