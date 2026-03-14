"""Tests for the indicators service (calculate_indicators, generate_signal, aggregate_signals)."""

import calendar
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.services.indicators import (
    aggregate_signals,
    calculate_indicators,
    generate_signal,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXPECTED_INDICATOR_IDS = {
    "rsi",
    "macd",
    "bollinger",
    "ma",
    "stochastic",
    "obv",
    "fibonacci",
    "atr",
    "ichimoku",
    "cci",
}

EXPECTED_SERIES_KEYS: dict[str, set[str]] = {
    "rsi": {"rsi"},
    "macd": {"macd", "signal", "histogram"},
    "bollinger": {"upper", "middle", "lower"},
    "ma": {"sma20", "sma50", "sma200"},
    "stochastic": {"k", "d"},
    "obv": {"obv"},
    "fibonacci": {"fib_0", "fib_24", "fib_38", "fib_50", "fib_62", "fib_79", "fib_100"},
    "atr": {"atr"},
    "ichimoku": {"tenkan", "kijun"},
    "cci": {"cci"},
}


def _make_ohlcv(n: int = 300, base_price: float = 100.0, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic OHLCV data with enough rows for all indicator lookbacks."""
    rng = np.random.default_rng(seed)
    dates = [date(2024, 1, 2) + timedelta(days=i) for i in range(n)]
    closes = np.cumsum(rng.normal(0, 1, n)) + base_price
    # Ensure all prices are positive
    closes = closes - closes.min() + 10.0

    opens = closes + rng.normal(0, 0.5, n)
    highs = np.maximum(opens, closes) + np.abs(rng.normal(0, 0.8, n))
    lows = np.minimum(opens, closes) - np.abs(rng.normal(0, 0.8, n))
    volumes = np.abs(rng.normal(1_000_000, 300_000, n))

    df = pd.DataFrame(
        {
            "Date": dates,
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": volumes,
        }
    )
    df["Date"] = pd.to_datetime(df["Date"])
    df.set_index("Date", inplace=True)
    return df


@pytest.fixture
def ohlcv_df() -> pd.DataFrame:
    """Standard 300-row OHLCV DataFrame fixture."""
    return _make_ohlcv()


# ---------------------------------------------------------------------------
# Test: calculate_indicators
# ---------------------------------------------------------------------------


def test_calculate_all_indicators_returns_correct_keys(ohlcv_df: pd.DataFrame):
    """All 10 indicator IDs present in output with correct series keys."""
    result = calculate_indicators(ohlcv_df)
    assert set(result.keys()) == EXPECTED_INDICATOR_IDS


def test_indicator_series_keys_match_frontend(ohlcv_df: pd.DataFrame):
    """Each indicator produces exactly the series keys the frontend expects."""
    result = calculate_indicators(ohlcv_df)
    for ind_id, expected_keys in EXPECTED_SERIES_KEYS.items():
        actual_keys = set(result[ind_id].keys())
        assert actual_keys == expected_keys, (
            f"{ind_id}: expected {expected_keys}, got {actual_keys}"
        )


def test_nan_rows_dropped(ohlcv_df: pd.DataFrame):
    """Leading NaN from lookback periods are stripped from output."""
    result = calculate_indicators(ohlcv_df)

    for ind_id, series_dict in result.items():
        for key, points in series_dict.items():
            for pt in points:
                assert pt["value"] is not None, f"{ind_id}.{key} has None value"
                assert not np.isnan(pt["value"]), f"{ind_id}.{key} has NaN value"


def test_timestamps_are_unix_seconds(ohlcv_df: pd.DataFrame):
    """All time values are unix timestamps (integer seconds)."""
    result = calculate_indicators(ohlcv_df)

    for ind_id, series_dict in result.items():
        for key, points in series_dict.items():
            if len(points) == 0:
                continue
            first = points[0]
            assert isinstance(first["time"], int), (
                f"{ind_id}.{key} time is {type(first['time'])}, expected int"
            )
            # Sanity: timestamps should be in a reasonable range (year 2024)
            assert first["time"] > 1_700_000_000, (
                f"{ind_id}.{key} timestamp {first['time']} too small"
            )


def test_series_have_data_points(ohlcv_df: pd.DataFrame):
    """Each series has at least some data points (not all dropped by NaN filtering)."""
    result = calculate_indicators(ohlcv_df)

    for ind_id, series_dict in result.items():
        for key, points in series_dict.items():
            assert len(points) > 0, f"{ind_id}.{key} is empty"


# ---------------------------------------------------------------------------
# Test: generate_signal — RSI
# ---------------------------------------------------------------------------


def test_rsi_signal_overbought():
    """RSI > 70 generates sell signal."""
    series = {"rsi": [{"time": 100, "value": 75.0}]}
    assert generate_signal("rsi", series) == "sell"


def test_rsi_signal_oversold():
    """RSI < 30 generates buy signal."""
    series = {"rsi": [{"time": 100, "value": 25.0}]}
    assert generate_signal("rsi", series) == "buy"


def test_rsi_signal_neutral():
    """RSI between 30 and 70 generates hold signal."""
    series = {"rsi": [{"time": 100, "value": 50.0}]}
    assert generate_signal("rsi", series) == "hold"


# ---------------------------------------------------------------------------
# Test: generate_signal — MACD
# ---------------------------------------------------------------------------


def test_macd_signal_crossover():
    """MACD > signal line generates buy signal."""
    series = {
        "macd": [{"time": 100, "value": 5.0}],
        "signal": [{"time": 100, "value": 3.0}],
        "histogram": [{"time": 100, "value": 2.0}],
    }
    assert generate_signal("macd", series) == "buy"


def test_macd_signal_bearish():
    """MACD < signal line generates sell signal."""
    series = {
        "macd": [{"time": 100, "value": 2.0}],
        "signal": [{"time": 100, "value": 5.0}],
        "histogram": [{"time": 100, "value": -3.0}],
    }
    assert generate_signal("macd", series) == "sell"


# ---------------------------------------------------------------------------
# Test: generate_signal — Bollinger
# ---------------------------------------------------------------------------


def test_bollinger_signal_buy():
    """Close below lower band generates buy signal."""
    df = pd.DataFrame({"Close": [90.0]})
    series = {
        "upper": [{"time": 100, "value": 110.0}],
        "middle": [{"time": 100, "value": 100.0}],
        "lower": [{"time": 100, "value": 95.0}],
    }
    assert generate_signal("bollinger", series, df) == "buy"


def test_bollinger_signal_sell():
    """Close above upper band generates sell signal."""
    df = pd.DataFrame({"Close": [115.0]})
    series = {
        "upper": [{"time": 100, "value": 110.0}],
        "middle": [{"time": 100, "value": 100.0}],
        "lower": [{"time": 100, "value": 95.0}],
    }
    assert generate_signal("bollinger", series, df) == "sell"


# ---------------------------------------------------------------------------
# Test: generate_signal — Stochastic
# ---------------------------------------------------------------------------


def test_stochastic_signal_oversold():
    """K < 20 generates buy signal."""
    series = {
        "k": [{"time": 100, "value": 15.0}],
        "d": [{"time": 100, "value": 18.0}],
    }
    assert generate_signal("stochastic", series) == "buy"


def test_stochastic_signal_overbought():
    """K > 80 generates sell signal."""
    series = {
        "k": [{"time": 100, "value": 85.0}],
        "d": [{"time": 100, "value": 82.0}],
    }
    assert generate_signal("stochastic", series) == "sell"


# ---------------------------------------------------------------------------
# Test: generate_signal — CCI
# ---------------------------------------------------------------------------


def test_cci_signal_buy():
    """CCI < -100 generates buy signal."""
    series = {"cci": [{"time": 100, "value": -120.0}]}
    assert generate_signal("cci", series) == "buy"


def test_cci_signal_sell():
    """CCI > 100 generates sell signal."""
    series = {"cci": [{"time": 100, "value": 130.0}]}
    assert generate_signal("cci", series) == "sell"


# ---------------------------------------------------------------------------
# Test: generate_signal — MA
# ---------------------------------------------------------------------------


def test_ma_signal_buy():
    """Price above SMA200 and SMA50 above SMA200 generates buy signal."""
    df = pd.DataFrame({"Close": [150.0]})
    series = {
        "sma20": [{"time": 100, "value": 140.0}],
        "sma50": [{"time": 100, "value": 130.0}],
        "sma200": [{"time": 100, "value": 120.0}],
    }
    assert generate_signal("ma", series, df) == "buy"


def test_ma_signal_sell():
    """Price below SMA200 and SMA50 below SMA200 generates sell signal."""
    df = pd.DataFrame({"Close": [100.0]})
    series = {
        "sma20": [{"time": 100, "value": 110.0}],
        "sma50": [{"time": 100, "value": 115.0}],
        "sma200": [{"time": 100, "value": 130.0}],
    }
    assert generate_signal("ma", series, df) == "sell"


# ---------------------------------------------------------------------------
# Test: generate_signal — ATR
# ---------------------------------------------------------------------------


def test_atr_signal_always_hold():
    """ATR always returns hold."""
    series = {"atr": [{"time": 100, "value": 5.0}]}
    assert generate_signal("atr", series) == "hold"


# ---------------------------------------------------------------------------
# Test: generate_signal — Ichimoku
# ---------------------------------------------------------------------------


def test_ichimoku_signal_buy():
    """Price above cloud (above both tenkan and kijun) generates buy signal."""
    df = pd.DataFrame({"Close": [150.0]})
    series = {
        "tenkan": [{"time": 100, "value": 130.0}],
        "kijun": [{"time": 100, "value": 120.0}],
    }
    assert generate_signal("ichimoku", series, df) == "buy"


def test_ichimoku_signal_sell():
    """Price below cloud (below both tenkan and kijun) generates sell signal."""
    df = pd.DataFrame({"Close": [100.0]})
    series = {
        "tenkan": [{"time": 100, "value": 130.0}],
        "kijun": [{"time": 100, "value": 120.0}],
    }
    assert generate_signal("ichimoku", series, df) == "sell"


# ---------------------------------------------------------------------------
# Test: generate_signal — OBV
# ---------------------------------------------------------------------------


def test_obv_signal_rising():
    """Rising OBV trend generates buy signal."""
    series = {
        "obv": [
            {"time": 100, "value": 1000.0},
            {"time": 101, "value": 1100.0},
            {"time": 102, "value": 1200.0},
            {"time": 103, "value": 1300.0},
            {"time": 104, "value": 1400.0},
        ]
    }
    assert generate_signal("obv", series) == "buy"


def test_obv_signal_falling():
    """Falling OBV trend generates sell signal."""
    series = {
        "obv": [
            {"time": 100, "value": 1400.0},
            {"time": 101, "value": 1300.0},
            {"time": 102, "value": 1200.0},
            {"time": 103, "value": 1100.0},
            {"time": 104, "value": 1000.0},
        ]
    }
    assert generate_signal("obv", series) == "sell"


# ---------------------------------------------------------------------------
# Test: generate_signal — Fibonacci
# ---------------------------------------------------------------------------


def test_fibonacci_levels():
    """Fibonacci generates 7 levels from high/low range."""
    df = _make_ohlcv()
    result = calculate_indicators(df)
    fib = result["fibonacci"]

    assert len(fib) == 7
    expected_keys = {"fib_0", "fib_24", "fib_38", "fib_50", "fib_62", "fib_79", "fib_100"}
    assert set(fib.keys()) == expected_keys

    # Each level should have the same number of points (all dates)
    lengths = [len(v) for v in fib.values()]
    assert len(set(lengths)) == 1, f"Fibonacci levels have different lengths: {lengths}"


def test_fibonacci_level_values():
    """Fibonacci level values are computed correctly from high/low range."""
    # Create simple data where high=200, low=100, so diff=100
    n = 50
    dates = [date(2024, 1, 2) + timedelta(days=i) for i in range(n)]
    df = pd.DataFrame(
        {
            "Date": pd.to_datetime(dates),
            "Open": [150.0] * n,
            "High": [200.0] * n,
            "Low": [100.0] * n,
            "Close": [150.0] * n,
            "Volume": [1_000_000.0] * n,
        }
    )
    df.set_index("Date", inplace=True)

    result = calculate_indicators(df)
    fib = result["fibonacci"]

    # fib_0 = high = 200, fib_100 = low = 100
    # fib_50 = high - diff * 0.5 = 150
    assert fib["fib_0"][0]["value"] == pytest.approx(200.0)
    assert fib["fib_100"][0]["value"] == pytest.approx(100.0)
    assert fib["fib_50"][0]["value"] == pytest.approx(150.0)


def test_fibonacci_signal_near_support():
    """Close near fib support level generates buy signal."""
    # Support at fib_62 (~38.2% retracement from low)
    series = {
        "fib_0": [{"time": 100, "value": 200.0}],
        "fib_24": [{"time": 100, "value": 176.4}],
        "fib_38": [{"time": 100, "value": 161.8}],
        "fib_50": [{"time": 100, "value": 150.0}],
        "fib_62": [{"time": 100, "value": 138.2}],
        "fib_79": [{"time": 100, "value": 121.4}],
        "fib_100": [{"time": 100, "value": 100.0}],
    }
    # Close near fib_62 (support)
    df = pd.DataFrame({"Close": [139.0]})
    assert generate_signal("fibonacci", series, df) == "buy"


def test_fibonacci_signal_near_resistance():
    """Close near fib resistance level generates sell signal."""
    series = {
        "fib_0": [{"time": 100, "value": 200.0}],
        "fib_24": [{"time": 100, "value": 176.4}],
        "fib_38": [{"time": 100, "value": 161.8}],
        "fib_50": [{"time": 100, "value": 150.0}],
        "fib_62": [{"time": 100, "value": 138.2}],
        "fib_79": [{"time": 100, "value": 121.4}],
        "fib_100": [{"time": 100, "value": 100.0}],
    }
    # Close near fib_24 (resistance)
    df = pd.DataFrame({"Close": [177.0]})
    assert generate_signal("fibonacci", series, df) == "sell"


# ---------------------------------------------------------------------------
# Test: aggregate_signals
# ---------------------------------------------------------------------------


def test_aggregate_majority_vote():
    """Majority buy/sell/hold wins. Ties go to hold."""
    signals = {
        "rsi": "buy",
        "macd": "buy",
        "bollinger": "buy",
        "ma": "sell",
        "stochastic": "hold",
        "obv": "hold",
        "fibonacci": "hold",
        "atr": "hold",
        "ichimoku": "sell",
        "cci": "hold",
    }
    # 3 buy, 2 sell, 5 hold → hold wins
    assert aggregate_signals(signals) == "hold"


def test_aggregate_majority_buy():
    """Majority buy wins when buy count is highest."""
    signals = {
        "rsi": "buy",
        "macd": "buy",
        "bollinger": "buy",
        "ma": "buy",
        "stochastic": "buy",
        "obv": "buy",
        "fibonacci": "hold",
        "atr": "hold",
        "ichimoku": "sell",
        "cci": "sell",
    }
    # 6 buy, 2 sell, 2 hold → buy wins
    assert aggregate_signals(signals) == "buy"


def test_aggregate_majority_sell():
    """Majority sell wins when sell count is highest."""
    signals = {
        "rsi": "sell",
        "macd": "sell",
        "bollinger": "sell",
        "ma": "sell",
        "stochastic": "sell",
        "obv": "sell",
        "fibonacci": "hold",
        "atr": "hold",
        "ichimoku": "buy",
        "cci": "buy",
    }
    # 2 buy, 6 sell, 2 hold → sell wins
    assert aggregate_signals(signals) == "sell"


def test_aggregate_tie_goes_to_hold():
    """When buy and sell are tied, result is hold."""
    signals = {
        "rsi": "buy",
        "macd": "buy",
        "bollinger": "sell",
        "ma": "sell",
        "stochastic": "hold",
    }
    # 2 buy, 2 sell, 1 hold → tie between buy/sell → hold
    assert aggregate_signals(signals) == "hold"


def test_aggregate_empty_returns_hold():
    """Empty signal dict returns hold."""
    assert aggregate_signals({}) == "hold"


# ---------------------------------------------------------------------------
# Integration: calculate + signal for real data
# ---------------------------------------------------------------------------


def test_proxy_ohlcv_produces_valid_fund_indicators():
    """Proxy DataFrame (O=H=L=C=NAV, V=0) produces data for eligible indicators."""
    import random
    rng = random.Random(42)
    nav_values = [100 + i * 0.1 + rng.uniform(-2, 2) for i in range(300)]
    df = pd.DataFrame({
        "Open": nav_values, "High": nav_values, "Low": nav_values,
        "Close": nav_values, "Volume": [0] * 300,
    }, index=pd.date_range("2025-01-01", periods=300, freq="B", tz="UTC"))
    result = calculate_indicators(df)
    for ind_id in ("rsi", "macd", "ma", "cci", "bollinger"):
        assert any(len(pts) > 0 for pts in result[ind_id].values()), f"{ind_id} has no data"


def test_end_to_end_signals(ohlcv_df: pd.DataFrame):
    """calculate_indicators → generate_signal for each → aggregate_signals produces valid result."""
    indicators = calculate_indicators(ohlcv_df)
    signals = {}
    for ind_id, series_data in indicators.items():
        signals[ind_id] = generate_signal(ind_id, series_data, ohlcv_df)

    # Each signal should be valid
    for ind_id, sig in signals.items():
        assert sig in ("buy", "sell", "hold"), f"{ind_id} signal is '{sig}'"

    # Aggregate should be valid
    agg = aggregate_signals(signals)
    assert agg in ("buy", "sell", "hold")
