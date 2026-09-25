import pandas as pd
from hypothesis import grade, price_after


def test_bullish_right_when_price_rises():
    return_percent, accurate = grade("bullish", 100, 105)
    assert accurate == 1 and round(return_percent, 2) == 5.0


def test_bullish_wrong_when_price_falls():
    assert grade("bullish", 100, 95)[1] == 0


def test_bearish_right_when_price_falls():
    assert grade("bearish", 100, 90)[1] == 1


def test_neutral_is_not_graded():
    assert grade("neutral", 100, 120)[1] is None


def _closes():
    index = pd.to_datetime(["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04", "2026-09-07"])
    return pd.Series([10.0, 11.0, 12.0, 13.0, 14.0], index=index)


def test_price_after_counts_trading_days():
    assert price_after(_closes(), "2026-09-01", 3) == 13.0


def test_price_after_returns_none_if_too_soon():
    assert price_after(_closes(), "2026-09-04", 5) is None


def test_price_after_unknown_date():
    assert price_after(_closes(), "2026-08-01", 1) is None


def test_grades_rows_logged_out_of_date_order(temp_db, monkeypatch):
    """A later-dated signal logged FIRST must not stop an earlier one being graded."""
    import hypothesis

    closes = pd.Series(
        [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0],
        index=pd.to_datetime(["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04",
                              "2026-09-07", "2026-09-08", "2026-09-09"]),
    )

    class FakeTicker:
        def __init__(self, symbol):
            pass

        def history(self, start):
            # like yfinance: only rows on/after the requested start date
            return pd.DataFrame({"Close": closes[closes.index >= start]})

    monkeypatch.setattr(hypothesis.yf, "Ticker", FakeTicker)

    def signal(day):
        return {"date": day, "symbol": "ABC", "signal_type": f"test_{day}", "direction": "bullish",
                "reasoning": "t", "confidence": "low", "timeframe_days": 1, "entry_price": 10.0}

    hypothesis.log_signals([signal("2026-09-08")])   # logged first, later date
    hypothesis.log_signals([signal("2026-09-01")])   # logged second, earlier date
    assert hypothesis.evaluate_hypotheses() == 2


def test_log_signals_ignores_duplicates(temp_db):
    from hypothesis import log_signals, accuracy_report
    signal = {
        "date": "2026-09-01", "symbol": "ABC", "signal_type": "gap_up",
        "direction": "bullish", "reasoning": "test", "confidence": "low",
        "timeframe_days": 3, "entry_price": 10.0,
    }
    assert log_signals([signal]) == 1
    assert log_signals([signal]) == 0  # same day, same signal — not logged twice
    assert "1 signal(s) logged" in accuracy_report()
