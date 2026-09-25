"""
Phase 6 — News intelligence pipeline.

Runs inside the 5am market pipeline:
  1. Collect headlines (Yahoo Finance + Google News per ticker; Fed + RBNZ)
  2. Deduplicate (same headline from several feeds = one story)
  3. Claude classifies each event, extracts entities, and reasons through
     direct → second → third order effects, scoring impact
  4. Every concrete claim becomes a hypothesis in hypothesis_log,
     graded later exactly like the technical signals
  5. Confidence is calibrated by Alfred's own track record per event type

Alfred never recommends trades. These are logged hypotheses, not advice.
"""
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus
import feedparser
import httpx
import yfinance as yf
from database import get_connection
from hypothesis import log_signals, calibrate_confidence, latest_completed_close, accuracy_stats
from llm import ask_structured

HEADERS = {"User-Agent": "Mozilla/5.0 (Alfred personal assistant)"}
MACRO_FEEDS = {
    "Federal Reserve": "https://www.federalreserve.gov/feeds/press_all.xml",
    "RBNZ": "https://www.rbnz.govt.nz/feeds/news",
}
MAX_AGE_HOURS = 36
MIN_IMPACT = 3.0

EVENT_TYPES = ["earnings", "m&a", "regulatory", "macro", "geopolitical", "insider", "product", "other"]

ANALYST_PROMPT = """
You are Alfred's news analyst. You read headlines and reason about
market consequences. You never recommend trades; you produce testable
hypotheses that will be graded against real prices later.

Signal phrases to watch for:
Earnings: beat, miss, guidance raised/lowered, profit warning, restatement
M&A: merger, acquisition, takeover, buyout, strategic alternatives, going private
Regulatory: FDA approved/rejected, SEC investigation, antitrust, sanctions, export controls
Macro: rate decision, inflation, jobs report, GDP, yield curve, credit downgrade
Geopolitical: military action, trade war, tariffs, supply chain, energy embargo
Insider: insider buying, 13D filing, activist, short seller report, fraud allegation

For every meaningful event, reason explicitly: direct effects → second
order → third order. Never stop at the headline implication. Name
ambiguous exposures as ambiguous rather than forcing a direction.

Group headlines about the same story into ONE event. Skip noise
(listicles, "3 stocks to buy", opinion with no new facts).

Hypotheses must use real ticker symbols Yahoo Finance recognises
(NZX stocks end in .NZ). Only include a hypothesis when you have a
genuine directional view; say low confidence when unsure.
Score magnitude, novelty, clarity and breadth 1-5 honestly.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "headline_ids": {"type": "array", "items": {"type": "string"}},
                    "summary": {"type": "string"},
                    "event_type": {"type": "string", "enum": EVENT_TYPES},
                    "sentiment": {"type": "string", "enum": ["positive", "negative", "mixed", "neutral"]},
                    "entities": {"type": "array", "items": {"type": "string"}},
                    "direct_effects": {"type": "string"},
                    "second_order": {"type": "string"},
                    "third_order": {"type": "string"},
                    "magnitude": {"type": "integer", "minimum": 1, "maximum": 5},
                    "novelty": {"type": "integer", "minimum": 1, "maximum": 5},
                    "clarity": {"type": "integer", "minimum": 1, "maximum": 5},
                    "breadth": {"type": "integer", "minimum": 1, "maximum": 5},
                    "hypotheses": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "symbol": {"type": "string"},
                                "direction": {"type": "string", "enum": ["bullish", "bearish"]},
                                "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                                "timeframe_days": {"type": "integer", "minimum": 1, "maximum": 30},
                                "reasoning": {"type": "string"},
                            },
                            "required": ["symbol", "direction", "confidence", "timeframe_days", "reasoning"],
                        },
                    },
                },
                "required": ["headline_ids", "summary", "event_type", "sentiment", "magnitude",
                             "novelty", "clarity", "breadth", "hypotheses"],
            },
        }
    },
    "required": ["events"],
}


# ---------- collecting ----------

def normalise_title(title):
    """'NVIDIA beats estimates - Reuters' and 'Nvidia Beats Estimates' → same key."""
    title = re.sub(r"\s+[-|–]\s+[^-|–]+$", "", title)   # drop trailing " - Source"
    return re.sub(r"[^a-z0-9 ]", "", title.lower()).strip()


def headline_id(title):
    return hashlib.sha256(normalise_title(title).encode()).hexdigest()[:16]


def ticker_feeds(symbol):
    name = symbol
    try:
        name = yf.Ticker(symbol).info.get("shortName") or symbol
    except Exception:
        pass
    query = quote_plus(f'"{name}" OR {symbol.split(".")[0]} stock')
    feeds = {f"Google News {symbol}": f"https://news.google.com/rss/search?q={query}&hl=en-NZ&gl=NZ&ceid=NZ:en"}
    if not symbol.endswith(".NZ"):
        feeds[f"Yahoo {symbol}"] = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
    return feeds


def is_recent(entry, now=None, max_age_hours=MAX_AGE_HOURS):
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    if not published:
        return True
    published_at = datetime(*published[:6], tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return now - published_at <= timedelta(hours=max_age_hours)


def collect_news(tickers):
    feeds = dict(MACRO_FEEDS)
    for symbol in tickers:
        feeds.update(ticker_feeds(symbol))

    conn = get_connection()
    new_items = 0
    with httpx.Client(timeout=15, headers=HEADERS, follow_redirects=True) as client:
        for source, url in feeds.items():
            try:
                parsed = feedparser.parse(client.get(url).text)
            except Exception as e:
                logging.warning(f"Feed failed {source}: {e}")
                continue
            for entry in parsed.entries[:20]:
                title = entry.get("title", "").strip()
                if not title or not is_recent(entry):
                    continue
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO news_items (id, fetched_at, published, source, title, link, query)
                    VALUES (?, datetime('now'), ?, ?, ?, ?, ?)
                    """,
                    (headline_id(title), entry.get("published", ""), source, title,
                     entry.get("link", ""), source),
                )
                new_items += cursor.rowcount
    conn.commit()
    conn.close()
    return new_items


# ---------- analysing ----------

def impact_score(event):
    return (event["magnitude"] + event["novelty"] + event["clarity"] + event["breadth"]) / 4


def analyse_news(tracked, max_items=40):
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, source, title FROM news_items WHERE processed = 0 ORDER BY fetched_at DESC LIMIT ?",
        (max_items,),
    ).fetchall()
    conn.close()
    if not rows:
        return []

    headlines = "\n".join(f"[{hid}] ({source}) {title}" for hid, source, title in rows)
    prompt = (
        f"Jay tracks: {', '.join(tracked)}.\n"
        f"Today's headlines (id in brackets):\n{headlines}\n\n"
        "Analyse the meaningful events."
    )
    result = ask_structured(ANALYST_PROMPT, prompt, "record_news_analysis",
                            "Record the structured analysis of today's news events.", SCHEMA)
    events = (result or {}).get("events", [])

    conn = get_connection()
    for hid, _, _ in rows:
        conn.execute("UPDATE news_items SET processed = 1 WHERE id = ?", (hid,))
    for event in events:
        for hid in event.get("headline_ids", []):
            conn.execute("UPDATE news_items SET analysis = ? WHERE id = ?", (json.dumps(event), hid))
    conn.commit()
    conn.close()
    return events


def events_to_signals(events, stats=None):
    """Turn significant events into hypothesis dicts (the same shape as
    market_signals produces), with calibrated confidence."""
    stats = accuracy_stats() if stats is None else stats
    signals = []
    for event in events:
        if impact_score(event) < MIN_IMPACT:
            continue
        for hyp in event.get("hypotheses", [])[:5]:
            symbol = hyp["symbol"].upper().strip()
            signal_date, entry_price = latest_completed_close(symbol)
            if entry_price is None:
                continue   # not a symbol Yahoo recognises
            signal_type = f"news_{event['event_type'].replace('&', '')}"
            confidence, note = calibrate_confidence(signal_type, hyp["confidence"], stats)
            signals.append({
                "symbol": symbol,
                "signal_type": signal_type,
                "direction": hyp["direction"],
                "confidence": confidence,
                "timeframe_days": hyp["timeframe_days"],
                "reasoning": (
                    f"{event['summary']} | {hyp['reasoning']}"
                    + (f" | 2nd order: {event.get('second_order', '')}" if event.get("second_order") else "")
                    + (f" | confidence {note}" if note else "")
                ),
                "entry_price": entry_price,
                "date": signal_date,
            })
    return signals


def run_news_pipeline(tracked):
    """Returns text for the market brief."""
    collected = collect_news(tracked)
    events = analyse_news(tracked)
    signals = events_to_signals(events)
    new_logged = log_signals(signals)

    significant = [e for e in events if impact_score(e) >= MIN_IMPACT]
    if not significant:
        return f"NEWS\nNo significant events ({collected} new headlines scanned)."
    lines = ["NEWS"]
    for event in sorted(significant, key=impact_score, reverse=True)[:6]:
        lines.append(
            f"[{event['event_type']}, impact {impact_score(event):.1f}/5, {event['sentiment']}] {event['summary']}\n"
            f"  direct: {event.get('direct_effects', '')}\n"
            f"  2nd order: {event.get('second_order', '')}\n"
            f"  3rd order: {event.get('third_order', '')}"
        )
    lines.append(f"({len(signals)} news hypotheses, {new_logged} newly logged)")
    return "\n".join(lines)
