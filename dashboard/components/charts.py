"""
Reusable chart components for the KešMani dashboard.

All functions return Plotly figures.  Charts automatically adapt their
color theme to the active Streamlit dark/light mode via ``get_chart_layout()``.
"""

from typing import Optional
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.analysis.technical import (
    calculate_sma,
    calculate_ema,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
)


# ---------------------------------------------------------------------------
# Theme-aware layout
# ---------------------------------------------------------------------------

_DARK_COLORS = dict(
    paper_bgcolor="#0d1117",
    plot_bgcolor="#0d1117",
    font_color="#c9d1d9",
    grid_color="#30363d",
    legend_bgcolor="#161b22",
    legend_bordercolor="#30363d",
    candle_up="#00cc44",
    candle_down="#cc0000",
)

_LIGHT_COLORS = dict(
    paper_bgcolor="#FFFFFF",
    plot_bgcolor="#F8F9FA",
    font_color="#212529",
    grid_color="#DEE2E6",
    legend_bgcolor="#F8F9FA",
    legend_bordercolor="#DEE2E6",
    candle_up="#10B981",
    candle_down="#EF4444",
)

# Keep DARK_LAYOUT for backward compatibility
DARK_LAYOUT = dict(
    paper_bgcolor=_DARK_COLORS["paper_bgcolor"],
    plot_bgcolor=_DARK_COLORS["plot_bgcolor"],
    font=dict(color=_DARK_COLORS["font_color"]),
    xaxis=dict(gridcolor=_DARK_COLORS["grid_color"], showgrid=True),
    yaxis=dict(gridcolor=_DARK_COLORS["grid_color"], showgrid=True),
    legend=dict(bgcolor=_DARK_COLORS["legend_bgcolor"], bordercolor=_DARK_COLORS["legend_bordercolor"]),
    margin=dict(l=50, r=20, t=40, b=40),
)


def get_chart_layout() -> dict:
    """
    Return a Plotly layout dict that matches the current Streamlit theme.

    Uses dark colors when ``st.session_state.dark_mode`` is True.
    """
    is_dark = st.session_state.get("dark_mode", False)
    c = _DARK_COLORS if is_dark else _LIGHT_COLORS
    return dict(
        paper_bgcolor=c["paper_bgcolor"],
        plot_bgcolor=c["plot_bgcolor"],
        font=dict(color=c["font_color"]),
        xaxis=dict(gridcolor=c["grid_color"], showgrid=True),
        yaxis=dict(gridcolor=c["grid_color"], showgrid=True),
        legend=dict(bgcolor=c["legend_bgcolor"], bordercolor=c["legend_bordercolor"]),
        margin=dict(l=50, r=20, t=40, b=40),
    )


def _candle_colors() -> tuple[str, str]:
    """Return (up_color, down_color) for the active theme."""
    is_dark = st.session_state.get("dark_mode", False)
    c = _DARK_COLORS if is_dark else _LIGHT_COLORS
    return c["candle_up"], c["candle_down"]


# ---------------------------------------------------------------------------
# Timeframe slicing
# ---------------------------------------------------------------------------

_TIMEFRAME_BARS: dict[str, int] = {
    "1W": 5,
    "1M": 21,
    "3M": 63,
    "6M": 126,
    "1Y": 252,
    "All": 0,
}


def slice_dataframe(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    Slice a DataFrame to the last N bars for a given timeframe label.

    Parameters
    ----------
    df:
        Full OHLCV DataFrame.
    timeframe:
        One of "1W", "1M", "3M", "6M", "1Y", "All".

    Returns
    -------
    Sliced DataFrame (or the full DataFrame when timeframe=="All").
    """
    bars = _TIMEFRAME_BARS.get(timeframe, 0)
    if bars == 0 or len(df) <= bars:
        return df
    return df.tail(bars)


def candlestick_chart(
    df: pd.DataFrame,
    ticker: str,
    show_sma: bool = True,
    show_ema: bool = True,
    show_bollinger: bool = True,
    show_volume: bool = True,
    show_rsi: bool = True,
    show_macd: bool = True,
    timeframe: str = "All",
) -> go.Figure:
    """
    Build a full-featured candlestick chart with optional overlays.

    Parameters
    ----------
    df:
        OHLCV DataFrame with Date index.
    ticker:
        Symbol label for the chart title.
    show_sma, show_ema, show_bollinger, show_volume, show_rsi, show_macd:
        Toggle individual chart elements.
    timeframe:
        Slice data to this timeframe before charting.
        One of "1W", "1M", "3M", "6M", "1Y", "All".

    Returns
    -------
    Plotly Figure with subplots: [OHLCV + overlays, Volume, RSI, MACD].
    """
    df = slice_dataframe(df, timeframe)

    n_rows = 1 + int(show_volume) + int(show_rsi) + int(show_macd)
    row_heights = [0.5]
    if show_volume:
        row_heights.append(0.1)
    if show_rsi:
        row_heights.append(0.2)
    if show_macd:
        row_heights.append(0.2)

    specs = [[{"secondary_y": False}]] * n_rows

    fig = make_subplots(
        rows=n_rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        specs=specs,
    )

    close = df["Close"]
    dates = df.index
    current_row = 1
    up_color, down_color = _candle_colors()

    # --- Candlestick ---
    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=close,
            name=ticker,
            increasing_line_color=up_color,
            decreasing_line_color=down_color,
        ),
        row=1,
        col=1,
    )

    # --- SMAs ---
    if show_sma:
        sma_configs = [(20, "#58a6ff"), (50, "#ff7c00"), (200, "#cc00cc")]
        for period, color in sma_configs:
            sma = calculate_sma(close, period)
            fig.add_trace(
                go.Scatter(
                    x=dates, y=sma, name=f"SMA{period}", line=dict(color=color, width=1.2)
                ),
                row=1, col=1,
            )

    # --- EMAs ---
    if show_ema:
        for period, color in [(9, "#ffcc00"), (21, "#00cccc")]:
            ema = calculate_ema(close, period)
            fig.add_trace(
                go.Scatter(
                    x=dates, y=ema, name=f"EMA{period}", line=dict(color=color, width=1, dash="dot")
                ),
                row=1, col=1,
            )

    # --- Bollinger Bands ---
    if show_bollinger:
        bb = calculate_bollinger_bands(close)
        fig.add_trace(
            go.Scatter(x=dates, y=bb["upper"], name="BB Upper",
                       line=dict(color="#8b949e", width=1, dash="dash"), showlegend=False),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(x=dates, y=bb["lower"], name="BB Lower",
                       fill="tonexty", fillcolor="rgba(139,148,158,0.1)",
                       line=dict(color="#8b949e", width=1, dash="dash"), showlegend=False),
            row=1, col=1,
        )

    # --- Volume ---
    if show_volume:
        current_row += 1
        colors = [
            up_color if c >= o else down_color
            for c, o in zip(df["Close"], df["Open"])
        ]
        fig.add_trace(
            go.Bar(x=dates, y=df["Volume"], name="Volume", marker_color=colors, opacity=0.7),
            row=current_row, col=1,
        )
        fig.update_yaxes(title_text="Volume", row=current_row, col=1)

    # --- RSI ---
    if show_rsi:
        current_row += 1
        rsi = calculate_rsi(close)
        fig.add_trace(
            go.Scatter(x=dates, y=rsi, name="RSI", line=dict(color="#58a6ff", width=1.5)),
            row=current_row, col=1,
        )
        fig.add_hline(y=70, line_dash="dash", line_color=down_color, line_width=1, row=current_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color=up_color, line_width=1, row=current_row, col=1)
        fig.update_yaxes(title_text="RSI", range=[0, 100], row=current_row, col=1)

    # --- MACD ---
    if show_macd:
        current_row += 1
        macd_data = calculate_macd(close)
        macd_line = macd_data["macd"]
        signal_line = macd_data["signal"]
        histogram = macd_data["histogram"]
        hist_colors = [up_color if v >= 0 else down_color for v in histogram]
        fig.add_trace(
            go.Bar(x=dates, y=histogram, name="MACD Hist", marker_color=hist_colors, opacity=0.7),
            row=current_row, col=1,
        )
        fig.add_trace(
            go.Scatter(x=dates, y=macd_line, name="MACD", line=dict(color="#58a6ff", width=1.5)),
            row=current_row, col=1,
        )
        fig.add_trace(
            go.Scatter(x=dates, y=signal_line, name="Signal", line=dict(color="#ff7c00", width=1.5)),
            row=current_row, col=1,
        )
        fig.update_yaxes(title_text="MACD", row=current_row, col=1)

    # --- Layout ---
    layout = get_chart_layout()
    fig.update_layout(
        title=f"{ticker} — Price Chart ({timeframe})",
        xaxis_rangeslider_visible=False,
        **layout,
        height=700,
    )

    return fig


def sparkline(series: pd.Series, color: str = "#58a6ff") -> go.Figure:
    """Create a compact sparkline figure."""
    layout = get_chart_layout()
    fig = go.Figure(
        go.Scatter(
            x=list(range(len(series))),
            y=series.values,
            line=dict(color=color, width=2),
            fill="tozeroy",
            fillcolor=f"rgba(88,166,255,0.1)",
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=60,
        showlegend=False,
    )
    return fig


def portfolio_pie(positions: list[dict]) -> go.Figure:
    """Pie chart of portfolio allocation by ticker."""
    if not positions:
        return go.Figure()
    labels = [p["ticker"] for p in positions]
    values = [p.get("market_value", p.get("cost_basis", 0)) for p in positions]
    layout = get_chart_layout()
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker=dict(line=dict(color=layout["paper_bgcolor"], width=2)),
        )
    )
    fig.update_layout(title="Portfolio Allocation", **layout, height=350)
    return fig


def sector_bar_chart(sector_data: list[dict]) -> go.Figure:
    """
    Bar chart showing portfolio sector concentration.

    Parameters
    ----------
    sector_data:
        List of dicts with keys: sector, pct (percentage of portfolio value).

    Returns
    -------
    Plotly Figure.
    """
    if not sector_data:
        return go.Figure()
    layout = get_chart_layout()
    sectors = [d["sector"] for d in sector_data]
    pcts = [d["pct"] for d in sector_data]
    colors = ["#3B82F6" if p < 25 else "#F59E0B" if p < 40 else "#EF4444" for p in pcts]
    fig = go.Figure(go.Bar(x=sectors, y=pcts, marker_color=colors))
    fig.update_layout(
        title="Sector Concentration (%)",
        yaxis_title="% of Portfolio",
        **layout,
        height=300,
    )
    return fig
