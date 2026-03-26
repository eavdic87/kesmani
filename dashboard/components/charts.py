"""
Reusable chart components for the Kesmani dashboard.

All functions return Plotly figures configured for the dark trading theme.
"""

from typing import Optional
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
# Shared theme
# ---------------------------------------------------------------------------

DARK_LAYOUT = dict(
    paper_bgcolor="#0d1117",
    plot_bgcolor="#0d1117",
    font=dict(color="#c9d1d9"),
    xaxis=dict(gridcolor="#30363d", showgrid=True),
    yaxis=dict(gridcolor="#30363d", showgrid=True),
    legend=dict(bgcolor="#161b22", bordercolor="#30363d"),
    margin=dict(l=50, r=20, t=40, b=40),
)


def candlestick_chart(
    df: pd.DataFrame,
    ticker: str,
    show_sma: bool = True,
    show_ema: bool = True,
    show_bollinger: bool = True,
    show_volume: bool = True,
    show_rsi: bool = True,
    show_macd: bool = True,
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

    Returns
    -------
    Plotly Figure with subplots: [OHLCV + overlays, Volume, RSI, MACD].
    """
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

    # --- Candlestick ---
    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=close,
            name=ticker,
            increasing_line_color="#00cc44",
            decreasing_line_color="#cc0000",
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
            "#00cc44" if c >= o else "#cc0000"
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
        fig.add_hline(y=70, line_dash="dash", line_color="#cc0000", line_width=1, row=current_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#00cc44", line_width=1, row=current_row, col=1)
        fig.update_yaxes(title_text="RSI", range=[0, 100], row=current_row, col=1)

    # --- MACD ---
    if show_macd:
        current_row += 1
        macd_data = calculate_macd(close)
        macd_line = macd_data["macd"]
        signal_line = macd_data["signal"]
        histogram = macd_data["histogram"]
        hist_colors = ["#00cc44" if v >= 0 else "#cc0000" for v in histogram]
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
    fig.update_layout(
        title=f"{ticker} — Price Chart",
        xaxis_rangeslider_visible=False,
        **DARK_LAYOUT,
        height=700,
    )

    return fig


def sparkline(series: pd.Series, color: str = "#58a6ff") -> go.Figure:
    """Create a compact sparkline figure."""
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
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker=dict(line=dict(color="#0d1117", width=2)),
        )
    )
    fig.update_layout(title="Portfolio Allocation", **DARK_LAYOUT, height=350)
    return fig
