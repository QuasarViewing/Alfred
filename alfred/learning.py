"""
Phase 7 — Cooking and learning mode.

Photos come in through bot.py's handle_photo() and go to Claude as
images (vision). This file is the memory side: every practice session
(a meal cooked, a workout, a repair) is logged so Alfred can see Jay
improving and adjust difficulty.
"""
from database import get_connection

COACH_PROMPT = """
Photos: you can see images Jay sends.
- A fridge or pantry photo: list what you can identify, then suggest 2-3
  meals that fit his cooking history (check get_learning_history for
  domain "cooking" first). Pitch difficulty one small step above his
  recent ratings.
- A photo mid-cooking (or exercise form, a plant, a repair): assess
  technique honestly and specifically, then give ONE next step.
- Coach one step at a time. Ask him to send a photo at each stage.
- When a session ends, call log_learning with what he did and how it went.
"""


def log_learning(domain, activity, notes="", self_rating=None, difficulty=""):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO learning_log (timestamp, domain, activity, notes, self_rating, difficulty)
        VALUES (datetime('now'), ?, ?, ?, ?, ?)
        """,
        (domain.lower(), activity, notes, self_rating, difficulty),
    )
    conn.commit()
    conn.close()
    return f"Logged {domain}: {activity}"


def get_learning_history(domain=None, limit=15):
    conn = get_connection()
    if domain:
        rows = conn.execute(
            """
            SELECT date(timestamp), domain, activity, self_rating, difficulty, notes
            FROM learning_log WHERE domain = ? ORDER BY id DESC LIMIT ?
            """,
            (domain.lower(), limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT date(timestamp), domain, activity, self_rating, difficulty, notes
            FROM learning_log ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    conn.close()
    if not rows:
        return "No learning history yet" + (f" for {domain}." if domain else ".")
    return "\n".join(
        f"{d} [{dom}] {activity}"
        + (f" — rated {rating}/10" if rating is not None else "")
        + (f", {difficulty}" if difficulty else "")
        + (f". {notes}" if notes else "")
        for d, dom, activity, rating, difficulty, notes in rows
    )
