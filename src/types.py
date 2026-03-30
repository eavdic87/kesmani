"""
TypedDict definitions for KešMani.

Provides type-safe return types for the main data layer functions,
improving IDE auto-completion and static analysis.
"""

from typing import Optional
try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict  # type: ignore[assignment]


class IndicatorResult(TypedDict, total=False):
    current_price: float
    sma_20: Optional[float]
    sma_50: Optional[float]
    sma_100: Optional[float]
    sma_200: Optional[float]
    ema_9: Optional[float]
    ema_21: Optional[float]
    rsi: Optional[float]
    rsi_overbought: bool
    rsi_oversold: bool
    stoch_rsi_k: Optional[float]
    stoch_rsi_d: Optional[float]
    stoch_rsi_overbought: bool
    stoch_rsi_oversold: bool
    macd: float
    macd_signal: float
    macd_histogram: float
    macd_crossover: str
    bb_upper: Optional[float]
    bb_lower: Optional[float]
    bb_percent_b: Optional[float]
    bb_squeeze: bool
    atr: Optional[float]
    volume_ratio: float
    obv: Optional[float]
    support: Optional[float]
    resistance: Optional[float]
    trend: str


class PriceSummary(TypedDict, total=False):
    ticker: str
    current_price: float
    day_change_pct: float
    week52_high: float
    week52_low: float
    pct_from_52w_high: float


class PortfolioSummary(TypedDict, total=False):
    starting_capital: float
    cash: float
    positions: list
    total_invested: float
    total_market_value: float
    total_unrealized_pnl: float
    total_unrealized_pnl_pct: float
    total_realized_pnl: float
    net_worth: float
    closed_trades: list
    last_updated: str
