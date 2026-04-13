"""
Reusable card components for the KešMani dashboard.

Provides a consistent ``render_card`` helper that replaces raw
``st.markdown(unsafe_allow_html=True)`` calls for cards and heatmap cells.
"""

import streamlit as st


def render_card(
    title: str,
    body: str,
    color: str | None = None,
    border_color: str | None = None,
    compact: bool = False,
) -> None:
    """
    Render a styled KešMani card using native Streamlit containers.

    Parameters
    ----------
    title:
        Card heading (markdown-safe text).
    body:
        Card body text (markdown-safe text).
    color:
        Optional background accent color (hex or CSS color string).
        When provided a left border in this color is added.
    border_color:
        Optional explicit border color.  Falls back to ``color`` when not set.
    compact:
        Use the compact card CSS class (less padding).
    """
    css_class = "km-card-compact" if compact else "km-card"
    border = f"border-left: 4px solid {border_color or color};" if (color or border_color) else ""
    with st.container():
        st.markdown(
            f"""
            <div class="{css_class}" style="{border}">
                <h4 style="margin-top:0;margin-bottom:6px;">{title}</h4>
                <p style="margin:0;">{body}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_metric_card(
    label: str,
    value: str,
    delta: str | None = None,
    delta_positive: bool = True,
) -> None:
    """
    Render a simple metric card with label, value, and optional delta.

    Uses ``st.metric`` so it integrates with Streamlit's native theming.

    Parameters
    ----------
    label:
        Metric label.
    value:
        Metric value string.
    delta:
        Optional delta string (e.g. "+3.2%").
    delta_positive:
        Whether a positive delta is good (green) or bad (red).
    """
    st.metric(
        label=label,
        value=value,
        delta=delta,
        delta_color="normal" if delta_positive else "inverse",
    )


def render_alert_badge(alert_type: str, ticker: str) -> str:
    """
    Return an HTML pill badge for a position alert.

    Parameters
    ----------
    alert_type:
        "STOP", "TARGET_1", or "TARGET_2".
    ticker:
        Ticker symbol to display in the badge.

    Returns
    -------
    HTML string for the badge.
    """
    configs = {
        "STOP": ("🔴 AT STOP", "#EF4444"),
        "TARGET_1": ("🟢 TARGET 1 HIT", "#10B981"),
        "TARGET_2": ("🟢 TARGET 2 HIT", "#059669"),
    }
    label, color = configs.get(alert_type, ("⚠️ ALERT", "#F59E0B"))
    return (
        f'<span style="display:inline-block;padding:4px 12px;border-radius:9999px;'
        f'background:{color};color:white;font-size:0.8rem;font-weight:700;'
        f'letter-spacing:0.05em;">{ticker}: {label}</span>'
    )


def render_explainer_card(title: str, body: str) -> None:
    """Render a soft blue/teal 'What does this mean?' information box."""
    st.markdown(
        f"""
        <div class="km-explainer">
            <strong>📖 {title}</strong>
            <div style="margin-top:8px;">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_card(steps: list[str], title: str = "How to do this") -> None:
    """Render a numbered step-by-step guide card."""
    steps_html = ""
    for i, step in enumerate(steps, 1):
        steps_html += (
            f'<div class="km-step">'
            f'<div class="km-step-number">{i}</div>'
            f'<div class="km-step-body">{step}</div>'
            f'</div>'
        )
    st.markdown(
        f'<div style="margin-bottom:8px;"><strong>{title}</strong></div>{steps_html}',
        unsafe_allow_html=True,
    )


def render_beginner_tip(tip: str) -> None:
    """Render a soft yellow beginner tip box."""
    st.markdown(
        f'<div class="km-beginner-tip">💡 <strong>Beginner tip:</strong> {tip}</div>',
        unsafe_allow_html=True,
    )


def render_hero_card(title: str, subtitle: str, color: str, emoji: str = "") -> None:
    """Render the dominant hero card for the most important element on a page."""
    st.markdown(
        f"""
        <div class="km-hero-card" style="border-color:{color};">
            <div style="font-size:2.5rem;margin-bottom:8px;">{emoji}</div>
            <div style="font-size:1.8rem;font-weight:800;color:{color};margin-bottom:6px;">{title}</div>
            <div style="font-size:1rem;opacity:0.8;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_action_needed_card(
    ticker: str,
    message: str,
    action: str,
    color: str = "#EF4444",
) -> None:
    """Render an urgent action-required card for portfolio alerts."""
    bg = color + "15"
    st.markdown(
        f"""
        <div class="km-action-card" style="background:{bg};border-color:{color};">
            <div style="color:{color};font-size:1.1rem;font-weight:700;margin-bottom:4px;">
                ⚠️ Action Needed: <strong>{ticker}</strong>
            </div>
            <div style="margin-bottom:6px;">{message}</div>
            <div style="font-size:0.9rem;font-style:italic;color:{color};">{action}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

