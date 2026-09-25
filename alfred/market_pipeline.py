"""
Milestone 7 — the overnight market pipeline.

Runs at 5am NZ time (APScheduler, see bot.py):
  1. Grade old predictions whose timeframe has passed
  2. Download a year of daily prices for every tracked ticker
  3. Scan for signals, log each one as a hypothesis
  4. Ask Claude to turn signals + track record into a short brief
  5. Save the brief — the 7am morning brief picks it up

Run it by hand any time:  py market_pipeline.py
"""
import logging
import yfinance as yf
from database import init_db, save_market_brief, log_task
from finance_tool import get_tracked_tickers
from market_signals import drop_incomplete_bar, scan_signals, summarise_indicators
from hypothesis import log_signals, evaluate_hypotheses, accuracy_report, accuracy_stats, calibrate_confidence
from llm import ask_once

MARKET_SYSTEM_PROMPT = """
You are Alfred, writing the market section of Jay's morning brief.
It will be read aloud, so write plain sentences — no tables, no bullet symbols.
Keep it under 250 words: market context first, then the top signals and
news events, then Alfred's recent accuracy on similar signals.
For news, give the second-order effect in one sentence where it's interesting.

Rules you never break:
- Factual. Describe what the indicators show, never recommend buying or selling.
- Never express certainty about what a price will do.
- When you mention a signal type, mention Alfred's track record on it
  if there is one — including when that record is poor.
- If there are no signals, say so briefly and summarise the snapshot.

Format with Telegram HTML only: <b>bold</b> and <i>italic</i>.
"""


def scan_ticker(symbol):
    hist = yf.Ticker(symbol).history(period="1y")
    hist = drop_incomplete_bar(hist)
    if len(hist) < 30:
        return None, [], f"{symbol}: not enough price history"
    return hist, scan_signals(hist, symbol), summarise_indicators(hist, symbol)


def run_market_pipeline(send_to_claude=True, include_news=None):
    # News needs Claude to analyse headlines, so it follows send_to_claude by default
    include_news = send_to_claude if include_news is None else include_news
    tickers = get_tracked_tickers()
    if not tickers:
        return "Nothing on your watchlist or portfolio to scan."

    graded = evaluate_hypotheses()

    all_signals = []
    snapshots = []
    for symbol in tickers:
        try:
            _, signals, snapshot = scan_ticker(symbol)
            all_signals.extend(signals)
            snapshots.append(snapshot)
        except Exception as e:
            logging.error(f"Market scan failed for {symbol}: {e}")
            snapshots.append(f"{symbol}: data unavailable")

    # Phase 6: confidence follows Alfred's own track record per signal type
    stats = accuracy_stats()
    for signal in all_signals:
        signal["confidence"], note = calibrate_confidence(signal["signal_type"], signal["confidence"], stats)
        if note:
            signal["reasoning"] += f" (confidence {note})"

    new_logged = log_signals(all_signals)

    news_text = ""
    if include_news:
        try:
            from news_pipeline import run_news_pipeline
            news_text = run_news_pipeline(tickers)
        except Exception as e:
            logging.exception("News pipeline failed")
            news_text = f"NEWS\nNews scan failed: {e}"

    track_record = accuracy_report()

    signal_lines = [
        f"{s['symbol']} — {s['signal_type']} ({s['direction']}, {s['confidence']} confidence, "
        f"{s['timeframe_days']}-day view): {s['reasoning']}"
        for s in all_signals
    ] or ["No signals fired today."]

    raw = (
        "SIGNALS\n" + "\n".join(signal_lines)
        + "\n\nSNAPSHOT\n" + "\n".join(snapshots)
        + (f"\n\n{news_text}" if news_text else "")
        + "\n\nALFRED'S TRACK RECORD\n" + track_record
    )

    if send_to_claude:
        brief = ask_once(MARKET_SYSTEM_PROMPT, raw)
    else:
        brief = raw

    save_market_brief(brief)
    log_task(
        "market_pipeline",
        f"{len(tickers)} tickers, {len(all_signals)} signals, {new_logged} new, {graded} graded",
        "success",
    )
    return brief


if __name__ == "__main__":
    init_db()
    print(run_market_pipeline(send_to_claude=False))
