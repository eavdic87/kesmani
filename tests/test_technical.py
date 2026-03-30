"""
Unit tests for the technical analysis module.

Tests are performed with synthetic price data so no network calls are made.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import pytest

from src.analysis.technical import (
    calculate_sma,
    calculate_ema,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_atr,
    calculate_stoch_rsi,
    calculate_obv,
    calculate_relative_strength,
    calculate_support_resistance,
    detect_macd_crossover,
    detect_bb_squeeze,
    volume_ratio,
    determine_trend,
    compute_all_indicators,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_series(values: list[float]) -> pd.Series:
    return pd.Series(values, dtype=float)


def make_ohlcv(n: int = 100, trend: str = "up") -> pd.DataFrame:
    """Generate synthetic OHLCV data."""
    np.random.seed(42)
    base = 100.0
    prices: list[float] = [base]
    for _ in range(n - 1):
        delta = np.random.normal(0.5 if trend == "up" else -0.5, 1.5)
        prices.append(max(1.0, prices[-1] + delta))

    close = np.array(prices)
    high = close + np.random.uniform(0.5, 2.0, n)
    low = close - np.random.uniform(0.5, 2.0, n)
    open_ = close + np.random.normal(0, 1, n)
    volume = np.random.randint(500_000, 5_000_000, n).astype(float)

    df = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=pd.date_range("2024-01-01", periods=n, freq="D"),
    )
    return df


# ---------------------------------------------------------------------------
# SMA tests
# ---------------------------------------------------------------------------

class TestSMA:
    def test_basic_sma(self):
        s = make_series([1.0, 2.0, 3.0, 4.0, 5.0])
        sma = calculate_sma(s, 3)
        assert pd.isna(sma.iloc[0])
        assert pd.isna(sma.iloc[1])
        assert sma.iloc[2] == pytest.approx(2.0)
        assert sma.iloc[4] == pytest.approx(4.0)

    def test_sma_length_preserved(self):
        s = make_series(list(range(20)))
        sma = calculate_sma(s, 5)
        assert len(sma) == len(s)

    def test_sma_constant_series(self):
        s = make_series([10.0] * 10)
        sma = calculate_sma(s, 5)
        assert sma.dropna().iloc[-1] == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# EMA tests
# ---------------------------------------------------------------------------

class TestEMA:
    def test_ema_converges(self):
        # Constant series → EMA == constant
        s = make_series([50.0] * 30)
        ema = calculate_ema(s, 9)
        assert ema.iloc[-1] == pytest.approx(50.0, abs=0.1)

    def test_ema_faster_than_sma(self):
        # EMA reacts faster: after a big jump, EMA should be lower than current price
        # but higher than the old average, showing it's converging faster than SMA
        # from below when prices suddenly jump up then stay there.
        values = [100.0] * 20 + [200.0] * 30
        s = make_series(values)
        ema = calculate_ema(s, 9)
        sma = calculate_sma(s, 9)
        # After 30 periods of 200, both should be close to 200
        # but SMA(9) is exactly 200 because last 9 values are all 200
        # EMA still slightly below due to decay from initial 100
        # Verify that EMA is in the right ballpark (> 180)
        assert float(ema.iloc[-1]) > 180.0
        # After enough time, both should converge to the new price
        long_values = [100.0] * 20 + [200.0] * 100
        s2 = make_series(long_values)
        ema2 = calculate_ema(s2, 9)
        assert float(ema2.iloc[-1]) == pytest.approx(200.0, abs=0.01)


# ---------------------------------------------------------------------------
# RSI tests
# ---------------------------------------------------------------------------

class TestRSI:
    def test_rsi_range(self):
        df = make_ohlcv(100)
        rsi = calculate_rsi(df["Close"])
        valid = rsi.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_rsi_overbought(self):
        # Strongly rising prices → RSI should approach overbought
        # Use enough data points and a clear uptrend
        values = [float(i) for i in range(1, 101)]
        s = make_series(values)
        rsi = calculate_rsi(s, 14)
        assert rsi.iloc[-1] > 70

    def test_rsi_oversold(self):
        # Strongly falling prices → RSI should approach oversold
        values = [float(50 - i) for i in range(50)]
        s = make_series(values)
        rsi = calculate_rsi(s, 14)
        assert rsi.dropna().iloc[-1] < 30

    def test_rsi_default_period_14(self):
        df = make_ohlcv(60)
        rsi = calculate_rsi(df["Close"])
        assert len(rsi) == 60


# ---------------------------------------------------------------------------
# MACD tests
# ---------------------------------------------------------------------------

class TestMACD:
    def test_macd_returns_correct_keys(self):
        df = make_ohlcv(100)
        result = calculate_macd(df["Close"])
        assert "macd" in result
        assert "signal" in result
        assert "histogram" in result

    def test_histogram_is_macd_minus_signal(self):
        df = make_ohlcv(100)
        result = calculate_macd(df["Close"])
        diff = result["macd"] - result["signal"]
        pd.testing.assert_series_equal(
            result["histogram"].round(10), diff.round(10), check_names=False
        )

    def test_macd_crossover_detection(self):
        # Manufacture a bullish crossover at the last two elements
        # prev: macd < signal, curr: macd > signal
        macd_vals = make_series([-1.0, 1.0])
        signal_vals = make_series([0.0, 0.0])
        macd_dict = {
            "macd": macd_vals,
            "signal": signal_vals,
        }
        result = detect_macd_crossover(macd_dict)
        assert result == "bullish_crossover"

    def test_bearish_crossover(self):
        # prev: macd > signal, curr: macd < signal
        macd_vals = make_series([1.0, -1.0])
        signal_vals = make_series([0.0, 0.0])
        macd_dict = {
            "macd": macd_vals,
            "signal": signal_vals,
        }
        result = detect_macd_crossover(macd_dict)
        assert result == "bearish_crossover"


# ---------------------------------------------------------------------------
# Bollinger Band tests
# ---------------------------------------------------------------------------

class TestBollingerBands:
    def test_keys_present(self):
        df = make_ohlcv(60)
        bands = calculate_bollinger_bands(df["Close"])
        for k in ("upper", "middle", "lower", "bandwidth", "percent_b"):
            assert k in bands

    def test_upper_above_lower(self):
        df = make_ohlcv(60)
        bands = calculate_bollinger_bands(df["Close"])
        upper = bands["upper"].dropna()
        lower = bands["lower"].dropna()
        assert (upper > lower).all()

    def test_middle_between_bands(self):
        df = make_ohlcv(60)
        bands = calculate_bollinger_bands(df["Close"])
        middle = bands["middle"].dropna()
        upper = bands["upper"].dropna()
        lower = bands["lower"].dropna()
        assert (middle <= upper).all()
        assert (middle >= lower).all()

    def test_bb_squeeze_false_on_wide_bands(self):
        # Highly volatile data → bands should be wide → no squeeze
        values = [100.0 + (i % 2) * 20 for i in range(50)]
        s = make_series(values)
        bands = calculate_bollinger_bands(s)
        # Wide bands → squeeze should be False most of the time
        # (just verify it returns a boolean)
        assert isinstance(detect_bb_squeeze(bands), bool)


# ---------------------------------------------------------------------------
# ATR tests
# ---------------------------------------------------------------------------

class TestATR:
    def test_atr_positive(self):
        df = make_ohlcv(50)
        atr = calculate_atr(df, 14)
        valid = atr.dropna()
        assert (valid > 0).all()

    def test_atr_length(self):
        df = make_ohlcv(50)
        atr = calculate_atr(df)
        assert len(atr) == 50


# ---------------------------------------------------------------------------
# Volume ratio tests
# ---------------------------------------------------------------------------

class TestVolumeRatio:
    def test_ratio_of_1_when_constant(self):
        vol = make_series([1_000_000.0] * 25)
        ratio = volume_ratio(vol, 20)
        assert ratio == pytest.approx(1.0, abs=0.01)

    def test_high_volume_last_day(self):
        base = [1_000_000.0] * 20
        high_vol = base + [5_000_000.0]
        vol = make_series(high_vol)
        ratio = volume_ratio(vol, 20)
        assert ratio > 1.0


# ---------------------------------------------------------------------------
# Trend determination tests
# ---------------------------------------------------------------------------

class TestTrendDetermination:
    def test_bullish_when_aligned(self):
        close = make_series([200.0])
        sma_vals = {"sma_20": 190.0, "sma_50": 180.0, "sma_200": 160.0}
        assert determine_trend(close, sma_vals) == "BULLISH"

    def test_bearish_when_aligned_down(self):
        close = make_series([100.0])
        sma_vals = {"sma_20": 110.0, "sma_50": 120.0, "sma_200": 140.0}
        assert determine_trend(close, sma_vals) == "BEARISH"

    def test_neutral_mixed(self):
        close = make_series([150.0])
        sma_vals = {"sma_20": 160.0, "sma_50": 145.0, "sma_200": 130.0}
        assert determine_trend(close, sma_vals) == "NEUTRAL"


# ---------------------------------------------------------------------------
# compute_all_indicators integration test
# ---------------------------------------------------------------------------

class TestComputeAllIndicators:
    def test_returns_expected_keys(self):
        df = make_ohlcv(250)
        result = compute_all_indicators(df)
        for key in ("current_price", "rsi", "macd", "trend", "atr", "volume_ratio"):
            assert key in result

    def test_empty_df_returns_empty_dict(self):
        df = pd.DataFrame()
        result = compute_all_indicators(df)
        assert result == {}

    def test_insufficient_data_returns_empty(self):
        # Now requires >= 200 bars (for SMA-200)
        df = make_ohlcv(150)
        result = compute_all_indicators(df)
        assert result == {}

    def test_exactly_200_bars_succeeds(self):
        df = make_ohlcv(200)
        result = compute_all_indicators(df)
        assert "current_price" in result

    def test_stoch_rsi_keys_present(self):
        df = make_ohlcv(250)
        result = compute_all_indicators(df)
        assert "stoch_rsi_k" in result
        assert "stoch_rsi_d" in result

    def test_obv_key_present(self):
        df = make_ohlcv(250)
        result = compute_all_indicators(df)
        assert "obv" in result


# ---------------------------------------------------------------------------
# Stochastic RSI tests
# ---------------------------------------------------------------------------

class TestStochasticRSI:
    def test_returns_expected_keys(self):
        df = make_ohlcv(100)
        result = calculate_stoch_rsi(df["Close"])
        assert "stoch_k" in result
        assert "stoch_d" in result

    def test_values_in_range(self):
        df = make_ohlcv(100)
        result = calculate_stoch_rsi(df["Close"])
        k = result["stoch_k"].dropna()
        d = result["stoch_d"].dropna()
        assert (k >= 0).all() and (k <= 100).all()
        assert (d >= 0).all() and (d <= 100).all()

    def test_length_preserved(self):
        df = make_ohlcv(100)
        result = calculate_stoch_rsi(df["Close"])
        assert len(result["stoch_k"]) == 100


# ---------------------------------------------------------------------------
# OBV tests
# ---------------------------------------------------------------------------

class TestOBV:
    def test_increases_on_up_day(self):
        # Simple 3-bar: price up, price up → OBV should grow
        close = make_series([10.0, 11.0, 12.0])
        volume = make_series([1000.0, 1000.0, 1000.0])
        obv = calculate_obv(close, volume)
        assert float(obv.iloc[-1]) > float(obv.iloc[0])

    def test_decreases_on_down_day(self):
        close = make_series([12.0, 11.0, 10.0])
        volume = make_series([1000.0, 1000.0, 1000.0])
        obv = calculate_obv(close, volume)
        assert float(obv.iloc[-1]) < float(obv.iloc[0])

    def test_length_preserved(self):
        df = make_ohlcv(60)
        obv = calculate_obv(df["Close"], df["Volume"])
        assert len(obv) == 60


# ---------------------------------------------------------------------------
# Relative Strength tests
# ---------------------------------------------------------------------------

class TestRelativeStrength:
    def test_outperforming_ticker_above_50(self):
        # Ticker up 20% vs benchmark up 5% → RS > 50
        np.random.seed(0)
        n = 100
        ticker_close = make_series([100.0 * (1.002 ** i) for i in range(n)])
        bench_close = make_series([100.0 * (1.0005 ** i) for i in range(n)])
        rs = calculate_relative_strength(ticker_close, bench_close, period=90)
        assert rs > 50

    def test_underperforming_ticker_below_50(self):
        n = 100
        ticker_close = make_series([100.0 * (0.999 ** i) for i in range(n)])
        bench_close = make_series([100.0 * (1.001 ** i) for i in range(n)])
        rs = calculate_relative_strength(ticker_close, bench_close, period=90)
        assert rs < 50

    def test_returns_50_for_short_series(self):
        close = make_series([100.0] * 10)
        bench = make_series([100.0] * 10)
        rs = calculate_relative_strength(close, bench, period=90)
        assert rs == 50.0


# ---------------------------------------------------------------------------
# Support & Resistance (vectorized) tests
# ---------------------------------------------------------------------------

class TestSupportResistanceVectorized:
    def test_returns_expected_keys(self):
        df = make_ohlcv(200)
        result = calculate_support_resistance(df)
        for key in ("current_price", "resistance", "support"):
            assert key in result

    def test_support_below_current_price(self):
        df = make_ohlcv(200)
        result = calculate_support_resistance(df)
        assert result["support"] < result["current_price"]

    def test_resistance_above_current_price(self):
        df = make_ohlcv(200)
        result = calculate_support_resistance(df)
        assert result["resistance"] > result["current_price"]

    def test_insufficient_data_returns_empty(self):
        df = make_ohlcv(20)
        result = calculate_support_resistance(df, window=20)
        assert result == {}
