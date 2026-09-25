"""
Phase 4 — The life intelligence layer.

"Alfred is a clarity system, not surveillance."

Daily at 18:00 NZ:
  1. gather_context()  — health vs baseline, activity rhythm, calendar
                         load, learning, thinking sessions, money, and
                         Jay's own recent words (stated values)
  2. Claude runs the 11-step inference and proposes observations,
     each with a tier 1-5
  3. EVERY observation is logged (tier 1-2 = log only, silent)
  4. should_surface() — the minimum bar, enforced in CODE:
       5+ data points, 2+ domains, no known explanation, actionable,
       nothing surfaced in the last 7 days, 7am-9pm, calendar not slammed
     Tier 5 (immediate concern) skips the timing rules.
  5. At most ONE observation is surfaced, kindly, as a question

Self-reflection: Jay rates surfaced observations (rate_observation).
If recent surfaced observations are mostly wrong, the bar rises to tier 4.

Reviews: weekly (Sunday 19:00), monthly (1st, 09:00), quarterly.
Alfred is not a clinician and never diagnoses.
"""
import json
import logging
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from config import TIMEZONE
from database import get_connection, get_all_preferences, log_task
from health import METRICS, get_health_summary, metric_trend
from llm import ask_structured, ask_once

NZ = ZoneInfo(TIMEZONE)
QUIET_START, QUIET_END = 21, 7        # never interrupt 9pm–7am
COOLDOWN_DAYS = 7
MIN_DATA_POINTS = 5
MIN_DOMAINS = 2
DOMAINS = ["sleep", "energy", "mood", "health", "work", "learning", "social",
           "money", "routine", "thinking", "values"]

INFERENCE_PROMPT = """
You are Alfred's inference engine. You look at Jay's data for honest,
longitudinal patterns — not what he thinks is happening, what the data shows.
You are a mirror, not a judge. You are not a clinician and never diagnose.

For each candidate pattern, work through internally:
1 OBSERVATION: the raw signal.  2 SIGNIFICANCE: meaningful vs HIS baseline?
3 CONTEXT: is there a known explanation (holiday, deadline, illness he mentioned)?
4 HISTORY: seen before? (check past observations)  5 CORRELATION: do several domains align?
6 ALTERNATIVES: what else explains it?  7 ACTIONABILITY: can Jay do anything?
8 TIMING: right moment?  9 HUMILITY: within your competence?
10 DRAFT: write it kindly  11 decide the tier.

Tiers:
1 soft signal (log only) · 2 pattern forming (watch) · 3 significant pattern (worth raising)
4 serious pattern (raise soon) · 5 immediate concern (raise now, gently)

Be conservative. Most days produce nothing above tier 2 — that is correct.
Count data_points honestly (actual logged values / days behind the claim).
Do not repeat observations already made in the last 30 days unless the pattern changed.

Honesty rule: only claim what the data in front of you shows. Never
invent history — say "in your history" ONLY if PAST OBSERVATIONS or the
data actually contain an earlier instance. If this is the first time
you've seen it, say so ("this is the first time I've seen this").

Drafts (only matter for tier 3+):
- "I've noticed", never "you are". "In your history this has sometimes…" (only when true), never "this means".
- Show the supporting data briefly. Say "I might be reading this wrong."
- End with a question ("What's your read?", "Worth exploring?"), not a conclusion.
- Offer one concrete thing if useful. Under 90 words.

Psychological boundaries:
mild → reflect and ask. moderate → gently mention talking to someone could help.
significant → actively encourage support. serious (any sign of crisis or self-harm)
→ tier 5, prioritise safety, include NZ support: free call or text 1737, Lifeline 0800 543 354.
Never minimise, never try to be the solution.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "observations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "observation": {"type": "string"},
                    "domains": {"type": "array", "items": {"type": "string", "enum": DOMAINS}},
                    "data_points": {"type": "integer", "minimum": 0},
                    "tier": {"type": "integer", "minimum": 1, "maximum": 5},
                    "known_explanation": {"type": "string", "description": "empty if none"},
                    "alternatives": {"type": "string"},
                    "actionable": {"type": "boolean"},
                    "draft_message": {"type": "string"},
                    "prediction": {"type": "string", "description": "what you expect to happen next if the pattern holds"},
                },
                "required": ["observation", "domains", "data_points", "tier", "known_explanation",
                             "actionable", "draft_message", "prediction"],
            },
        }
    },
    "required": ["observations"],
}


# ---------- the gate (pure, tested) ----------

def should_surface(obs, now, surfaced_in_cooldown, calendar_busy, min_tier=3):
    """The minimum bar from the vision doc. Returns (ok, reason)."""
    if obs["tier"] == 5:
        return True, "tier 5: immediate concern"
    if obs["tier"] < min_tier:
        return False, f"tier {obs['tier']} below bar {min_tier}"
    if obs["data_points"] < MIN_DATA_POINTS:
        return False, "fewer than 5 data points"
    if len(set(obs["domains"])) < MIN_DOMAINS:
        return False, "only one domain"
    if (obs.get("known_explanation") or "").strip():
        return False, "has a known explanation"
    if not obs["actionable"]:
        return False, "not actionable"
    if surfaced_in_cooldown:
        return False, "something was raised in the last 7 days"
    if not QUIET_END <= now.hour < QUIET_START:
        return False, "quiet hours"
    if calendar_busy:
        return False, "busy calendar period"
    return True, "all checks passed"


def current_min_tier(ratings):
    """Self-adjusting bar. ratings: recent jay_rating values (1 right, 0 wrong),
    newest first. Mostly wrong lately → only raise tier 4+."""
    recent = [r for r in ratings if r is not None][:10]
    if len(recent) >= 5 and sum(recent) / len(recent) < 0.5:
        return 4
    return 3


# ---------- gathering ----------

def _nz(timestamp_utc):
    return datetime.fromisoformat(timestamp_utc).replace(tzinfo=ZoneInfo("UTC")).astimezone(NZ)


def activity_rhythm(days=30):
    """Messages per day and late-night activity, from the conversations table."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT timestamp, user_message FROM conversations WHERE timestamp >= datetime('now', ?)",
        (f"-{days} days",),
    ).fetchall()
    conn.close()
    if not rows:
        return "No conversations in this period.", []
    times = [_nz(t) for t, _ in rows]
    week_ago = datetime.now(NZ) - timedelta(days=7)
    late = lambda t: t.hour >= 23 or t.hour < 5
    recent = [t for t in times if t >= week_ago]
    older = [t for t in times if t < week_ago]
    older_weeks = max((days - 7) / 7, 1)
    per_day = Counter(t.strftime("%a %d %b") for t in recent)
    text = (
        f"Messages last 7 days: {len(recent)} (earlier weekly average {len(older) / older_weeks:.0f}). "
        f"Late-night (11pm-5am) messages last 7 days: {sum(map(late, recent))} "
        f"(earlier weekly average {sum(map(late, older)) / older_weeks:.1f}). "
        f"By day: {dict(per_day)}"
    )
    recent_words = [m[:200] for t, m in rows[-40:] if m and not m.startswith("[confirmed")]
    return text, recent_words


def calendar_load():
    """(text, busy?) — busy = 5+ events in the next 2 days. Fails soft."""
    try:
        from calendar_tool import get_upcoming_events
        events = get_upcoming_events(max_results=30)
        if events.startswith("An error") or events.startswith("No upcoming"):
            return events, False
        soon = datetime.now(NZ) + timedelta(days=2)
        count_soon = 0
        for line in events.splitlines():
            stamp = line.split("] ", 1)[-1].split(": ", 1)[0]
            try:
                start = datetime.fromisoformat(stamp)
                if start.tzinfo is None:
                    start = start.replace(tzinfo=NZ)
                if start <= soon:
                    count_soon += 1
            except ValueError:
                continue
        return f"{len(events.splitlines())} upcoming events; {count_soon} in the next 48h.", count_soon >= 5
    except Exception as e:
        return f"Calendar unavailable: {e}", False


def past_observations(days=30):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, date(created_at), tier, status, observation, jay_rating
        FROM observations WHERE created_at >= datetime('now', ?) ORDER BY id DESC LIMIT 30
        """,
        (f"-{days} days",),
    ).fetchall()
    conn.close()
    return "\n".join(
        f"#{i} {d} tier {tier} [{status}] {text}"
        + ("" if rating is None else f" (Jay rated: {'right' if rating else 'wrong'})")
        for i, d, tier, status, text, rating in rows
    ) or "(none)"


def gather_context():
    from learning import get_learning_history
    from socrates import past_sessions
    rhythm, recent_words = activity_rhythm()
    calendar_text, busy = calendar_load()
    health_trends = []
    for metric in METRICS:
        trend = metric_trend(metric)
        if trend:
            health_trends.append(f"{metric}: {trend['label']} (recent {trend['recent_mean']}, "
                                 f"normal {trend['baseline_mean']} ± {trend['baseline_sd']}, z={trend['z']})")
    money = ""
    try:
        from akahu_tool import akahu_connected, daily_money_alerts
        if akahu_connected():
            money = "\n".join(daily_money_alerts()) or "No unusual spending."
    except Exception:
        pass
    preferences = "\n".join(f"- {k}: {v}" for k, v in get_all_preferences()) or "(none)"

    context = f"""
TODAY: {datetime.now(NZ):%A %d %B %Y, %H:%M}

HEALTH (last 7 days vs his own baseline)
{get_health_summary(7)}
{chr(10).join(health_trends) or '(no baselines yet)'}

ACTIVITY RHYTHM
{rhythm}

CALENDAR
{calendar_text}

LEARNING
{get_learning_history(limit=10)}

THINKING SESSIONS
{past_sessions(5)}

MONEY
{money or '(Akahu not connected)'}

STATED PREFERENCES / VALUES
{preferences}

JAY'S RECENT MESSAGES (his own words, oldest first)
{chr(10).join('- ' + w for w in recent_words) or '(none)'}

PAST OBSERVATIONS (last 30 days)
{past_observations()}
"""
    return context, busy


# ---------- running ----------

def _surfaced_in_cooldown():
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) FROM observations WHERE surfaced_at >= datetime('now', ?)",
        (f"-{COOLDOWN_DAYS} days",),
    ).fetchone()
    conn.close()
    return row[0] > 0


def _recent_ratings():
    conn = get_connection()
    rows = conn.execute(
        "SELECT jay_rating FROM observations WHERE surfaced_at IS NOT NULL AND jay_rating IS NOT NULL "
        "ORDER BY id DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def save_observation(obs, status):
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO observations (created_at, observation, domains, data_points, tier,
            known_explanation, alternatives, actionable, draft_message, prediction, status)
        VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (obs["observation"], json.dumps(obs["domains"]), obs["data_points"], obs["tier"],
         obs.get("known_explanation", ""), obs.get("alternatives", ""), int(obs["actionable"]),
         obs["draft_message"], obs["prediction"], status),
    )
    conn.commit()
    observation_id = cursor.lastrowid
    conn.close()
    return observation_id


def mark_surfaced(observation_id):
    conn = get_connection()
    conn.execute(
        "UPDATE observations SET status = 'surfaced', surfaced_at = datetime('now') WHERE id = ?",
        (observation_id,),
    )
    conn.commit()
    conn.close()


def run_inference(now=None):
    """Returns the message to send Jay, or None (most days: None)."""
    now = now or datetime.now(NZ)
    context, busy = gather_context()
    result = ask_structured(
        INFERENCE_PROMPT, context, "record_observations",
        "Record today's observations (an empty list is a fine answer).", SCHEMA,
    )
    observations = (result or {}).get("observations", [])
    min_tier = current_min_tier(_recent_ratings())
    cooldown = _surfaced_in_cooldown()

    candidates = []
    for obs in observations:
        ok, reason = should_surface(obs, now, cooldown, busy, min_tier)
        observation_id = save_observation(obs, "candidate" if ok else "logged")
        if ok:
            candidates.append((obs["tier"], observation_id, obs))
    log_task("inference", f"{len(observations)} observations, {len(candidates)} passed the bar", "success")

    if not candidates:
        return None
    tier, observation_id, obs = max(candidates, key=lambda c: c[0])
    mark_surfaced(observation_id)
    return (
        f"{obs['draft_message']}\n\n"
        f"<i>(Observation #{observation_id}. Tell me if I've read it right or wrong — I keep score.)</i>"
    )


def rate_observation(observation_id, accurate, note=""):
    conn = get_connection()
    cursor = conn.execute(
        "UPDATE observations SET jay_rating = ?, jay_note = ? WHERE id = ?",
        (int(accurate), note, observation_id),
    )
    conn.commit()
    conn.close()
    if not cursor.rowcount:
        return f"No observation #{observation_id}."
    return f"Noted — observation #{observation_id} marked {'right' if accurate else 'wrong'}."


def get_observations(include_logged=False, limit=15):
    conn = get_connection()
    where = "" if include_logged else "WHERE status = 'surfaced'"
    rows = conn.execute(
        f"""
        SELECT id, date(created_at), tier, status, observation, prediction, jay_rating
        FROM observations {where} ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    if not rows:
        return "No observations yet — it takes weeks of data before patterns are worth naming."
    return "\n".join(
        f"#{i} {d} tier {tier} [{status}] {text} → predicted: {prediction}"
        + ("" if rating is None else f" | you said: {'right' if rating else 'wrong'}")
        for i, d, tier, status, text, prediction, rating in rows
    )


def what_alfred_knows():
    """'What do you know about me?' / 'How accurate have you been?' /
    'What don't you understand about me yet?'"""
    conn = get_connection()
    counts = {
        "conversations": conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0],
        "health logs": conn.execute("SELECT COUNT(*) FROM health_logs").fetchone()[0],
        "learning sessions": conn.execute("SELECT COUNT(*) FROM learning_log").fetchone()[0],
        "thinking sessions": conn.execute("SELECT COUNT(*) FROM thinking_sessions").fetchone()[0],
        "observations logged": conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0],
        "preferences": conn.execute("SELECT COUNT(*) FROM preferences").fetchone()[0],
    }
    rated = conn.execute(
        "SELECT SUM(jay_rating), COUNT(jay_rating) FROM observations WHERE jay_rating IS NOT NULL"
    ).fetchone()
    per_metric = dict(conn.execute("SELECT metric, COUNT(DISTINCT date) FROM health_logs GROUP BY metric").fetchall())
    conn.close()

    lines = ["What I have:"] + [f"- {k}: {v}" for k, v in counts.items()]
    if rated and rated[1]:
        lines.append(f"\nMy accuracy: {rated[0]} of {rated[1]} surfaced observations you rated were right.")
    else:
        lines.append("\nMy accuracy: nothing rated yet.")
    thin = [m for m in METRICS if per_metric.get(m, 0) < 5]
    lines.append("\nWhat I don't understand yet (under 5 days of data): " + (", ".join(thin) or "nothing — good coverage"))
    lines.append("\nSurfaced observations:\n" + get_observations())
    return "\n".join(lines)


# ---------- reviews ----------

REVIEW_PROMPTS = {
    "weekly": "Write Jay's WEEKLY REVIEW: what happened this week, patterns, what's coming up, "
              "and end with ONE reflection for him to sit with. Under 200 words.",
    "monthly": "Write Jay's MONTHLY REPORT: trends vs last month, what improved, what didn't, "
               "health metrics vs his baseline, money if available. Honest, under 300 words.",
    "quarterly": "Write Jay's QUARTERLY DEEP REVIEW: how is he different from 3 months ago? "
                 "What does the data say vs what he seems to think? Where is the trajectory heading? "
                 "End with one honest question you want to ask him. Under 400 words.",
}

REVIEW_SYSTEM = """
You are Alfred writing a life review for Jay. Composed, warm, direct.
Data over flattery; note uncertainty where data is thin. Never diagnose.
Telegram HTML only (<b>, <i>). No markdown.
"""


def last_review(period):
    conn = get_connection()
    row = conn.execute(
        "SELECT created_at, content FROM reviews WHERE period = ? ORDER BY id DESC LIMIT 1", (period,)
    ).fetchone()
    conn.close()
    return row


def write_review(period):
    context, _ = gather_context()
    previous = last_review(period)
    prompt = (
        REVIEW_PROMPTS[period]
        + f"\n\nDATA\n{context}"
        + (f"\n\nYOUR PREVIOUS {period.upper()} REVIEW ({previous[0]}):\n{previous[1]}" if previous else "")
    )
    content = ask_once(REVIEW_SYSTEM, prompt, max_tokens=1500)
    conn = get_connection()
    conn.execute("INSERT INTO reviews (created_at, period, content) VALUES (datetime('now'), ?, ?)",
                 (period, content))
    conn.commit()
    conn.close()
    log_task(f"review_{period}", "written", "success")
    return content


def get_last_review(period="weekly"):
    row = last_review(period)
    return row[1] if row else f"No {period} review yet."
