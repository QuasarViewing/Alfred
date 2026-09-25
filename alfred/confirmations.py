"""
The confirmation gate.

Some tools are too consequential for Claude to run on its own
(sending email, deleting events, spending money). When Claude calls
one, Alfred does NOT run it. Instead it parks the call here as a
"pending action" and Telegram shows Jay ✅ Confirm / ❌ Cancel buttons.
Only a tap on Confirm actually runs the function.

This is enforced in code, not in the prompt — so even if Claude
misunderstands, or a malicious email tries to trick it, nothing
irreversible happens without Jay's tap.
"""
from datetime import datetime, timedelta
import uuid

EXPIRY = timedelta(minutes=15)

# id → {"name", "function", "args", "description", "created"}
_pending = {}


def request_confirmation(name, function, args, description):
    _clear_expired()
    action_id = uuid.uuid4().hex[:10]
    _pending[action_id] = {
        "name": name,
        "function": function,
        "args": args,
        "description": description,
        "created": datetime.now(),
    }
    return action_id


def get_pending(action_id):
    _clear_expired()
    return _pending.get(action_id)


def pop_pending(action_id):
    """Remove and return an action — pop so a double-tap can't run it twice."""
    _clear_expired()
    return _pending.pop(action_id, None)


def _clear_expired():
    now = datetime.now()
    for action_id in [k for k, v in _pending.items() if now - v["created"] > EXPIRY]:
        del _pending[action_id]
