"""Tests for the full-version phases: health, bills, banking analysis,
the intelligence gate, confidence calibration, news dedupe, Socrates."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import time
import pytest

NZ = ZoneInfo("Pacific/Auckland")


# ---------- Phase 3: health ----------

def test_baseline_needs_enough_history():
    from health import compare_to_baseline
    assert compare_to_baseline([5], [6, 7]) is None


def test_baseline_within_usual_range():
    from health import compare_to_baseline
    result = compare_to_baseline([6.5], [6, 7, 6, 7, 6, 7])
    assert result["label"] == "within your usual range"


def test_baseline_well_below_usual():
    from health import compare_to_baseline
    result = compare_to_baseline([3, 3], [7, 7.5, 6.5, 7, 7.2, 6.8])
    assert result["label"] == "well below your usual" and result["z"] < -2


def test_log_health_validates(temp_db):
    from health import log_health, get_metric_history
    assert "Unknown metric" in log_health("vibes", 5)
    assert "Not logged" in log_health("energy", 42)
    assert log_health("energy", 6, "after coffee").startswith("Logged energy = 6")
    assert len(get_metric_history("energy")) == 1


# ---------- Phase 2: bills ----------

def test_monthly_bill_on_31st_clamps_then_recovers():
    from bills import next_due_after
    jan31 = date(2026, 1, 31)
    feb = next_due_after(jan31, "monthly", 31)
    mar = next_due_after(feb, "monthly", 31)
    assert feb == date(2026, 2, 28) and mar == date(2026, 3, 31)


def test_other_frequencies():
    from bills import next_due_after
    start = date(2026, 11, 15)
    assert next_due_after(start, "weekly", 15) == date(2026, 11, 22)
    assert next_due_after(start, "fortnightly", 15) == date(2026, 11, 29)
    assert next_due_after(start, "quarterly", 15) == date(2027, 2, 15)
    assert next_due_after(start, "yearly", 15) == date(2027, 11, 15)


def test_bill_reminder_fires_once_per_due_date(temp_db):
    from bills import add_bill, bills_needing_reminder, mark_bill_paid
    today = date(2026, 10, 10)
    add_bill("power", 180, "monthly", "2026-10-12")
    add_bill("netflix", 25.99, "monthly", "2026-10-28", is_subscription=True)
    first = bills_needing_reminder(today)
    assert len(first) == 1 and "power" in first[0] and "2 day" in first[0]
    assert bills_needing_reminder(today) == []           # idempotent
    mark_bill_paid("power")
    assert bills_needing_reminder(date(2026, 11, 10)) != []  # next cycle reminds again


# ---------- Phase 2: banking analysis ----------

def _txn(day, amount, merchant, category="Entertainment"):
    return {"date": day.isoformat() + "T00:00:00Z", "amount": amount,
            "merchant": {"name": merchant}, "category": {"name": category}}


def test_detects_monthly_subscription():
    from akahu_tool import detect_subscriptions
    start = date(2026, 3, 5)
    txns = [_txn(start + timedelta(days=30 * i), -25.99, "Netflix") for i in range(5)]
    txns += [_txn(date(2026, 4, 2), -80, "Countdown", "Groceries"),
             _txn(date(2026, 4, 20), -12, "Countdown", "Groceries")]
    subs = detect_subscriptions(txns)
    assert [s["merchant"] for s in subs] == ["Netflix"]
    assert subs[0]["interval_days"] == 30


def test_irregular_merchant_is_not_a_subscription():
    from akahu_tool import detect_subscriptions
    days = [date(2026, 3, 1), date(2026, 3, 4), date(2026, 4, 20), date(2026, 5, 2)]
    assert detect_subscriptions([_txn(d, -40, "Z Energy", "Transport") for d in days]) == []


def test_unusual_spending_uses_own_baseline():
    from akahu_tool import unusual_transactions
    history = [_txn(date(2026, 5, d), -(30 + d % 5), "Countdown", "Groceries") for d in range(1, 20)]
    recent = [_txn(date(2026, 6, 1), -35, "Countdown", "Groceries"),
              _txn(date(2026, 6, 2), -420, "Countdown", "Groceries")]
    flagged = unusual_transactions(history, recent)
    assert len(flagged) == 1 and flagged[0][0]["amount"] == -420


def test_spending_by_category_ignores_income():
    from akahu_tool import spending_by_category
    txns = [_txn(date(2026, 6, 1), 3000, "Employer", "Income"),
            _txn(date(2026, 6, 2), -50, "Countdown", "Groceries"),
            _txn(date(2026, 6, 3), -20, "Countdown", "Groceries")]
    assert spending_by_category(txns) == [("Groceries", 70)]


# ---------- Phase 4: the surfacing gate ----------

def _obs(**overrides):
    obs = {"tier": 3, "data_points": 8, "domains": ["sleep", "mood"], "known_explanation": "",
           "actionable": True}
    obs.update(overrides)
    return obs


AFTERNOON = datetime(2026, 10, 1, 18, 0, tzinfo=NZ)


def test_gate_passes_a_good_observation():
    from intelligence import should_surface
    assert should_surface(_obs(), AFTERNOON, False, False)[0]


@pytest.mark.parametrize("overrides, when, cooldown, busy", [
    ({"tier": 2}, AFTERNOON, False, False),
    ({"data_points": 4}, AFTERNOON, False, False),
    ({"domains": ["sleep"]}, AFTERNOON, False, False),
    ({"known_explanation": "he was sick"}, AFTERNOON, False, False),
    ({"actionable": False}, AFTERNOON, False, False),
    ({}, AFTERNOON, True, False),                                   # raised something this week
    ({}, datetime(2026, 10, 1, 22, 0, tzinfo=NZ), False, False),    # after 9pm
    ({}, datetime(2026, 10, 1, 6, 30, tzinfo=NZ), False, False),    # before 7am
    ({}, AFTERNOON, False, True),                                   # busy calendar
])
def test_gate_blocks(overrides, when, cooldown, busy):
    from intelligence import should_surface
    assert not should_surface(_obs(**overrides), when, cooldown, busy)[0]


def test_tier_five_always_surfaces():
    from intelligence import should_surface
    late_night = datetime(2026, 10, 1, 23, 30, tzinfo=NZ)
    assert should_surface(_obs(tier=5, data_points=1, domains=["mood"]), late_night, True, True)[0]


def test_bar_rises_when_alfred_is_often_wrong():
    from intelligence import current_min_tier
    assert current_min_tier([1, 1, 0, 1, 1]) == 3
    assert current_min_tier([0, 0, 1, 0, 0, 1]) == 4
    assert current_min_tier([0, 0]) == 3   # too few ratings to judge


# ---------- Phase 6: calibration and news ----------

def test_calibration_needs_twenty_samples():
    from hypothesis import calibrate_confidence
    assert calibrate_confidence("gap_up", "medium", {"gap_up": (2, 10)}) == ("medium", "")


def test_calibration_downgrades_and_upgrades():
    from hypothesis import calibrate_confidence
    assert calibrate_confidence("gap_up", "medium", {"gap_up": (8, 20)})[0] == "low"
    assert calibrate_confidence("golden_cross", "medium", {"golden_cross": (15, 22)})[0] == "high"
    assert calibrate_confidence("gap_up", "low", {"gap_up": (1, 30)})[0] == "low"   # floor


def test_same_story_from_two_sources_dedupes():
    from news_pipeline import headline_id
    assert headline_id("NVIDIA beats estimates, raises guidance - Reuters") == \
           headline_id("Nvidia Beats Estimates, Raises Guidance")


def test_impact_score():
    from news_pipeline import impact_score
    assert impact_score({"magnitude": 4, "novelty": 3, "clarity": 5, "breadth": 2}) == 3.5


def test_old_news_is_skipped():
    from news_pipeline import is_recent
    now = datetime(2026, 9, 24, 12, tzinfo=timezone.utc)
    fresh = {"published_parsed": time.struct_time((2026, 9, 24, 1, 0, 0, 0, 0, 0))}
    stale = {"published_parsed": time.struct_time((2026, 9, 20, 1, 0, 0, 0, 0, 0))}
    assert is_recent(fresh, now) and not is_recent(stale, now)


# ---------- Phase 8 + 7: Socrates and learning ----------

def test_thinking_session_lifecycle(temp_db):
    from socrates import start_thinking_session, end_thinking_session, get_active_session, \
        socratic_prompt_block, past_sessions
    assert socratic_prompt_block() == ""
    start_thinking_session("should I go contracting?")
    assert get_active_session()["topic"] == "should I go contracting?"
    assert "already open" in start_thinking_session("something else")
    assert "SOCRATES MODE IS ACTIVE" in socratic_prompt_block()
    end_thinking_session("Leaning towards it; money worry is the blocker", "What's my runway?")
    assert get_active_session() is None
    assert "runway" in past_sessions()


def test_learning_log_round_trip(temp_db):
    from learning import log_learning, get_learning_history
    log_learning("Cooking", "pan-seared salmon", "skin crisp, slightly overdone", 7, "medium")
    history = get_learning_history("cooking")
    assert "salmon" in history and "7/10" in history
