"""
Central configuration for the Kesmani Trading Intelligence System.

All tunable parameters live here — change these to adapt the system
to your own risk tolerance, universe, and thresholds.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Stock universe
# ---------------------------------------------------------------------------
WATCHLIST: dict[str, list[str]] = {
    "mega_cap": ["NVDA", "META", "AMZN", "MSFT", "AAPL", "GOOGL"],
    "semiconductors": ["SMH", "AMD", "AVGO"],
    "financials": ["JPM", "GS"],
    "energy": ["XLE", "CVX"],
    "growth": ["PLTR", "UBER", "CRWD"],
    "benchmarks": ["SPY", "QQQ", "IWM"],
}

ALL_TICKERS: list[str] = [t for group in WATCHLIST.values() for t in group]
BENCHMARK_TICKERS: list[str] = WATCHLIST["benchmarks"]

# Human-readable sector labels
TICKER_SECTORS: dict[str, str] = {
    "NVDA": "Semiconductors",
    "META": "Technology",
    "AMZN": "Consumer Discretionary",
    "MSFT": "Technology",
    "AAPL": "Technology",
    "GOOGL": "Communication Services",
    "SMH": "Semiconductors ETF",
    "AMD": "Semiconductors",
    "AVGO": "Semiconductors",
    "JPM": "Financials",
    "GS": "Financials",
    "XLE": "Energy ETF",
    "CVX": "Energy",
    "PLTR": "Technology",
    "UBER": "Technology",
    "CRWD": "Cybersecurity",
    "SPY": "Benchmark ETF",
    "QQQ": "Benchmark ETF",
    "IWM": "Benchmark ETF",
}

# ---------------------------------------------------------------------------
# Portfolio settings
# ---------------------------------------------------------------------------
PORTFOLIO_SETTINGS: dict[str, float | int] = {
    "starting_capital": float(os.getenv("STARTING_CAPITAL", "1000")),
    "max_risk_per_trade": 0.02,   # 2 % of total capital per trade
    "max_portfolio_heat": 0.08,   # 8 % maximum aggregate open risk
    "default_rr_ratio": 2.0,      # minimum reward-to-risk ratio for setups
}

# ---------------------------------------------------------------------------
# Technical indicator settings
# ---------------------------------------------------------------------------
TECHNICAL_SETTINGS: dict[str, int | list[int]] = {
    "rsi_period": 14,
    "rsi_overbought": 70,
    "rsi_oversold": 30,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "bb_period": 20,
    "bb_std": 2,
    "sma_periods": [20, 50, 100, 200],
    "ema_periods": [9, 21],
    "atr_period": 14,
    "volume_avg_period": 20,
}

# ---------------------------------------------------------------------------
# Screener weights (must sum to 1.0)
# ---------------------------------------------------------------------------
SCREENER_WEIGHTS: dict[str, float] = {
    "trend": 0.25,
    "momentum": 0.25,
    "volume": 0.20,
    "fundamental": 0.15,
    "relative_strength": 0.15,
}

# ---------------------------------------------------------------------------
# Signal thresholds
# ---------------------------------------------------------------------------
SIGNAL_THRESHOLDS: dict[str, float] = {
    "strong_buy_min_score": 80.0,
    "buy_min_score": 65.0,
    "avoid_max_score": 40.0,
    "strong_buy_max_rsi": 60.0,   # not overbought on a strong-buy
    "sell_rsi": 75.0,
}

# ---------------------------------------------------------------------------
# Data fetch settings
# ---------------------------------------------------------------------------
DATA_SETTINGS: dict[str, str | int] = {
    "default_period": "1y",        # default lookback for technical analysis
    "long_period": "5y",           # long-term fundamental lookback
    "cache_ttl_minutes": 60,       # file-cache TTL in minutes
    "earnings_warning_days": 7,    # flag upcoming earnings within N days
}
