from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from market_signals import scan_signals, drop_incomplete_bar, add_indicators


def make_prices(closes, volume=1_000_000, opens=None):
    """Build a yfinance-shaped DataFrame from a list of closing prices."""
    closes = np.asarray(closes, dtype=float)
    index = pd.date_range("2025-01-01", periods=len(closes), freq="B", tz="America/New_York")
    opens = closes if opens is None else np.asarray(opens, dtype=float)
    volumes = np.full(len(closes), volume, dtype=float) if np.isscalar(volume) else volume
    return pd.DataFrame(
        {
            "Open": opens,
            "High": np.maximum(opens, closes) + 0.5,
            "Low": np.minimum(opens, closes) - 0.5,
            "Close": closes,
            "Volume": volumes,
        },
        index=index,
    )


def signal_types(df):
    return {s["signal_type"] for s in scan_signals(df, "TEST")}


def test_too_little_data_returns_nothing():
    assert scan_signals(make_prices([100] * 10), "TEST") == []


def test_rsi_oversold_after_long_decline():
    closes = list(np.linspace(200, 100, 60))
    assert "rsi_oversold" in signal_types(make_prices(closes))


def test_rsi_overbought_after_long_rise():
    closes = list(np.linspace(100, 200, 60))
    assert "rsi_overbought" in signal_types(make_prices(closes))


def test_ema_bull_cross_after_downtrend_reverses():
    # Fall for 40 days, then rally hard until the fast EMA crosses the slow one
    closes = list(np.linspace(150, 100, 40))
    df = None
    for price in np.linspace(101, 140, 30):
        closes.append(price)
        df = make_prices(closes)
        if "ema_9_21_bull_cross" in signal_types(df):
            break
    assert "ema_9_21_bull_cross" in signal_types(df)


def test_volume_spike_on_up_day_is_bullish():
    closes = [100.0] * 40 + [103.0]
    opens = [100.0] * 40 + [100.5]
    volume = np.array([1_000_000.0] * 40 + [3_500_000.0])
    signals = scan_signals(make_prices(closes, volume=volume, opens=opens), "TEST")
    spike = [s for s in signals if s["signal_type"] == "volume_spike"]
    assert spike and spike[0]["direction"] == "bullish"


def test_gap_up_detected():
    closes = [100.0] * 40 + [104.0]
    opens = [100.0] * 40 + [103.0]  # opened 3% above yesterday's 100 close
    assert "gap_up" in signal_types(make_prices(closes, opens=opens))


def test_flat_market_fires_nothing_directional():
    rng = np.random.default_rng(0)
    closes = 100 + rng.normal(0, 0.05, 60).cumsum()
    fired = signal_types(make_prices(closes))
    assert not fired & {"rsi_oversold", "rsi_overbought", "gap_up", "gap_down", "volume_spike"}


def test_signal_has_everything_hypothesis_log_needs():
    closes = list(np.linspace(200, 100, 60))
    signal = scan_signals(make_prices(closes), "ABC")[0]
    for key in ("symbol", "signal_type", "direction", "confidence", "timeframe_days",
                "reasoning", "entry_price", "date"):
        assert key in signal


def test_indicator_columns_added():
    df = add_indicators(make_prices(np.linspace(100, 120, 60)))
    for col in ("rsi", "ema9", "ema21", "atr", "volume_avg20", "bb_width"):
        assert col in df.columns


def test_drop_incomplete_bar_while_market_open():
    df = make_prices([100] * 5)
    last_day = df.index[-1]
    during_session = last_day.replace(hour=11)
    assert len(drop_incomplete_bar(df, now=during_session)) == 4


def test_keep_bar_after_market_close():
    df = make_prices([100] * 5)
    after_close = df.index[-1].replace(hour=17)
    assert len(drop_incomplete_bar(df, now=after_close)) == 5


def test_keep_bar_on_a_later_day():
    df = make_prices([100] * 5)
    next_morning = datetime(2030, 1, 1, 9, tzinfo=ZoneInfo("America/New_York"))
    assert len(drop_incomplete_bar(df, now=next_morning)) == 5
