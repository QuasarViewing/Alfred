"""
Milestone 7 — technical indicators and the signal scanner.

Everything in here is pure: a DataFrame of daily prices goes in,
indicators / signals come out. No internet, no database. That makes
it easy to test with fake data (see tests/test_market_signals.py).

Expected input columns (what yfinance returns):
    Open, High, Low, Close, Volume   — one row per trading day
"""
from datetime import datetime
import pandas as pd
import pandas_ta as ta


# How many trading days each signal type is judged over,
# and how confident Alfred is in it before any track record exists.
SIGNAL_RULES = {
    "ema_9_21_bull_cross": {"direction": "bullish", "timeframe": 5, "confidence": "medium"},
    "ema_9_21_bear_cross": {"direction": "bearish", "timeframe": 5, "confidence": "medium"},
    "golden_cross": {"direction": "bullish", "timeframe": 20, "confidence": "medium"},
    "death_cross": {"direction": "bearish", "timeframe": 20, "confidence": "medium"},
    "rsi_oversold": {"direction": "bullish", "timeframe": 5, "confidence": "low"},
    "rsi_overbought": {"direction": "bearish", "timeframe": 5, "confidence": "low"},
    "volume_spike": {"direction": None, "timeframe": 5, "confidence": "low"},
    "gap_up": {"direction": "bullish", "timeframe": 3, "confidence": "low"},
    "gap_down": {"direction": "bearish", "timeframe": 3, "confidence": "low"},
    "atr_expansion": {"direction": "neutral", "timeframe": 5, "confidence": "low"},
    "new_52w_high": {"direction": "bullish", "timeframe": 10, "confidence": "medium"},
    "bollinger_squeeze": {"direction": "neutral", "timeframe": 10, "confidence": "low"},
}


def drop_incomplete_bar(df, now=None, close_hour=16):
    """Remove today's row if the market it trades on hasn't closed yet.

    Alfred's pipeline runs at 5am NZ time — which is mid-afternoon in
    New York, so the US market is still open and the last row is a
    half-finished day. Signals must only use finished days.
    """
    if df.empty or df.index.tz is None:
        return df
    now = now or datetime.now(df.index.tz)
    last_day = df.index[-1].date()
    if last_day == now.date() and now.hour < close_hour:
        return df.iloc[:-1]
    return df


def add_indicators(df):
    """Return a copy of df with indicator columns added."""
    df = df.copy()
    close = df["Close"]

    df["rsi"] = ta.rsi(close, length=14)
    df["ema9"] = ta.ema(close, length=9)
    df["ema21"] = ta.ema(close, length=21)
    df["ema50"] = ta.ema(close, length=50)
    df["ema200"] = ta.ema(close, length=200)
    df["atr"] = ta.atr(df["High"], df["Low"], close, length=14)
    df["atr_avg20"] = df["atr"].rolling(20).mean()
    df["volume_avg20"] = df["Volume"].rolling(20).mean().shift(1)
    df["high_52w"] = df["High"].rolling(252, min_periods=200).max().shift(1)

    bands = ta.bbands(close, length=20)
    bandwidth_col = [c for c in bands.columns if c.startswith("BBB")][0]
    df["bb_width"] = bands[bandwidth_col]
    df["bb_width_min120"] = df["bb_width"].rolling(120, min_periods=60).min()

    return df


def _crossed_above(fast, slow):
    """True if `fast` was below `slow` yesterday and is above today."""
    return fast.iloc[-2] <= slow.iloc[-2] and fast.iloc[-1] > slow.iloc[-1]


def _crossed_below(fast, slow):
    return fast.iloc[-2] >= slow.iloc[-2] and fast.iloc[-1] < slow.iloc[-1]


def scan_signals(df, symbol):
    """Check the most recent day for every signal condition.

    Returns a list of dicts, one per signal that fired.
    """
    if len(df) < 30:
        return []

    df = add_indicators(df)
    today = df.iloc[-1]
    yesterday = df.iloc[-2]
    fired = []

    def add(signal_type, reasoning, direction=None):
        rule = SIGNAL_RULES[signal_type]
        fired.append({
            "symbol": symbol,
            "signal_type": signal_type,
            "direction": direction or rule["direction"],
            "confidence": rule["confidence"],
            "timeframe_days": rule["timeframe"],
            "reasoning": reasoning,
            "entry_price": round(float(today["Close"]), 4),
            "date": df.index[-1].strftime("%Y-%m-%d"),
        })

    # MOMENTUM — EMA crossovers
    if _crossed_above(df["ema9"], df["ema21"]):
        add("ema_9_21_bull_cross", "9-day EMA crossed above 21-day EMA")
    if _crossed_below(df["ema9"], df["ema21"]):
        add("ema_9_21_bear_cross", "9-day EMA crossed below 21-day EMA")
    if df["ema200"].notna().iloc[-2]:
        if _crossed_above(df["ema50"], df["ema200"]):
            add("golden_cross", "50-day EMA crossed above 200-day EMA (golden cross)")
        if _crossed_below(df["ema50"], df["ema200"]):
            add("death_cross", "50-day EMA crossed below 200-day EMA (death cross)")

    # RSI
    if today["rsi"] < 30:
        add("rsi_oversold", f"RSI(14) is {today['rsi']:.1f}, below 30")
    elif today["rsi"] > 70:
        add("rsi_overbought", f"RSI(14) is {today['rsi']:.1f}, above 70")

    # VOLUME — direction follows the day's candle
    if pd.notna(today["volume_avg20"]) and today["Volume"] > 2 * today["volume_avg20"]:
        ratio = today["Volume"] / today["volume_avg20"]
        candle = "bullish" if today["Close"] >= today["Open"] else "bearish"
        add("volume_spike", f"Volume {ratio:.1f}x its 20-day average on a {candle} day", candle)

    # PRICE — gaps and new highs
    gap = (today["Open"] - yesterday["Close"]) / yesterday["Close"] * 100
    if gap > 1.5:
        add("gap_up", f"Opened {gap:.1f}% above the previous close")
    elif gap < -1.5:
        add("gap_down", f"Opened {abs(gap):.1f}% below the previous close")
    if pd.notna(today["high_52w"]) and today["Close"] > today["high_52w"]:
        add("new_52w_high", f"Closed at a new 52-week high ({today['Close']:.2f})")

    # VOLATILITY
    if pd.notna(today["atr_avg20"]) and today["atr"] > 1.5 * today["atr_avg20"]:
        add("atr_expansion", f"ATR(14) is {today['atr'] / today['atr_avg20']:.1f}x its 20-day average")
    if pd.notna(today["bb_width_min120"]) and today["bb_width"] <= today["bb_width_min120"]:
        add("bollinger_squeeze", "Bollinger Band width at a 6-month low — volatility compressed")

    return fired


def summarise_indicators(df, symbol):
    """One-line snapshot for the brief, even when no signal fires."""
    df = add_indicators(df)
    t = df.iloc[-1]
    change = (t["Close"] / df["Close"].iloc[-2] - 1) * 100
    trend = "above" if t["Close"] > t["ema50"] else "below"
    return (
        f"{symbol}: {t['Close']:.2f} ({change:+.1f}% day), RSI {t['rsi']:.0f}, "
        f"{trend} 50-day EMA"
    )
