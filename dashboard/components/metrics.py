"""
KPI metric card components for the KešMani dashboard.
"""

import streamlit as st
from src.utils.helpers import fmt_currency, fmt_pct, trend_color


def market_regime_card(regime: str) -> None:
    """Display a prominent market regime indicator with plain-English explanation."""
    from dashboard.theme import plain_english_regime, plain_english_regime_action, get_theme
    t = get_theme()
    color = {"BULLISH": "#10B981", "BEARISH": "#EF4444", "VOLATILE": "#F59E0B", "NEUTRAL": "#6B7280"}.get(regime, "#888")
    emoji = {"BULLISH": "📈", "BEARISH": "📉", "VOLATILE": "⚡", "NEUTRAL": "➡️"}.get(regime, "⬜")
    description = plain_english_regime(regime)
    action = plain_english_regime_action(regime)
    st.markdown(
        f"""
        <div style="background:{color}18;border:2px solid {color};border-radius:14px;
                    padding:24px;text-align:center;margin-bottom:16px;">
          <div style="font-size:2.5rem;margin-bottom:6px;">{emoji}</div>
          <div style="color:{color};font-size:2rem;font-weight:800;margin-bottom:4px;">{regime}</div>
          <div style="font-size:0.85rem;opacity:0.6;margin-bottom:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;">Current Market Regime</div>
          <div style="font-size:1rem;max-width:520px;margin:0 auto 10px auto;">{description}</div>
          <div style="font-size:0.95rem;font-weight:600;max-width:520px;margin:0 auto;padding:10px 16px;background:{color}20;border-radius:8px;">{action}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def benchmark_card(snapshot: dict) -> None:
    """Display a single benchmark ETF KPI card with plain-English label."""
    _DESCRIPTIONS = {
        "SPY": "S&P 500 — Top 500 US companies",
        "QQQ": "Nasdaq — Tech-heavy index",
        "IWM": "Russell 2000 — Small companies",
    }
    ticker = snapshot.get("ticker", "")
    description = _DESCRIPTIONS.get(ticker, ticker)
    price = fmt_currency(snapshot.get("current_price"))
    chg = snapshot.get("day_change_pct", 0.0)
    chg_str = fmt_pct(chg)
    color = "#10B981" if chg >= 0 else "#EF4444"
    arrow = "▲" if chg >= 0 else "▼"
    score = snapshot.get("composite_score", snapshot.get("score", 0))
    from dashboard.theme import get_theme, score_color
    t = get_theme()
    sc = score_color(score) if score else "#6B7280"
    st.markdown(
        f"""
        <div style="background:{t['surface']};border:1px solid {t['border']};border-radius:10px;
                    padding:16px;text-align:center;">
          <div style="font-size:1.1rem;font-weight:700;">{ticker}</div>
          <div style="font-size:0.78rem;opacity:0.65;margin-bottom:8px;">{description}</div>
          <div style="font-size:1.6rem;font-weight:800;margin-bottom:2px;">{price}</div>
          <div style="color:{color};font-size:1rem;font-weight:600;">{arrow} {chg_str} today</div>
          {f'<div style="margin-top:8px;font-size:0.82rem;color:{sc};font-weight:600;">Health Score: {score:.0f}/100</div>' if score else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def heat_gauge(heat_pct: float, max_heat_pct: float = 8.0) -> None:
    """Display portfolio heat gauge with plain-English risk level labels."""
    ratio = min(heat_pct / max_heat_pct, 1.0)
    if heat_pct <= 4.0:
        color = "#10B981"
        risk_label = "🟢 Low Risk — you have room to add more positions"
    elif heat_pct <= 6.0:
        color = "#34D399"
        risk_label = "🟡 Moderate Risk — be selective about new trades"
    elif heat_pct <= 8.0:
        color = "#F59E0B"
        risk_label = "🟠 High Risk — consider not adding more until some positions close"
    else:
        color = "#EF4444"
        risk_label = "🔴 Maximum Risk Reached — do not open new positions"

    within = heat_pct <= max_heat_pct
    from dashboard.theme import get_theme
    t = get_theme()
    st.markdown(
        f"""
        <div style="background:{t['surface']};border:1px solid {t['border']};border-radius:10px;padding:16px;margin-bottom:12px;">
          <div style="font-size:0.85rem;font-weight:600;margin-bottom:2px;">How much risk you're carrying right now</div>
          <div style="font-size:0.75rem;opacity:0.65;margin-bottom:10px;">Total % of your account at risk across all open positions</div>
          <div style="background:{t['border']};border-radius:4px;height:14px;width:100%;margin-bottom:8px;">
            <div style="background:{color};border-radius:4px;height:14px;width:{ratio*100:.0f}%;"></div>
          </div>
          <div style="font-size:1.15rem;font-weight:700;color:{color};margin-bottom:4px;">{heat_pct:.1f}% / {max_heat_pct:.0f}% max</div>
          <div style="font-size:0.88rem;">{risk_label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def signal_summary_card(signal_data: dict) -> None:
    """Display the signal summary for a single ticker."""
    from src.utils.helpers import signal_color, signal_emoji
    from dashboard.theme import plain_english_signal

    sig = signal_data.get("signal", "HOLD")
    color = signal_color(sig)
    emoji = signal_emoji(sig)
    plain = plain_english_signal(sig)

    st.markdown(
        f"""
        <div style="border:2px solid {color};border-radius:10px;padding:16px;margin-bottom:12px;">
          <div style="color:{color};font-size:1.4em;font-weight:bold;">{emoji} {sig}</div>
          <div style="font-size:0.85em;font-style:italic;margin-bottom:8px;">{plain}</div>
          <div style="font-size:0.85em;opacity:0.7;">Health Score: {signal_data.get('composite_score', 0):.0f}/100</div>
          <hr style="opacity:0.2;margin:10px 0;">
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:8px;">
            <div><div style="font-size:0.78em;opacity:0.7;">Buy at</div>
                 <div style="font-weight:bold;">{fmt_currency(signal_data.get('entry'))}</div></div>
            <div><div style="font-size:0.78em;opacity:0.7;">Sell if drops to</div>
                 <div style="font-weight:bold;color:#EF4444;">{fmt_currency(signal_data.get('stop_loss'))}</div></div>
            <div><div style="font-size:0.78em;opacity:0.7;">First profit target</div>
                 <div style="font-weight:bold;color:#10B981;">{fmt_currency(signal_data.get('target_1'))}</div></div>
          </div>
          <div style="margin-top:8px;font-size:0.85em;opacity:0.7;">
            Full target: {fmt_currency(signal_data.get('target_2'))} &nbsp;|&nbsp;
            Reward vs. Risk: {signal_data.get('rr_ratio', 'N/A')}:1 &nbsp;|&nbsp;
            Shares: {signal_data.get('position_shares', 0)} (Max loss: {fmt_currency(signal_data.get('risk_amount'))})
          </div>
          <div style="margin-top:8px;font-size:0.85em;">{signal_data.get('reasoning', '')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_rr_explainer(rr_ratio: float = 2.0) -> None:
    """Visually show what a given Reward:Risk ratio means with a simple bar diagram."""
    risk_width = 30
    reward_width = int(risk_width * rr_ratio)
    st.markdown(
        f"""
        <div style="margin:8px 0 12px 0;">
          <div style="font-size:0.85rem;font-weight:600;margin-bottom:6px;">
            What does {rr_ratio:.1f}:1 Reward vs. Risk mean?
          </div>
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
            <div style="width:{risk_width}px;height:16px;background:#EF4444;border-radius:4px;"></div>
            <span style="font-size:0.8rem;">Your risk — what you could lose ($1 unit)</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px;">
            <div style="width:{reward_width}px;height:16px;background:#10B981;border-radius:4px;"></div>
            <span style="font-size:0.8rem;">Your potential reward (${rr_ratio:.1f} units)</span>
          </div>
          <div style="font-size:0.78rem;opacity:0.7;margin-top:6px;">
            For every $1 you risk, you could make ${rr_ratio:.1f}. Aim for 2:1 or better.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
