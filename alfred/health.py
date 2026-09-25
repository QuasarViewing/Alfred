"""
Phase 3 — Health intelligence (manual logging).

Jay tells Alfred how he slept / his energy / mood in plain language;
Claude calls log_health() once per number. Everything is compared to
Jay's OWN baseline — "Jay's 45 HRV is Jay's 45 HRV" — never to
population averages.

Check-ins are gentle: the morning brief ends with one question, and
the evening nudge only fires if nothing has been logged that day.
Alfred never demands, never guilts.
"""
from datetime import datetime, timedelta
from statistics import mean, stdev
from zoneinfo import ZoneInfo
from config import TIMEZONE
from database import get_connection, get_preference

NZ = ZoneInfo(TIMEZONE)

# metric → (description, min, max). Scales are 1–10 unless stated.
METRICS = {
    "sleep_hours": ("hours slept", 0, 16),
    "sleep_quality": ("sleep quality 1-10", 1, 10),
    "energy": ("energy 1-10", 1, 10),
    "mood": ("mood 1-10", 1, 10),
    "stress": ("stress 1-10 (10 = very stressed)", 1, 10),
    "exercise_minutes": ("minutes of exercise", 0, 600),
    "alcohol_drinks": ("standard drinks", 0, 50),
    "caffeine_cups": ("cups of coffee/energy drinks", 0, 20),
    "focus": ("focus / ability to concentrate 1-10", 1, 10),
    "weight_kg": ("body weight kg", 20, 300),
}

MORNING_QUESTION = "How did you sleep, and how's your energy out of 10? (No pressure — skip if you like.)"
EVENING_QUESTION = "If you feel like it: mood today out of 10, and anything notable?"


def today_nz():
    return datetime.now(NZ).strftime("%Y-%m-%d")


def log_health(metric, value, note="", date=None):
    metric = metric.strip().lower()
    if metric not in METRICS:
        return f"Unknown metric '{metric}'. Known: {', '.join(METRICS)}"
    _, low, high = METRICS[metric]
    if not low <= value <= high:
        return f"{metric} should be between {low} and {high}; got {value}. Not logged."
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO health_logs (timestamp, date, metric, value, note)
        VALUES (datetime('now'), ?, ?, ?, ?)
        """,
        (date or today_nz(), metric, value, note),
    )
    conn.commit()
    conn.close()
    return f"Logged {metric} = {value:g}" + (f" ({note})" if note else "")


def get_metric_history(metric, days=60):
    """[(date, value)] oldest first. Several logs on one day → their average."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT date, AVG(value) FROM health_logs
        WHERE metric = ? AND date >= date('now', ?)
        GROUP BY date ORDER BY date
        """,
        (metric, f"-{days} days"),
    ).fetchall()
    conn.close()
    return rows


def compare_to_baseline(recent, baseline):
    """Pure logic: how does the recent average compare to Jay's own normal?

    Returns a dict, or None if there isn't enough history to say anything
    honest. z = how many "usual wobbles" (standard deviations) away.
    """
    if len(recent) < 1 or len(baseline) < 5:
        return None
    base_mean = mean(baseline)
    base_sd = stdev(baseline) if len(baseline) > 1 else 0
    recent_mean = mean(recent)
    z = (recent_mean - base_mean) / base_sd if base_sd > 0 else 0.0
    if abs(z) < 1:
        label = "within your usual range"
    elif z > 0:
        label = "above your usual" if abs(z) < 2 else "well above your usual"
    else:
        label = "below your usual" if abs(z) < 2 else "well below your usual"
    return {
        "recent_mean": round(recent_mean, 2),
        "baseline_mean": round(base_mean, 2),
        "baseline_sd": round(base_sd, 2),
        "z": round(z, 2),
        "label": label,
        "baseline_points": len(baseline),
    }


def metric_trend(metric, recent_days=7, baseline_days=60):
    history = get_metric_history(metric, baseline_days)
    if not history:
        return None
    cutoff = (datetime.now(NZ) - timedelta(days=recent_days)).strftime("%Y-%m-%d")
    recent = [v for d, v in history if d > cutoff]
    baseline = [v for d, v in history if d <= cutoff]
    return compare_to_baseline(recent, baseline)


def get_health_summary(days=7):
    lines = []
    for metric in METRICS:
        history = get_metric_history(metric, days)
        if not history:
            continue
        values = [v for _, v in history]
        line = f"{metric}: last {values[-1]:g}, {days}-day avg {mean(values):.1f} over {len(values)} days"
        trend = metric_trend(metric, recent_days=days)
        if trend:
            line += f" — {trend['label']} (your normal {trend['baseline_mean']:g})"
        else:
            line += " — not enough history for a baseline yet"
        lines.append(line)
    if not lines:
        return "Nothing logged yet. Tell me how you slept or your energy out of 10 whenever you like."
    return "\n".join(lines)


def logged_today(metrics=None):
    conn = get_connection()
    if metrics:
        placeholders = ",".join("?" * len(metrics))
        row = conn.execute(
            f"SELECT COUNT(*) FROM health_logs WHERE date = ? AND metric IN ({placeholders})",
            (today_nz(), *metrics),
        ).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) FROM health_logs WHERE date = ?", (today_nz(),)).fetchone()
    conn.close()
    return row[0] > 0


def checkins_enabled():
    return (get_preference("health_checkins") or "on").lower() != "off"
