"""
Central configuration for the KešMani Trading Intelligence System.

All tunable parameters live here — change these to adapt the system
to your own risk tolerance, universe, and thresholds.
"""

import os
from pathlib import Path

ACCOUNT_SIZE = float(os.getenv("ACCOUNT_SIZE", "5000"))

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

# Human-readable sector labels for the watchlist
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
# Broad market scan universe (~200+ unique tickers across all GICS sectors)
# ---------------------------------------------------------------------------
SCAN_UNIVERSE: dict[str, list[str]] = {
    "technology": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "AVGO", "CRM", "ADBE", "ORCL", "CSCO",
                   "INTC", "IBM", "NOW", "SHOP", "SQ", "SNOW", "DDOG", "NET", "PANW", "FTNT"],
    "semiconductors": ["NVDA", "AMD", "AVGO", "QCOM", "TXN", "MRVL", "KLAC", "LRCX", "AMAT", "MU",
                       "ON", "SMH"],
    "healthcare": ["UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY",
                   "AMGN", "GILD", "ISRG", "VRTX", "REGN"],
    "financials": ["JPM", "BAC", "GS", "MS", "WFC", "C", "BLK", "SCHW", "AXP", "V",
                   "MA", "PYPL", "COF", "USB"],
    "consumer_discretionary": ["AMZN", "TSLA", "HD", "NKE", "MCD", "SBUX", "TGT", "LOW", "BKNG",
                                "CMG", "LULU", "ROST", "DG"],
    "consumer_staples": ["PG", "KO", "PEP", "COST", "WMT", "PM", "MO", "CL", "GIS", "KHC",
                         "STZ", "MNST"],
    "energy": ["XOM", "CVX", "COP", "EOG", "SLB", "MPC", "PSX", "VLO", "OXY", "HAL",
               "DVN", "XLE"],
    "industrials": ["CAT", "DE", "HON", "UNP", "RTX", "BA", "LMT", "GD", "GE", "MMM",
                    "FDX", "UPS"],
    "real_estate": ["AMT", "PLD", "CCI", "SPG", "EQIX", "PSA", "DLR", "O", "WELL", "AVB",
                    "VNQ"],
    "utilities": ["NEE", "DUK", "SO", "AEP", "D", "EXC", "SRE", "XEL", "WEC", "ED", "XLU"],
    "communication_services": ["GOOGL", "META", "DIS", "NFLX", "CMCSA", "T", "VZ", "TMUS",
                                "CHTR", "EA", "TTWO"],
    "materials": ["LIN", "APD", "ECL", "SHW", "NEM", "FCX", "DOW", "DD", "NUE", "CF", "XLB"],
    "cybersecurity": ["CRWD", "PANW", "FTNT", "ZS", "S", "OKTA", "CYBR", "HACK"],
    "ai_and_cloud": ["NVDA", "MSFT", "GOOGL", "AMZN", "CRM", "NOW", "SNOW", "DDOG", "PLTR",
                     "AI", "PATH", "MDB"],
    "growth_momentum": ["PLTR", "UBER", "CRWD", "COIN", "RBLX", "ABNB", "DASH", "DKNG",
                        "AFRM", "SOFI", "HOOD"],
    "dividend_aristocrats": ["JNJ", "PG", "KO", "PEP", "MMM", "ABT", "ABBV", "T", "XOM",
                             "CVX", "IBM", "CL", "EMR", "SWK", "O"],
    "etfs": ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLI", "XLP",
             "XLY", "XLU", "XLB", "XLRE", "XLC", "SMH", "VNQ", "HACK", "ARKK", "SOXX"],
    "benchmarks": ["SPY", "QQQ", "IWM"],
}

# Deduplicated flat list of all tickers in the scan universe
def _build_full_universe(universe: dict[str, list[str]]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for tickers in universe.values():
        for t in tickers:
            if t not in seen:
                seen.add(t)
                result.append(t)
    return result

FULL_UNIVERSE: list[str] = _build_full_universe(SCAN_UNIVERSE)

# GICS sector mapping for every ticker in the scan universe
SECTOR_LABELS: dict[str, str] = {
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Communication Services",
    "META": "Communication Services", "NVDA": "Semiconductors", "AVGO": "Semiconductors",
    "CRM": "Technology", "ADBE": "Technology", "ORCL": "Technology", "CSCO": "Technology",
    "INTC": "Semiconductors", "IBM": "Technology", "NOW": "Technology", "SHOP": "Technology",
    "SQ": "Financials", "SNOW": "Technology", "DDOG": "Technology", "NET": "Technology",
    "PANW": "Cybersecurity", "FTNT": "Cybersecurity",
    # Semiconductors
    "AMD": "Semiconductors", "QCOM": "Semiconductors", "TXN": "Semiconductors",
    "MRVL": "Semiconductors", "KLAC": "Semiconductors", "LRCX": "Semiconductors",
    "AMAT": "Semiconductors", "MU": "Semiconductors", "ON": "Semiconductors",
    "SMH": "Semiconductors ETF", "SOXX": "Semiconductors ETF",
    # Healthcare
    "UNH": "Healthcare", "JNJ": "Healthcare", "LLY": "Healthcare", "PFE": "Healthcare",
    "ABBV": "Healthcare", "MRK": "Healthcare", "TMO": "Healthcare", "ABT": "Healthcare",
    "DHR": "Healthcare", "BMY": "Healthcare", "AMGN": "Healthcare", "GILD": "Healthcare",
    "ISRG": "Healthcare", "VRTX": "Healthcare", "REGN": "Healthcare",
    # Financials
    "JPM": "Financials", "BAC": "Financials", "GS": "Financials", "MS": "Financials",
    "WFC": "Financials", "C": "Financials", "BLK": "Financials", "SCHW": "Financials",
    "AXP": "Financials", "V": "Financials", "MA": "Financials", "PYPL": "Financials",
    "COF": "Financials", "USB": "Financials",
    # Consumer Discretionary
    "AMZN": "Consumer Discretionary", "TSLA": "Consumer Discretionary",
    "HD": "Consumer Discretionary", "NKE": "Consumer Discretionary",
    "MCD": "Consumer Discretionary", "SBUX": "Consumer Discretionary",
    "TGT": "Consumer Discretionary", "LOW": "Consumer Discretionary",
    "BKNG": "Consumer Discretionary", "CMG": "Consumer Discretionary",
    "LULU": "Consumer Discretionary", "ROST": "Consumer Discretionary",
    "DG": "Consumer Discretionary",
    # Consumer Staples
    "PG": "Consumer Staples", "KO": "Consumer Staples", "PEP": "Consumer Staples",
    "COST": "Consumer Staples", "WMT": "Consumer Staples", "PM": "Consumer Staples",
    "MO": "Consumer Staples", "CL": "Consumer Staples", "GIS": "Consumer Staples",
    "KHC": "Consumer Staples", "STZ": "Consumer Staples", "MNST": "Consumer Staples",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "EOG": "Energy",
    "SLB": "Energy", "MPC": "Energy", "PSX": "Energy", "VLO": "Energy",
    "OXY": "Energy", "HAL": "Energy", "DVN": "Energy",
    "XLE": "Energy ETF",
    # Industrials
    "CAT": "Industrials", "DE": "Industrials", "HON": "Industrials", "UNP": "Industrials",
    "RTX": "Industrials", "BA": "Industrials", "LMT": "Industrials", "GD": "Industrials",
    "GE": "Industrials", "MMM": "Industrials", "FDX": "Industrials", "UPS": "Industrials",
    "EMR": "Industrials", "SWK": "Industrials",
    # Real Estate
    "AMT": "Real Estate", "PLD": "Real Estate", "CCI": "Real Estate", "SPG": "Real Estate",
    "EQIX": "Real Estate", "PSA": "Real Estate", "DLR": "Real Estate", "O": "Real Estate",
    "WELL": "Real Estate", "AVB": "Real Estate",
    "VNQ": "Real Estate ETF", "XLRE": "Real Estate ETF",
    # Utilities
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities", "AEP": "Utilities",
    "D": "Utilities", "EXC": "Utilities", "SRE": "Utilities", "XEL": "Utilities",
    "WEC": "Utilities", "ED": "Utilities",
    "XLU": "Utilities ETF",
    # Communication Services
    "DIS": "Communication Services", "NFLX": "Communication Services",
    "CMCSA": "Communication Services", "T": "Communication Services",
    "VZ": "Communication Services", "TMUS": "Communication Services",
    "CHTR": "Communication Services", "EA": "Communication Services",
    "TTWO": "Communication Services",
    # Materials
    "LIN": "Materials", "APD": "Materials", "ECL": "Materials", "SHW": "Materials",
    "NEM": "Materials", "FCX": "Materials", "DOW": "Materials", "DD": "Materials",
    "NUE": "Materials", "CF": "Materials",
    "XLB": "Materials ETF",
    # Cybersecurity
    "CRWD": "Cybersecurity", "ZS": "Cybersecurity", "S": "Cybersecurity",
    "OKTA": "Cybersecurity", "CYBR": "Cybersecurity",
    "HACK": "Cybersecurity ETF",
    # AI / Cloud / Growth
    "AI": "AI & Cloud", "PATH": "AI & Cloud", "MDB": "Technology",
    "PLTR": "AI & Cloud", "UBER": "Growth", "COIN": "Financials",
    "RBLX": "Growth", "ABNB": "Consumer Discretionary", "DASH": "Growth",
    "DKNG": "Growth", "AFRM": "Financials", "SOFI": "Financials", "HOOD": "Financials",
    # Broad ETFs / Benchmarks
    "SPY": "Benchmark ETF", "QQQ": "Benchmark ETF", "IWM": "Benchmark ETF",
    "DIA": "Benchmark ETF", "ARKK": "Growth ETF",
    "XLK": "Technology ETF", "XLF": "Financials ETF", "XLV": "Healthcare ETF",
    "XLI": "Industrials ETF", "XLP": "Consumer Staples ETF", "XLY": "Consumer Discretionary ETF",
    "XLC": "Communication Services ETF",
}

# Mega-cap stocks where MARKET orders are acceptable during market hours
MEGA_CAPS: list[str] = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO",
    "JPM", "V", "MA", "UNH", "XOM", "LLY", "HD",
]

# VIX fear gauge thresholds
VIX_THRESHOLDS: dict[str, float] = {
    "normal": 20.0,       # VIX below this = calm market
    "elevated": 25.0,     # VIX above this = reduce position size 50%
    "high_fear": 30.0,    # VIX above this = extreme caution, consider sitting out
}

# Optimal entry timing windows (ET)
TIMING_WINDOWS: dict[str, dict[str, int]] = {
    "best_entry": {"start_hour": 10, "start_min": 0, "end_hour": 11, "end_min": 30},
    "second_best": {"start_hour": 14, "start_min": 0, "end_hour": 15, "end_min": 30},
    "avoid_open": {"start_hour": 9, "start_min": 30, "end_hour": 9, "end_min": 45},
    "avoid_close": {"start_hour": 15, "start_min": 45, "end_hour": 16, "end_min": 0},
}

# ---------------------------------------------------------------------------
# Portfolio settings
# ---------------------------------------------------------------------------
PORTFOLIO_SETTINGS: dict[str, float | int] = {
    "starting_capital": float(os.getenv("STARTING_CAPITAL", "5000")),
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

DATA_STALENESS_MINUTES = 30
