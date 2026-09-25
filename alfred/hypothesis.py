"""
Milestone 7 — Alfred keeps score of itself.

Every signal becomes a hypothesis row ("TSLA bullish over 5 days").
Once enough trading days have passed, evaluate_hypotheses() looks up
what the price actually did and marks each one accurate or not.
accuracy_report() turns that history into honest numbers.
"""
from datetime import datetime, timedelta
import yfinance as yf
from database import get_connection


def log_signals(signals):
    """Save signals to hypothesis_log. Returns how many were new.

    INSERT OR IGNORE + the UNIQUE(date, symbol, signal_type) constraint
    means running the pipeline twice on the same day can't double-log.
    """
    conn = get_connection()
    cursor = conn.cursor()
    new_rows = 0
    for s in signals:
        cursor.execute(
            """
            INSERT OR IGNORE INTO hypothesis_log
                (date, symbol, signal_type, direction, reasoning,
                 confidence, timeframe_days, entry_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                s["date"], s["symbol"], s["signal_type"], s["direction"],
                s["reasoning"], s["confidence"], s["timeframe_days"], s["entry_price"],
            ),
        )
        new_rows += cursor.rowcount
    conn.commit()
    conn.close()
    return new_rows


def grade(direction, entry_price, result_price):
    """Return (return_percent, accurate).

    accurate is 1 (right), 0 (wrong) or None (neutral signals
    don't predict a direction, so there's nothing to grade).
    """
    return_percent = (result_price - entry_price) / entry_price * 100
    if direction == "bullish":
        return return_percent, int(return_percent > 0)
    if direction == "bearish":
        return return_percent, int(return_percent < 0)
    return return_percent, None


def price_after(closes, signal_date, trading_days):
    """Close price `trading_days` bars after signal_date, or None if
    not enough days have passed yet.

    closes: pandas Series of closing prices indexed by date.
    """
    dates = [d.strftime("%Y-%m-%d") for d in closes.index]
    if signal_date not in dates:
        return None
    position = dates.index(signal_date) + trading_days
    if position >= len(closes):
        return None
    return float(closes.iloc[position])


def evaluate_hypotheses():
    """Grade every hypothesis whose timeframe has passed. Returns count graded."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, date, symbol, direction, timeframe_days, entry_price
        FROM hypothesis_log WHERE evaluated_at IS NULL
        ORDER BY date, id
        """
        # ORDER BY date matters: the first row per symbol sets the price-history
        # start date in history_cache. If a later-dated row came first, earlier
        # rows would never find their date and would silently never be graded.
    )
    pending = cursor.fetchall()
    graded = 0
    history_cache = {}

    for row_id, signal_date, symbol, direction, timeframe, entry_price in pending:
        if symbol not in history_cache:
            start = datetime.fromisoformat(signal_date) - timedelta(days=5)
            history_cache[symbol] = yf.Ticker(symbol).history(start=start.strftime("%Y-%m-%d"))
        hist = history_cache[symbol]
        if hist.empty:
            continue
        result_price = price_after(hist["Close"], signal_date, timeframe)
        if result_price is None:
            continue
        return_percent, accurate = grade(direction, entry_price, result_price)
        cursor.execute(
            """
            UPDATE hypothesis_log
            SET result_price = ?, return_percent = ?, accurate = ?, evaluated_at = datetime('now')
            WHERE id = ?
            """,
            (result_price, round(return_percent, 3), accurate, row_id),
        )
        graded += 1

    conn.commit()
    conn.close()
    return graded


def accuracy_stats():
    """Per-signal-type accuracy: {signal_type: (correct, total)}."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT signal_type, SUM(accurate), COUNT(*)
        FROM hypothesis_log
        WHERE accurate IS NOT NULL
        GROUP BY signal_type
        ORDER BY COUNT(*) DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return {signal_type: (int(correct), total) for signal_type, correct, total in rows}


CONFIDENCE_LEVELS = ["low", "medium", "high"]
MIN_SAMPLE_FOR_CALIBRATION = 20


def calibrate_confidence(signal_type, base_confidence, stats=None):
    """Adjust confidence using Alfred's OWN track record for this signal type.

    Under 20 graded signals: no change (not enough evidence).
    Right < 50% of the time: one level down (worse than a coin flip).
    Right >= 60%: one level up.
    Returns (confidence, note).
    """
    stats = accuracy_stats() if stats is None else stats
    if signal_type not in stats:
        return base_confidence, ""
    correct, total = stats[signal_type]
    if total < MIN_SAMPLE_FOR_CALIBRATION:
        return base_confidence, ""
    rate = correct / total
    index = CONFIDENCE_LEVELS.index(base_confidence)
    if rate < 0.5 and index > 0:
        return CONFIDENCE_LEVELS[index - 1], f"downgraded: {rate:.0%} over {total}"
    if rate >= 0.6 and index < len(CONFIDENCE_LEVELS) - 1:
        return CONFIDENCE_LEVELS[index + 1], f"upgraded: {rate:.0%} over {total}"
    return base_confidence, ""


def latest_completed_close(symbol):
    """(date_str, close) for the last FINISHED trading day — the entry point
    for news hypotheses, which have no DataFrame of their own."""
    from market_signals import drop_incomplete_bar
    hist = drop_incomplete_bar(yf.Ticker(symbol).history(period="10d"))
    if hist.empty:
        return None, None
    return hist.index[-1].strftime("%Y-%m-%d"), round(float(hist["Close"].iloc[-1]), 4)


def accuracy_report():
    stats = accuracy_stats()
    if not stats:
        conn = get_connection()
        pending = conn.execute("SELECT COUNT(*) FROM hypothesis_log").fetchone()[0]
        conn.close()
        return (
            f"No graded predictions yet. {pending} signal(s) logged and waiting "
            "for their timeframe to pass."
        )
    lines = []
    total_correct = total_all = 0
    for signal_type, (correct, total) in stats.items():
        pct = correct / total * 100
        note = " (too few to judge)" if total < 10 else ""
        lines.append(f"{signal_type}: {pct:.0f}% right over {total} signals{note}")
        total_correct += correct
        total_all += total
    lines.append(f"Overall: {total_correct / total_all * 100:.0f}% over {total_all} graded signals")
    return "\n".join(lines)


def recent_signals(days=7):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT date, symbol, signal_type, direction, reasoning
        FROM hypothesis_log
        WHERE date >= date('now', ?)
        ORDER BY date DESC, symbol
        """,
        (f"-{days} days",),
    )
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        return f"No signals in the last {days} days."
    return "\n".join(f"{d} {sym} {st} ({direction}): {why}" for d, sym, st, direction, why in rows)
