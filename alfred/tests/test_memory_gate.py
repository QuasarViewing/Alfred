"""The memory gate must fail CLOSED: when in doubt, store nothing."""
from memory_gate import judge_memory


def fake_claude(answer=None, error=None):
    calls = []

    def ask(*args, **kwargs):
        calls.append(args)
        if error:
            raise error
        return answer

    ask.calls = calls
    return ask


def test_durable_fact_is_stored_as_clean_sentence():
    ask = fake_claude({"remember": True, "fact": "Jay's coffee order is a flat white."})
    assert judge_memory("ugh traffic, anyway my coffee order is a flat white now", ask) == \
        "Jay's coffee order is a flat white."


def test_not_durable_is_skipped():
    ask = fake_claude({"remember": False, "fact": ""})
    assert judge_memory("what's the weather doing tomorrow?", ask) is None


def test_short_messages_skip_the_api_call():
    ask = fake_claude({"remember": True, "fact": "x"})
    assert judge_memory("ok thanks", ask) is None
    assert ask.calls == []


def test_api_error_fails_closed():
    assert judge_memory("I'm allergic to penicillin", fake_claude(error=RuntimeError("503"))) is None


def test_no_tool_call_fails_closed():
    assert judge_memory("I'm allergic to penicillin", fake_claude(None)) is None


def test_non_boolean_remember_fails_closed():
    # "yes" is truthy but not True — a sloppy answer must not slip through
    assert judge_memory("I'm allergic to penicillin", fake_claude({"remember": "yes", "fact": "x"})) is None


def test_remember_true_but_empty_fact_fails_closed():
    assert judge_memory("I'm allergic to penicillin", fake_claude({"remember": True, "fact": "  "})) is None
