"""
Phase 8 — Socrates thinking mode.

"Think through this with me" → Claude calls start_thinking_session().
While a session is active, the system prompt switches Alfred from
answering to questioning. When Jay wraps up, Claude calls
end_thinking_session() with a summary and the open questions, so the
next session on a related topic picks up where this one left off.
"""
from database import get_connection, get_preference, save_preference

ACTIVE_KEY = "socratic_session_id"

SOCRATES_PROMPT = """
SOCRATES MODE IS ACTIVE. Topic: {topic}

You are not answering right now. You are helping Jay think.
- Ask one question at a time. Short. Then stop and wait.
- Challenge assumptions: "What makes you sure of that?"
- Surface what he isn't considering: costs, other people, the long run.
- Sit with uncertainty. Don't rush to resolve it.
- Never give your answer or recommendation, even if asked directly.
  If he pushes, say you'll share a view after the session ends.
- Notice when his reasoning conflicts with values he's stated before.
- When he says he's done, call end_thinking_session with an honest
  summary and the questions still open.

Earlier thinking sessions (for continuity):
{history}
"""


def start_thinking_session(topic):
    active = get_active_session()
    if active:
        return f"A thinking session on '{active['topic']}' is already open. End it first, or keep going."
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO thinking_sessions (started_at, topic) VALUES (datetime('now'), ?)",
        (topic,),
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    save_preference(ACTIVE_KEY, str(session_id))
    return f"Thinking session started on '{topic}'. Socrates mode on — ask your first question."


def end_thinking_session(summary, open_questions=""):
    active = get_active_session()
    if not active:
        return "No thinking session is open."
    conn = get_connection()
    conn.execute(
        """
        UPDATE thinking_sessions
        SET ended_at = datetime('now'), summary = ?, open_questions = ?
        WHERE id = ?
        """,
        (summary, open_questions, active["id"]),
    )
    conn.commit()
    conn.close()
    save_preference(ACTIVE_KEY, "")
    return f"Session on '{active['topic']}' saved. Back to normal mode."


def get_active_session(max_hours=6):
    """The open session, or None. Sessions older than max_hours auto-close
    so Alfred can't get stuck in question mode for days."""
    session_id = get_preference(ACTIVE_KEY)
    if not session_id:
        return None
    conn = get_connection()
    row = conn.execute(
        """
        SELECT id, topic, started_at >= datetime('now', ?) FROM thinking_sessions
        WHERE id = ? AND ended_at IS NULL
        """,
        (f"-{max_hours} hours", int(session_id)),
    ).fetchone()
    conn.close()
    if not row:
        save_preference(ACTIVE_KEY, "")
        return None
    if not row[2]:
        end_thinking_session("(auto-closed after inactivity)")
        return None
    return {"id": row[0], "topic": row[1]}


def past_sessions(limit=5):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT date(started_at), topic, summary, open_questions FROM thinking_sessions
        WHERE ended_at IS NOT NULL ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    if not rows:
        return "(none yet)"
    return "\n".join(
        f"- {d} '{topic}': {summary or 'no summary'}"
        + (f" | still open: {questions}" if questions else "")
        for d, topic, summary, questions in rows
    )


def socratic_prompt_block():
    """Extra system-prompt text while a session is active, else ''."""
    active = get_active_session()
    if not active:
        return ""
    return SOCRATES_PROMPT.format(topic=active["topic"], history=past_sessions())
