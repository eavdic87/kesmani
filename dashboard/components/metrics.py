"""
KPI metric card components for the KešMani dashboard.
"""

import streamlit as st
from src.utils.helpers import fmt_currency, fmt_pct, trend_color


def market_regime_card(regime: str) -> None:
    """Display a prominent market regime indicator."""
    color = {"BULLISH": "#00cc44", "BEARISH": "#cc0000", "NEUTRAL": "#ffcc00"}.get(regime, "#888")
    emoji = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "🟡"}.get(regime, "⬜")
    st.markdown(
        f"""
        <div style="background:#161b22;border:1px solid {color};border-radius:10px;
                    padding:20px;text-align:center;margin-bottom:16px;">
          <div style="font-size:2em;">{emoji}</div>
          <div style="color:{color};font-size:1.6em;font-weight:bold;">{regime}</div>
          <div style="color:#8b949e;font-size:0.9em;">Market Regime</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def benchmark_card(snapshot: dict) -> None:
    """Display a single benchmark ETF KPI card."""
    ticker = snapshot.get("ticker", "")
    price = fmt_currency(snapshot.get("current_price"))
    chg = snapshot.get("day_change_pct", 0.0)
    chg_str = fmt_pct(chg)
    color = "#00cc44" if chg >= 0 else "#cc0000"
    arrow = "▲" if chg >= 0 else "▼"
    st.markdown(
        f"""
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;
                    padding:14px;text-align:center;">
          <div style="color:#8b949e;font-size:0.85em;">{ticker}</div>
          <div style="font-size:1.4em;font-weight:bold;">{price}</div>
          <div style="color:{color};font-size:1em;">{arrow} {chg_str}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def heat_gauge(heat_pct: float, max_heat_pct: float = 8.0) -> None:
    """Display a simple portfolio heat gauge."""
    ratio = min(heat_pct / max_heat_pct, 1.0)
    color = "#00cc44" if ratio < 0.5 else ("#ffcc00" if ratio < 0.8 else "#cc0000")
    within = heat_pct <= max_heat_pct
    label = "✅ Within Limit" if within else "🚨 Over Limit"
    st.markdown(
        f"""
        <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px;margin-bottom:12px;">
          <div style="color:#8b949e;font-size:0.85em;margin-bottom:6px;">Portfolio Heat</div>
          <div style="background:#30363d;border-radius:4px;height:12px;width:100%;">
            <div style="background:{color};border-radius:4px;height:12px;width:{ratio*100:.0f}%;"></div>
          </div>
          <div style="margin-top:6px;font-size:1.1em;font-weight:bold;color:{color};">
            {heat_pct:.1f}% / {max_heat_pct:.0f}%  {label}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def signal_summary_card(signal_data: dict) -> None:
    """Display the signal summary for a single ticker."""
    from src.utils.helpers import signal_color, signal_emoji

    sig = signal_data.get("signal", "HOLD")
    color = signal_color(sig)
    emoji = signal_emoji(sig)

    st.markdown(
        f"""
        <div style="background:#161b22;border:2px solid {color};border-radius:10px;padding:16px;margin-bottom:12px;">
          <div style="color:{color};font-size:1.4em;font-weight:bold;">{emoji} {sig}</div>
          <div style="color:#8b949e;font-size:0.85em;">Composite Score: {signal_data.get('composite_score', 0):.0f}/100</div>
          <hr style="border-color:#30363d;">
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:8px;">
            <div><div style="color:#8b949e;font-size:0.8em;">Entry</div>
                 <div style="font-weight:bold;">{fmt_currency(signal_data.get('entry'))}</div></div>
            <div><div style="color:#8b949e;font-size:0.8em;">Stop Loss</div>
                 <div style="font-weight:bold;color:#cc0000;">{fmt_currency(signal_data.get('stop_loss'))}</div></div>
            <div><div style="color:#8b949e;font-size:0.8em;">Target 1</div>
                 <div style="font-weight:bold;color:#00cc44;">{fmt_currency(signal_data.get('target_1'))}</div></div>
          </div>
          <div style="margin-top:8px;color:#8b949e;font-size:0.85em;">
            Target 2: {fmt_currency(signal_data.get('target_2'))} &nbsp;|&nbsp;
            R:R: {signal_data.get('rr_ratio', 'N/A')}:1 &nbsp;|&nbsp;
            Shares: {signal_data.get('position_shares', 0)} (Risk: {fmt_currency(signal_data.get('risk_amount'))})
          </div>
          <div style="margin-top:8px;color:#c9d1d9;font-size:0.85em;">{signal_data.get('reasoning', '')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
