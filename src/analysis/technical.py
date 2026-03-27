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
    Identify key support and resistance levels using recent pivot points.

    A pivot high is a local maximum; a pivot low is a local minimum.

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

    pivot_highs: list[float] = []
    pivot_lows: list[float] = []

    for i in range(window, len(df) - window):
        if float(high.iloc[i]) == float(high.iloc[i - window : i + window].max()):
            pivot_highs.append(float(high.iloc[i]))
        if float(low.iloc[i]) == float(low.iloc[i - window : i + window].min()):
            pivot_lows.append(float(low.iloc[i]))

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

def compute_all_indicators(df: pd.DataFrame) -> dict:
    """
    Compute the full set of technical indicators for a ticker.

    Parameters
    ----------
    df:
        OHLCV DataFrame (must have Open, High, Low, Close, Volume columns).

    Returns
    -------
    Dict containing all scalar indicator values needed by the screener
    and signal modules.
    """
    if df.empty or len(df) < 30:
        logger.warning("Insufficient data for indicator calculation (%d rows)", len(df))
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
        "support": sr.get("support"),
        "resistance": sr.get("resistance"),
        "trend": trend,
    }
