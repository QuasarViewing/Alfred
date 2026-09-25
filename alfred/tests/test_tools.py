from datetime import datetime, date, time
from zoneinfo import ZoneInfo
import pytest
from tools import calculate
from calendar_tool import find_free_slots
from confirmations import request_confirmation, get_pending, pop_pending
from food_order import parse_price

NZ = ZoneInfo("Pacific/Auckland")


# ---- calculator ----

@pytest.mark.parametrize("expression, expected", [
    ("2 + 2", "4"),
    ("2 + 2 * (3 - 1)", "6"),
    ("2^10", "1024"),
    ("sqrt(16)", "4.0"),
    ("-5 + 3", "-2"),
    ("round(2340 * 0.175, 2)", "409.5"),
])
def test_calculator_maths(expression, expected):
    assert calculate(expression) == expected


@pytest.mark.parametrize("attack", [
    "__import__('os').system('echo hacked')",
    "open('alfred.db').read()",
    "().__class__.__bases__",
    "9 ** 9 ** 9",
])
def test_calculator_refuses_code(attack):
    assert calculate(attack) == "Sorry, I couldn't calculate that."


# ---- free slots ----

def at(day, hour, minute=0):
    return datetime.combine(day, time(hour, minute), tzinfo=NZ)


def test_free_slots_between_meetings():
    day = date(2026, 6, 15)  # NZ winter, +12:00
    busy = [(at(day, 10), at(day, 11)), (at(day, 13), at(day, 14))]
    slots = find_free_slots(busy, at(day, 8), at(day, 22))
    assert [(s.hour, e.hour) for s, e in slots] == [(8, 10), (11, 13), (14, 22)]


def test_free_slots_handles_overlapping_events():
    day = date(2026, 1, 15)  # NZ summer, +13:00
    busy = [(at(day, 9), at(day, 12)), (at(day, 10), at(day, 11))]
    slots = find_free_slots(busy, at(day, 8), at(day, 22))
    assert [(s.hour, e.hour) for s, e in slots] == [(8, 9), (12, 22)]


def test_free_slots_fully_booked():
    day = date(2026, 3, 1)
    assert find_free_slots([(at(day, 7), at(day, 23))], at(day, 8), at(day, 22)) == []


def test_nz_offset_changes_with_daylight_saving():
    assert at(date(2026, 1, 15), 9).utcoffset().total_seconds() == 13 * 3600
    assert at(date(2026, 6, 15), 9).utcoffset().total_seconds() == 12 * 3600


# ---- confirmation gate ----

def test_confirmation_runs_only_once():
    action_id = request_confirmation("send_email", print, {"x": 1}, "desc")
    assert get_pending(action_id)["name"] == "send_email"
    assert pop_pending(action_id) is not None
    assert pop_pending(action_id) is None  # double-tap can't run it twice


def test_unknown_confirmation_is_none():
    assert get_pending("does-not-exist") is None


# ---- registry: gated tools describe themselves ----

def test_every_gated_tool_has_its_own_description():
    import tool_registry
    gated = [t for t in tool_registry.TOOLS if t.get("requires_confirmation")]
    assert gated, "expected at least one gated tool"
    for tool in gated:
        assert callable(tool.get("describe")), f"{tool['name']} is gated but has no describe"


def test_describe_action_uses_the_registry():
    from tool_registry import describe_action
    text = describe_action("send_email", {"to": "sam@example.com", "subject": "Late", "body": "10 mins"})
    assert text.startswith("📧 Send email to sam@example.com") and "10 mins" in text
    assert describe_action("checkout_food_order", {"order_name": "friday", "expected_total": 38.5}) == \
        "🍔 Order 'friday' for NZ$38.50"


# ---- error hygiene ----

def test_tool_errors_dont_leak_raw_messages(temp_db, monkeypatch):
    import tool_registry

    def broken():
        raise ValueError("secret path C:\\Users\\jjsey\\token.json")

    monkeypatch.setitem(tool_registry.TOOLS_BY_NAME, "broken_tool", {"name": "broken_tool", "function": broken})
    text, is_error, action_id = tool_registry.run_tool("broken_tool", {})
    assert is_error and action_id is None
    assert "ValueError" in text and "ref " in text
    assert "secret" not in text and "token.json" not in text


# ---- database concurrency ----

def test_connections_use_wal_and_wait_for_locks(temp_db):
    conn = temp_db.get_connection()
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
    conn.close()


def test_two_threads_writing_at_once_both_succeed(temp_db):
    import threading
    errors = []

    def write(n):
        try:
            for i in range(50):
                temp_db.log_task(f"thread{n}", str(i), "ok")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=write, args=(n,)) for n in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    conn = temp_db.get_connection()
    assert errors == []
    assert conn.execute("SELECT COUNT(*) FROM task_history").fetchone()[0] == 100
    conn.close()


# ---- food order helpers ----

@pytest.mark.parametrize("text, expected", [
    ("Total NZ$34.50", 34.5),
    ("Order total $1,204.99", 1204.99),
    ("Total: free", None),
    (None, None),
])
def test_parse_price(text, expected):
    assert parse_price(text) == expected


def test_usual_orders_round_trip(temp_db):
    from food_order import save_usual_order, get_usual_order
    save_usual_order("Friday Burger", "Burger Fuel", "Bastard, Kumara Fries")
    order = get_usual_order("friday burger")
    assert order["restaurant"] == "Burger Fuel"
    assert order["items"] == ["Bastard", "Kumara Fries"]
