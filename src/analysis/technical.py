"""
Technical analysis engine for KešMani.

Calculates all standard indicators used by the screening and signal
modules.  All functions accept a pandas DataFrame (OHLCV) and return
either a scalar value or a dict — never raw ta-library objects.

Indicators calculated:
  - Simple Moving Averages: SMA 20, 50, 100, 200
  - Exponential Moving Averages: EMA 9, 21
  - RSI (14-period)
  - MACD (12, 26, 9)
  - Bollinger Bands (20, 2σ)
  - Average True Range (ATR-14)
  - Volume ratio (current vs 20-day avg)
  - Support & resistance levels from pivot points
  - Trend determination (MA alignment)
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from config.settings import TECHNICAL_SETTINGS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Moving averages
# ---------------------------------------------------------------------------

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Return a Simple Moving Average series."""
    return series.rolling(window=period, min_periods=period).mean()


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Return an Exponential Moving Average series."""
    return series.ewm(span=period, adjust=False).mean()


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------

def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Wilder's RSI.

    Parameters
    ----------
    close:
        Series of closing prices.
    period:
        Look-back window (default 14).

    Returns
    -------
    RSI series in the range [0, 100].
    """
    delta = close.diff()
    # Fill the first NaN (from diff) with 0 so EWM initialises cleanly
    gain = delta.clip(lower=0).fillna(0)
    loss = (-delta).clip(lower=0).fillna(0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    # When avg_loss is 0 (all gains, no losses), RSI = 100
    rsi = rsi.where(avg_loss != 0, 100.0)
    return rsi


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------

def calculate_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, pd.Series]:
    """
    Calculate MACD, signal line, and histogram.

    Returns
    -------
    Dict with keys: macd, signal, histogram.
    """
    ema_fast = calculate_ema(close, fast)
    ema_slow = calculate_ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def detect_macd_crossover(macd_dict: dict[str, pd.Series]) -> str:
    """
    Detect the most recent MACD/signal crossover.

    Returns
    -------
    "bullish_crossover", "bearish_crossover", or "none".
    """
    macd = macd_dict["macd"]
    signal = macd_dict["signal"]
    if len(macd) < 2:
        return "none"
    prev_diff = macd.iloc[-2] - signal.iloc[-2]
    curr_diff = macd.iloc[-1] - signal.iloc[-1]
    if prev_diff < 0 and curr_diff >= 0:
        return "bullish_crossover"
    if prev_diff > 0 and curr_diff <= 0:
        return "bearish_crossover"
    return "none"


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------

def calculate_bollinger_bands(
    close: pd.Series,
    period: int = 20,
    std_dev: float = 2.0,
) -> dict[str, pd.Series]:
    """
    Calculate Bollinger Bands.

    Returns
    -------
    Dict with keys: upper, middle, lower, bandwidth, percent_b.
    """
    middle = calculate_sma(close, period)
    std = close.rolling(window=period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    bandwidth = (upper - lower) / middle
    percent_b = (close - lower) / (upper - lower)
    return {
        "upper": upper,
        "middle": middle,
        "lower": lower,
        "bandwidth": bandwidth,
        "percent_b": percent_b,
    }


def detect_bb_squeeze(bands: dict[str, pd.Series], lookback: int = 20) -> bool:
    """Return True if Bollinger bandwidth is at a 20-period low (squeeze)."""
    bw = bands["bandwidth"].dropna()
    if len(bw) < lookback:
        return False
    return float(bw.iloc[-1]) <= float(bw.tail(lookback).min()) * 1.05


# ---------------------------------------------------------------------------
# ATR (Average True Range)
# ---------------------------------------------------------------------------

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range.

    Parameters
    ----------
    df:
        DataFrame with High, Low, Close columns.
    period:
        ATR period (default 14).
    """
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


# ---------------------------------------------------------------------------
# Volume analysis
# ---------------------------------------------------------------------------

def volume_ratio(volume: pd.Series, avg_period: int = 20) -> float:
    """Return current volume / N-day average volume."""
    if len(volume) < avg_period:
        return 1.0
    avg = float(volume.tail(avg_period).mean())
    if avg == 0:
        return 1.0
    return round(float(volume.iloc[-1]) / avg, 2)


# ---------------------------------------------------------------------------
# Support & Resistance
# ---------------------------------------------------------------------------

def calculate_support_resistance(df: pd.DataFrame, window: int = 20) -> dict[str, float]:
    """
    Identify key support and resistance levels using rolling pivot detection.

    A pivot high is a local maximum; a pivot low is a local minimum.
    Uses vectorized rolling operations instead of an O(n²) loop.

    Returns
    -------
    Dict with keys: resistance (nearest above), support (nearest below),
    and current_price.
    """
    if len(df) < window * 2:
        return {}

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    current_price = float(close.iloc[-1])

    # Vectorized pivot detection using centered rolling windows (replaces O(n²) loop).
    # window*2+1 looks at `window` bars before and after each bar (center=True),
    # so a pivot high is a bar whose High equals the rolling max of its neighborhood.
    rolling_high_max = high.rolling(window=window * 2 + 1, center=True, min_periods=window).max()
    rolling_low_min = low.rolling(window=window * 2 + 1, center=True, min_periods=window).min()

    pivot_high_mask = high == rolling_high_max
    pivot_low_mask = low == rolling_low_min

    pivot_highs: list[float] = high[pivot_high_mask].tolist()
    pivot_lows: list[float] = low[pivot_low_mask].tolist()

    resistance_levels = sorted([p for p in pivot_highs if p > current_price])
    support_levels = sorted([p for p in pivot_lows if p < current_price], reverse=True)

    return {
        "current_price": current_price,
        "resistance": resistance_levels[0] if resistance_levels else current_price * 1.05,
        "support": support_levels[0] if support_levels else current_price * 0.95,
        "all_resistance": resistance_levels[:3],
        "all_support": support_levels[:3],
    }


# ---------------------------------------------------------------------------
# Stochastic RSI
# ---------------------------------------------------------------------------

def calculate_stoch_rsi(
    close: pd.Series,
    period: int = 14,
    smooth_k: int = 3,
    smooth_d: int = 3,
) -> dict[str, pd.Series]:
    """
    Calculate Stochastic RSI (%K and %D lines).

    Parameters
    ----------
    close:
        Series of closing prices.
    period:
        RSI look-back window (default 14).
    smooth_k:
        Smoothing period for %K (default 3).
    smooth_d:
        Smoothing period for %D (default 3).

    Returns
    -------
    Dict with keys: stoch_k, stoch_d — both series in [0, 100].
    """
    rsi = calculate_rsi(close, period)
    rsi_min = rsi.rolling(window=period, min_periods=1).min()
    rsi_max = rsi.rolling(window=period, min_periods=1).max()
    rsi_range = rsi_max - rsi_min
    stoch_k_raw = 100 * (rsi - rsi_min) / rsi_range.replace(0, np.nan)
    stoch_k = stoch_k_raw.rolling(window=smooth_k, min_periods=1).mean()
    stoch_d = stoch_k.rolling(window=smooth_d, min_periods=1).mean()
    return {"stoch_k": stoch_k, "stoch_d": stoch_d}


# ---------------------------------------------------------------------------
# On-Balance Volume (OBV)
# ---------------------------------------------------------------------------

def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    Calculate On-Balance Volume (OBV).

    OBV is a running total of volume that adds volume on up-days and
    subtracts volume on down-days.  It is a trend-confirmation indicator.

    Parameters
    ----------
    close:
        Series of closing prices.
    volume:
        Series of trading volume.

    Returns
    -------
    OBV series.
    """
    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv = (direction * volume).fillna(0).cumsum()
    return obv


# ---------------------------------------------------------------------------
# Relative Strength vs benchmark
# ---------------------------------------------------------------------------

def calculate_relative_strength(
    close: pd.Series,
    benchmark_close: pd.Series,
    period: int = 90,
) -> float:
    """
    Calculate relative strength of a ticker vs a benchmark (e.g. SPY).

    Computes the ratio of the ticker's return over ``period`` bars vs
    the benchmark return over the same period, then normalises to 0–100.

    Parameters
    ----------
    close:
        Closing prices for the ticker.
    benchmark_close:
        Closing prices for the benchmark (must share the same date index).
    period:
        Look-back window in trading days (default 90).

    Returns
    -------
    RS Rating in [0, 100].  50 = in-line with benchmark.
    """
    if len(close) < period or len(benchmark_close) < period:
        return 50.0
    try:
        ticker_return = (float(close.iloc[-1]) / float(close.iloc[-period]) - 1) * 100
        bench_return = (float(benchmark_close.iloc[-1]) / float(benchmark_close.iloc[-period]) - 1) * 100
        # Relative return: positive = outperforming
        rel_return = ticker_return - bench_return
        # Normalise to 0–100: clamp at ±50% relative return
        clamped = max(-50.0, min(50.0, rel_return))
        return round(50.0 + clamped, 2)
    except Exception:
        return 50.0


# ---------------------------------------------------------------------------
# Trend determination
# ---------------------------------------------------------------------------

def determine_trend(close: pd.Series, sma_values: dict[str, float]) -> str:
    """
    Determine the trend using MA alignment.

    Bullish:  price > SMA20 > SMA50 > SMA200
    Bearish:  price < SMA20 < SMA50 < SMA200
    Neutral:  anything else

    Returns
    -------
    "BULLISH", "BEARISH", or "NEUTRAL".
    """
    price = float(close.iloc[-1])
    sma20 = sma_values.get("sma_20")
    sma50 = sma_values.get("sma_50")
    sma200 = sma_values.get("sma_200")

    if None in (sma20, sma50, sma200):
        return "NEUTRAL"

    if price > sma20 > sma50 > sma200:
        return "BULLISH"
    if price < sma20 < sma50 < sma200:
        return "BEARISH"
    return "NEUTRAL"


# ---------------------------------------------------------------------------
# Master indicator calculator
# ---------------------------------------------------------------------------

def compute_all_indicators(df: pd.DataFrame) -> dict[str, float | bool | str | None]:
    """
    Compute the full set of technical indicators for a ticker.

    Parameters
    ----------
    df:
        OHLCV DataFrame (must have Open, High, Low, Close, Volume columns).

    Returns
    -------
    Dict containing all scalar indicator values needed by the screener
    and signal modules.  Returns an empty dict when there is insufficient
    data (fewer than 200 bars — required for SMA-200).
    """
    if df.empty or len(df) < 200:
        logger.warning(
            "Insufficient data for full indicator calculation (%d rows). "
            "Need at least 200 bars for SMA-200. Returning empty dict.",
            len(df),
        )
        return {}

    cfg = TECHNICAL_SETTINGS
    close = df["Close"]
    volume = df["Volume"]

    # --- Moving averages ---
    sma_values: dict[str, Optional[float]] = {}
    for p in cfg["sma_periods"]:
        sma = calculate_sma(close, p)
        sma_values[f"sma_{p}"] = float(sma.iloc[-1]) if not sma.isna().iloc[-1] else None

    ema_values: dict[str, Optional[float]] = {}
    for p in cfg["ema_periods"]:
        ema = calculate_ema(close, p)
        ema_values[f"ema_{p}"] = float(ema.iloc[-1]) if not np.isnan(ema.iloc[-1]) else None

    # --- RSI ---
    rsi_series = calculate_rsi(close, cfg["rsi_period"])
    rsi = float(rsi_series.iloc[-1]) if not np.isnan(rsi_series.iloc[-1]) else None

    # --- Stochastic RSI ---
    stoch = calculate_stoch_rsi(close)
    stoch_k = float(stoch["stoch_k"].iloc[-1]) if not np.isnan(stoch["stoch_k"].iloc[-1]) else None
    stoch_d = float(stoch["stoch_d"].iloc[-1]) if not np.isnan(stoch["stoch_d"].iloc[-1]) else None

    # --- MACD ---
    macd_dict = calculate_macd(close, cfg["macd_fast"], cfg["macd_slow"], cfg["macd_signal"])
    macd_val = float(macd_dict["macd"].iloc[-1])
    macd_signal_val = float(macd_dict["signal"].iloc[-1])
    macd_hist_val = float(macd_dict["histogram"].iloc[-1])
    macd_crossover = detect_macd_crossover(macd_dict)

    # --- Bollinger Bands ---
    bb = calculate_bollinger_bands(close, cfg["bb_period"], cfg["bb_std"])
    bb_squeeze = detect_bb_squeeze(bb)
    bb_upper = float(bb["upper"].iloc[-1]) if not bb["upper"].isna().iloc[-1] else None
    bb_lower = float(bb["lower"].iloc[-1]) if not bb["lower"].isna().iloc[-1] else None
    bb_pct = float(bb["percent_b"].iloc[-1]) if not bb["percent_b"].isna().iloc[-1] else None

    # --- ATR ---
    atr_series = calculate_atr(df, cfg["atr_period"])
    atr = float(atr_series.iloc[-1]) if not atr_series.isna().iloc[-1] else None

    # --- Volume ---
    vol_ratio = volume_ratio(volume, cfg["volume_avg_period"])

    # --- OBV ---
    obv_series = calculate_obv(close, volume)
    obv = float(obv_series.iloc[-1]) if not np.isnan(obv_series.iloc[-1]) else None

    # --- Support & Resistance ---
    sr = calculate_support_resistance(df)

    # --- Trend ---
    trend = determine_trend(close, sma_values)

    return {
        "current_price": float(close.iloc[-1]),
        **sma_values,
        **ema_values,
        "rsi": rsi,
        "rsi_overbought": rsi is not None and rsi > cfg["rsi_overbought"],
        "rsi_oversold": rsi is not None and rsi < cfg["rsi_oversold"],
        "stoch_rsi_k": stoch_k,
        "stoch_rsi_d": stoch_d,
        "stoch_rsi_overbought": stoch_k is not None and stoch_k > 80,
        "stoch_rsi_oversold": stoch_k is not None and stoch_k < 20,
        "macd": macd_val,
        "macd_signal": macd_signal_val,
        "macd_histogram": macd_hist_val,
        "macd_crossover": macd_crossover,
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "bb_percent_b": bb_pct,
        "bb_squeeze": bb_squeeze,
        "atr": atr,
        "volume_ratio": vol_ratio,
        "obv": obv,
        "support": sr.get("support"),
        "resistance": sr.get("resistance"),
        "trend": trend,
    }


def compute_multi_timeframe_signal(
    ticker: str,
    periods: list[str] | None = None,
) -> dict:
    """
    Fetch and analyse a ticker on multiple timeframes and return a confluence score.

    Parameters
    ----------
    ticker:
        Equity symbol.
    periods:
        yfinance period strings to analyse (default ["1y", "2y"]).
        Note: yfinance "interval" is daily; multi-period gives more history.

    Returns
    -------
    Dict with keys: daily_trend, weekly_trend, confluence (STRONG/MODERATE/WEAK),
    and confluence_score (0–100).
    """
    if periods is None:
        periods = ["1y", "2y"]

    from src.data.market_data import fetch_ohlcv

    results: dict[str, str] = {}
    for period in periods:
        df = fetch_ohlcv(ticker, period=period)
        if df.empty or len(df) < 200:
            results[period] = "NEUTRAL"
            continue
        indicators = compute_all_indicators(df)
        results[period] = indicators.get("trend", "NEUTRAL")

    trends = list(results.values())
    bullish_count = trends.count("BULLISH")
    bearish_count = trends.count("BEARISH")
    total = len(trends)

    if bullish_count == total:
        confluence = "STRONG BULLISH"
        score = 85.0
    elif bullish_count > total / 2:
        confluence = "MODERATE BULLISH"
        score = 65.0
    elif bearish_count == total:
        confluence = "STRONG BEARISH"
        score = 15.0
    elif bearish_count > total / 2:
        confluence = "MODERATE BEARISH"
        score = 35.0
    else:
        confluence = "NEUTRAL"
        score = 50.0

    return {
        **{f"trend_{p}": v for p, v in results.items()},
        "confluence": confluence,
        "confluence_score": score,
    }
