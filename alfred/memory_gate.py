"""
Deciding what goes into long-term memory (ChromaDB).

Only Jay's own messages are considered — never Alfred's replies, which
would otherwise be recalled later as if they were facts about Jay.
Claude judges whether a message contains a DURABLE fact or preference
("I'm vegetarian", "my sister's name is Mere"), and if so returns it
as one clean sentence. Passing moods, questions and chit-chat are skipped.

Fails closed: any error or malformed answer means nothing is stored.
A missed memory costs little; a false one pollutes every future answer.
"""
import logging
from llm import ask_structured

MIN_LENGTH = 12   # "ok thanks", "lol yes" — not worth an API call

JUDGE_PROMPT = """
You decide what Alfred, Jay's personal assistant, should remember long-term.

Remember only DURABLE facts or preferences that Jay states about himself,
his life, people, places, routines, goals or tastes — things still likely
to be true in a month. Examples worth remembering:
"I'm allergic to penicillin", "my gym is Anytime Fitness on Tongariro St",
"I prefer flat whites", "Mere is my sister", "I'm aiming to run a half marathon in March".

Do NOT remember: questions, requests to do something, passing moods,
one-off plans already handled by the calendar, small talk, or anything
Jay didn't actually state (no guesses or inferences).

If worth remembering, rewrite it as ONE short third-person sentence
about Jay, using only what he said.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "remember": {"type": "boolean"},
        "fact": {"type": "string", "description": "One third-person sentence; empty if remember is false."},
    },
    "required": ["remember", "fact"],
}


def judge_memory(message, ask=ask_structured):
    """Return the fact to store, or None. `ask` is swappable so tests can fake Claude."""
    if not message or len(message.strip()) < MIN_LENGTH:
        return None
    try:
        result = ask(
            JUDGE_PROMPT,
            f"Jay's message:\n{message}",
            "record_memory_decision",
            "Record whether this message contains a durable fact worth remembering.",
            SCHEMA,
            max_tokens=300,
        )
    except Exception:
        logging.exception("Memory judge failed; not storing")
        return None
    if not isinstance(result, dict) or result.get("remember") is not True:
        return None
    fact = (result.get("fact") or "").strip()
    return fact or None
