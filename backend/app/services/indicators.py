"""Technical indicators service.

Calculates all 10 indicators from OHLCV DataFrames and generates
buy/sell/hold signals. These are synchronous CPU-bound functions;
callers should wrap in a thread executor for async contexts.
"""

import calendar
from collections import Counter

import pandas as pd
import pandas_ta as ta  # noqa: F401 — registers df.ta accessor


# ---------------------------------------------------------------------------
# Series key definitions (must match frontend expectations)
# ---------------------------------------------------------------------------

INDICATOR_SERIES_KEYS: dict[str, set[str]] = {
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

# Fibonacci retracement levels
_FIB_LEVELS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
_FIB_KEYS = ["fib_0", "fib_24", "fib_38", "fib_50", "fib_62", "fib_79", "fib_100"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ts(dt: pd.Timestamp) -> int:
    """Convert a pandas Timestamp to unix seconds (int)."""
    return int(calendar.timegm(dt.timetuple()))


def _series_to_points(
    series: pd.Series | None, index: pd.DatetimeIndex
) -> list[dict]:
    """Convert a pandas Series to [{time, value}] dicts, dropping NaN.

    Returns empty list if series is None or not a proper Series
    (pandas-ta may return the original DataFrame when length > data size).
    """
    if series is None or not isinstance(series, pd.Series):
        return []
    mask = series.notna()
    times = index[mask]
    values = series[mask]
    return [
        {"time": _ts(t), "value": float(v)}
        for t, v in zip(times, values)
    ]


# ---------------------------------------------------------------------------
# calculate_indicators
# ---------------------------------------------------------------------------


def calculate_indicators(df: pd.DataFrame) -> dict[str, dict[str, list[dict]]]:
    """Calculate all 10 indicators from an OHLCV DataFrame.

    Args:
        df: DataFrame with DatetimeIndex and columns: Open, High, Low, Close, Volume.

    Returns:
        {indicator_id: {series_key: [{time: unix_s, value: float}]}}
    """
    idx = df.index
    result: dict[str, dict[str, list[dict]]] = {}

    # RSI (14)
    rsi = df.ta.rsi(length=14)
    result["rsi"] = {"rsi": _series_to_points(rsi, idx)}

    # MACD (12, 26, 9)
    macd_df = df.ta.macd(fast=12, slow=26, signal=9)
    if macd_df is not None and isinstance(macd_df, pd.DataFrame):
        result["macd"] = {
            "macd": _series_to_points(macd_df.iloc[:, 0], idx),
            "signal": _series_to_points(macd_df.iloc[:, 1], idx),
            "histogram": _series_to_points(macd_df.iloc[:, 2], idx),
        }
    else:
        result["macd"] = {"macd": [], "signal": [], "histogram": []}

    # Bollinger Bands (20, 2)
    bb_df = df.ta.bbands(length=20, std=2)
    if bb_df is not None and isinstance(bb_df, pd.DataFrame):
        result["bollinger"] = {
            "lower": _series_to_points(bb_df.iloc[:, 0], idx),
            "middle": _series_to_points(bb_df.iloc[:, 1], idx),
            "upper": _series_to_points(bb_df.iloc[:, 2], idx),
        }
    else:
        result["bollinger"] = {"upper": [], "middle": [], "lower": []}

    # Moving Averages
    sma20 = df.ta.sma(length=20)
    sma50 = df.ta.sma(length=50)
    sma200 = df.ta.sma(length=200)
    result["ma"] = {
        "sma20": _series_to_points(sma20, idx),
        "sma50": _series_to_points(sma50, idx),
        "sma200": _series_to_points(sma200, idx),
    }

    # Stochastic (14, 3, 3)
    stoch_df = df.ta.stoch(k=14, d=3, smooth_k=3)
    if stoch_df is not None and isinstance(stoch_df, pd.DataFrame):
        result["stochastic"] = {
            "k": _series_to_points(stoch_df.iloc[:, 0], idx),
            "d": _series_to_points(stoch_df.iloc[:, 1], idx),
        }
    else:
        result["stochastic"] = {"k": [], "d": []}

    # OBV
    obv = df.ta.obv()
    result["obv"] = {"obv": _series_to_points(obv, idx)}

    # Fibonacci (from period high/low)
    result["fibonacci"] = _calculate_fibonacci(df)

    # ATR (14)
    atr = df.ta.atr(length=14)
    result["atr"] = {"atr": _series_to_points(atr, idx)}

    # Ichimoku (9, 26, 52)
    ichimoku_result = df.ta.ichimoku(tenkan=9, kijun=26, senkou=52)
    # pandas-ta returns a tuple of (span_df, forward_df) or None
    ichi_df = None
    if ichimoku_result is not None:
        if isinstance(ichimoku_result, tuple):
            ichi_df = ichimoku_result[0]
        elif isinstance(ichimoku_result, pd.DataFrame):
            ichi_df = ichimoku_result

    if ichi_df is not None and isinstance(ichi_df, pd.DataFrame):
        # Column names from pandas-ta: ITS_9, IKS_26, ISA_9, ISB_26, ICS_26
        tenkan_cols = ichi_df.filter(like="ITS")
        kijun_cols = ichi_df.filter(like="IKS")
        result["ichimoku"] = {
            "tenkan": _series_to_points(
                tenkan_cols.iloc[:, 0] if len(tenkan_cols.columns) > 0 else None, idx
            ),
            "kijun": _series_to_points(
                kijun_cols.iloc[:, 0] if len(kijun_cols.columns) > 0 else None, idx
            ),
        }
    else:
        result["ichimoku"] = {"tenkan": [], "kijun": []}

    # CCI (20)
    cci = df.ta.cci(length=20)
    result["cci"] = {"cci": _series_to_points(cci, idx)}

    return result


def _calculate_fibonacci(df: pd.DataFrame) -> dict[str, list[dict]]:
    """Calculate Fibonacci retracement levels from the period's high/low range."""
    idx = df.index
    period_high = float(df["High"].max())
    period_low = float(df["Low"].min())
    diff = period_high - period_low

    series: dict[str, list[dict]] = {}
    for key, level in zip(_FIB_KEYS, _FIB_LEVELS):
        value = round(period_high - diff * level, 6)
        series[key] = [{"time": _ts(t), "value": value} for t in idx]

    return series


# ---------------------------------------------------------------------------
# generate_signal
# ---------------------------------------------------------------------------


def generate_signal(
    indicator_id: str,
    series_data: dict[str, list[dict]],
    df: pd.DataFrame | None = None,
) -> str:
    """Evaluate indicator output against thresholds.

    Args:
        indicator_id: One of the 10 indicator IDs.
        series_data: {series_key: [{time, value}]} for this indicator.
        df: Original OHLCV DataFrame (needed for Bollinger, MA, Ichimoku, Fibonacci).

    Returns:
        'buy', 'sell', or 'hold'.
    """
    try:
        match indicator_id:
            case "rsi":
                return _signal_rsi(series_data)
            case "macd":
                return _signal_macd(series_data)
            case "bollinger":
                return _signal_bollinger(series_data, df)
            case "ma":
                return _signal_ma(series_data, df)
            case "stochastic":
                return _signal_stochastic(series_data)
            case "obv":
                return _signal_obv(series_data)
            case "fibonacci":
                return _signal_fibonacci(series_data, df)
            case "atr":
                return "hold"  # ATR is volatility — no directional signal
            case "ichimoku":
                return _signal_ichimoku(series_data, df)
            case "cci":
                return _signal_cci(series_data)
            case _:
                return "hold"
    except (KeyError, IndexError, TypeError):
        return "hold"


def _last_value(points: list[dict]) -> float:
    """Get the last value from a series point list."""
    return float(points[-1]["value"])


def _signal_rsi(data: dict) -> str:
    rsi = _last_value(data["rsi"])
    if rsi < 30:
        return "buy"
    elif rsi > 70:
        return "sell"
    return "hold"


def _signal_macd(data: dict) -> str:
    macd = _last_value(data["macd"])
    signal = _last_value(data["signal"])
    if macd > signal:
        return "buy"
    elif macd < signal:
        return "sell"
    return "hold"


def _signal_bollinger(data: dict, df: pd.DataFrame | None) -> str:
    if df is None:
        return "hold"
    close = float(df["Close"].iloc[-1])
    lower = _last_value(data["lower"])
    upper = _last_value(data["upper"])
    if close < lower:
        return "buy"
    elif close > upper:
        return "sell"
    return "hold"


def _signal_ma(data: dict, df: pd.DataFrame | None) -> str:
    if df is None:
        return "hold"
    close = float(df["Close"].iloc[-1])
    sma50 = _last_value(data["sma50"])
    sma200 = _last_value(data["sma200"])
    if close > sma200 and sma50 > sma200:
        return "buy"
    elif close < sma200 and sma50 < sma200:
        return "sell"
    return "hold"


def _signal_stochastic(data: dict) -> str:
    k = _last_value(data["k"])
    if k < 20:
        return "buy"
    elif k > 80:
        return "sell"
    return "hold"


def _signal_obv(data: dict) -> str:
    points = data["obv"]
    if len(points) < 5:
        return "hold"
    # Compare last 5 points for trend direction
    recent = [p["value"] for p in points[-5:]]
    rising = all(recent[i] <= recent[i + 1] for i in range(len(recent) - 1))
    falling = all(recent[i] >= recent[i + 1] for i in range(len(recent) - 1))
    if rising:
        return "buy"
    elif falling:
        return "sell"
    return "hold"


def _signal_fibonacci(data: dict, df: pd.DataFrame | None) -> str:
    if df is None:
        return "hold"

    close = float(df["Close"].iloc[-1])
    levels = sorted(
        [_last_value(data[k]) for k in data],
        reverse=True,
    )

    if len(levels) < 2:
        return "hold"

    total_range = levels[0] - levels[-1]
    if total_range == 0:
        return "hold"

    # Find the nearest level to the current close
    nearest = min(levels, key=lambda lv: abs(lv - close))
    distance = abs(close - nearest)

    # "Near" means within 2% of the total range
    threshold = total_range * 0.02
    if distance > threshold:
        return "hold"

    # Support levels are in the lower half, resistance in the upper half
    mid = (levels[0] + levels[-1]) / 2
    if nearest < mid:
        return "buy"   # Near a support level
    elif nearest > mid:
        return "sell"  # Near a resistance level

    return "hold"


def _signal_ichimoku(data: dict, df: pd.DataFrame | None) -> str:
    if df is None:
        return "hold"
    close = float(df["Close"].iloc[-1])
    tenkan = _last_value(data["tenkan"])
    kijun = _last_value(data["kijun"])
    cloud_top = max(tenkan, kijun)
    cloud_bottom = min(tenkan, kijun)
    if close > cloud_top:
        return "buy"
    elif close < cloud_bottom:
        return "sell"
    return "hold"


def _signal_cci(data: dict) -> str:
    cci = _last_value(data["cci"])
    if cci < -100:
        return "buy"
    elif cci > 100:
        return "sell"
    return "hold"


# ---------------------------------------------------------------------------
# aggregate_signals
# ---------------------------------------------------------------------------


def aggregate_signals(signals: dict[str, str]) -> str:
    """Majority vote across all indicator signals.

    Args:
        signals: {indicator_id: 'buy'|'sell'|'hold'}

    Returns:
        'buy', 'sell', or 'hold'. Ties resolve to 'hold'.
    """
    if not signals:
        return "hold"

    counts = Counter(signals.values())
    buy = counts.get("buy", 0)
    sell = counts.get("sell", 0)
    hold = counts.get("hold", 0)

    if buy > sell and buy > hold:
        return "buy"
    elif sell > buy and sell > hold:
        return "sell"
    return "hold"
