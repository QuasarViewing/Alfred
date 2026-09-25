"""
Every tool Alfred can use, in one place.

Each entry pairs:
  - the schema Claude sees (name, description, input_schema)
  - the Python function that actually runs
  - whether Jay must confirm before it runs

The input_schema property names MUST match the function's parameter
names exactly, because the router calls   function(**tool_input)
which unpacks {"ticker": "AAPL"} into   function(ticker="AAPL").
"""
import logging
import uuid
from tools import web_search, get_weather, calculate, get_alfred_preference, save_alfred_preference
from calendar_tool import get_upcoming_events, get_events_for_day, add_event, delete_event, edit_event, get_free_slots
from gmail_tool import get_unread_emails, search_emails, create_draft, send_email
from finance_tool import (
    get_ticker_info, add_to_portfolio, remove_from_portfolio, get_portfolio_summary,
    add_to_watchlist, remove_from_watchlist, get_watchlist,
)
from hypothesis import accuracy_report, recent_signals
from food_order import save_usual_order, list_usual_orders, prepare_food_order, checkout_food_order
from health import log_health, get_health_summary, METRICS
from socrates import start_thinking_session, end_thinking_session
from learning import log_learning, get_learning_history
from bills import add_bill, list_bills, mark_bill_paid, remove_bill, FREQUENCIES
from akahu_tool import get_account_balances, get_spending_report, get_detected_subscriptions
from intelligence import what_alfred_knows, get_observations, rate_observation, get_last_review
from confirmations import request_confirmation
from database import get_latest_market_brief, log_task


def get_market_brief():
    brief = get_latest_market_brief()
    if brief:
        return brief
    from market_pipeline import run_market_pipeline
    return run_market_pipeline(send_to_claude=False)


def _schema(properties=None, required=None):
    return {
        "type": "object",
        "properties": properties or {},
        "required": required or [],
    }


def _string(description):
    return {"type": "string", "description": description}


def _integer(description):
    return {"type": "integer", "description": description}


def _number(description):
    return {"type": "number", "description": description}


TICKER = _string("Stock ticker symbol, e.g. 'AAPL'. NZX stocks end in .NZ, e.g. 'FPH.NZ'.")


TOOLS = [
    # ---- General ----
    {
        "name": "web_search",
        "description": "Search the web for current information on any topic.",
        "input_schema": _schema({"query": _string("The search query.")}, ["query"]),
        "function": web_search,
    },
    {
        "name": "get_weather",
        "description": "Get current weather for a location. Jay lives in Taupo, New Zealand.",
        "input_schema": _schema({"location": _string("Place name, e.g. 'Taupo'.")}, ["location"]),
        "function": get_weather,
    },
    {
        "name": "calculate",
        "description": "Evaluate a maths expression. Supports + - * / ** %, sqrt, round, abs, min, max, log, pi.",
        "input_schema": _schema({"expression": _string("e.g. '2 + 2 * (3 - 1)'")}, ["expression"]),
        "function": calculate,
    },
    {
        "name": "get_alfred_preference",
        "description": "Look up a stored preference or fact about Jay by key.",
        "input_schema": _schema({"key": _string("e.g. 'favourite_food'")}, ["key"]),
        "function": get_alfred_preference,
    },
    {
        "name": "save_alfred_preference",
        "description": "Store a lasting preference or fact about Jay when he tells you one (e.g. coffee order, dietary needs).",
        "input_schema": _schema(
            {"key": _string("Short snake_case key, e.g. 'coffee_order'"), "value": _string("The value to remember")},
            ["key", "value"],
        ),
        "function": save_alfred_preference,
    },
    # ---- Calendar ----
    {
        "name": "get_upcoming_events",
        "description": "List upcoming calendar events. Each line starts with [event_id], needed to edit or delete.",
        "input_schema": _schema({"max_results": _integer("How many events, default 10.")}),
        "function": get_upcoming_events,
    },
    {
        "name": "get_events_for_day",
        "description": "List calendar events on one specific day (NZ time).",
        "input_schema": _schema({"date_str": _string("YYYY-MM-DD. Omit for today.")}),
        "function": get_events_for_day,
    },
    {
        "name": "add_event",
        "description": "Add an event to Jay's calendar. Times are NZ local time.",
        "input_schema": _schema(
            {
                "summary": _string("Event title."),
                "start_time": _string("ISO 8601 start, e.g. 2026-10-02T14:00:00"),
                "end_time": _string("ISO 8601 end."),
                "description": _string("Optional notes."),
            },
            ["summary", "start_time", "end_time"],
        ),
        "function": add_event,
    },
    {
        "name": "edit_event",
        "description": "Edit an existing calendar event. Get the event_id from get_upcoming_events first.",
        "input_schema": _schema(
            {
                "event_id": _string("The event's ID."),
                "summary": _string("New title."),
                "start_time": _string("New ISO 8601 start."),
                "end_time": _string("New ISO 8601 end."),
                "description": _string("New description."),
            },
            ["event_id"],
        ),
        "function": edit_event,
    },
    {
        "name": "delete_event",
        "description": "Delete a calendar event. Get the event_id from get_upcoming_events first. Jay confirms with a button.",
        "input_schema": _schema({"event_id": _string("The event's ID.")}, ["event_id"]),
        "function": delete_event,
        "requires_confirmation": True,
        "describe": lambda args: f"🗑 Delete calendar event {args['event_id']}",
    },
    {
        "name": "get_free_slots",
        "description": "Find free time between 8am and 10pm on a given day.",
        "input_schema": _schema({"date_str": _string("YYYY-MM-DD")}, ["date_str"]),
        "function": get_free_slots,
    },
    # ---- Gmail ----
    {
        "name": "get_unread_emails",
        "description": "Get unread emails (sender, subject, snippet).",
        "input_schema": _schema({"max_results": _integer("How many, default 10.")}),
        "function": get_unread_emails,
    },
    {
        "name": "search_emails",
        "description": "Search Gmail using Gmail search syntax.",
        "input_schema": _schema(
            {
                "query": _string("e.g. 'from:alice subject:meeting newer_than:7d'"),
                "max_results": _integer("How many, default 10."),
            },
            ["query"],
        ),
        "function": search_emails,
    },
    {
        "name": "create_draft",
        "description": "Create a Gmail draft for Jay to review. Prefer this over send_email unless Jay says send.",
        "input_schema": _schema(
            {"to": _string("Recipient email."), "subject": _string("Subject."), "body": _string("Plain-text body.")},
            ["to", "subject", "body"],
        ),
        "function": create_draft,
    },
    {
        "name": "send_email",
        "description": "Send an email from Jay's Gmail. Jay confirms with a button before it sends.",
        "input_schema": _schema(
            {"to": _string("Recipient email."), "subject": _string("Subject."), "body": _string("Plain-text body.")},
            ["to", "subject", "body"],
        ),
        "function": send_email,
        "requires_confirmation": True,
        "describe": lambda args: (
            f"📧 Send email to {args['to']}\nSubject: {args['subject']}\n\n{args['body']}"
        ),
    },
    # ---- Finance ----
    {
        "name": "get_ticker_info",
        "description": "Current price, P/E, 52-week range, moving averages and RSI for a stock.",
        "input_schema": _schema({"ticker": TICKER}, ["ticker"]),
        "function": get_ticker_info,
    },
    {
        "name": "add_to_portfolio",
        "description": "Record a holding in Jay's portfolio (replaces any existing entry for that ticker).",
        "input_schema": _schema(
            {"ticker": TICKER, "shares": _number("Number of shares."), "avg_buy_price": _number("Average buy price.")},
            ["ticker", "shares", "avg_buy_price"],
        ),
        "function": add_to_portfolio,
    },
    {
        "name": "remove_from_portfolio",
        "description": "Remove a holding from Jay's portfolio.",
        "input_schema": _schema({"ticker": TICKER}, ["ticker"]),
        "function": remove_from_portfolio,
    },
    {
        "name": "get_portfolio_summary",
        "description": "Jay's holdings with current value and profit/loss.",
        "input_schema": _schema(),
        "function": get_portfolio_summary,
    },
    {
        "name": "add_to_watchlist",
        "description": "Add a stock to the watchlist. Alfred scans it overnight and alerts on big daily moves.",
        "input_schema": _schema(
            {"ticker": TICKER, "threshold_percent": _number("Daily move % that triggers an alert, default 5.")},
            ["ticker"],
        ),
        "function": add_to_watchlist,
    },
    {
        "name": "remove_from_watchlist",
        "description": "Remove a stock from the watchlist.",
        "input_schema": _schema({"ticker": TICKER}, ["ticker"]),
        "function": remove_from_watchlist,
    },
    {
        "name": "get_watchlist",
        "description": "List the stocks on Jay's watchlist.",
        "input_schema": _schema(),
        "function": get_watchlist,
    },
    {
        "name": "get_market_brief",
        "description": "The overnight technical signal brief for the watchlist and portfolio.",
        "input_schema": _schema(),
        "function": get_market_brief,
    },
    {
        "name": "get_recent_signals",
        "description": "Signals Alfred has logged recently.",
        "input_schema": _schema({"days": _integer("How many days back, default 7.")}),
        "function": recent_signals,
    },
    {
        "name": "get_prediction_accuracy",
        "description": "Alfred's honest track record: how often each signal type turned out right.",
        "input_schema": _schema(),
        "function": accuracy_report,
    },
    # ---- Food ----
    {
        "name": "save_usual_order",
        "description": "Save a named usual food order, e.g. 'friday burger'.",
        "input_schema": _schema(
            {
                "name": _string("Short name for the order."),
                "restaurant": _string("Restaurant name as it appears on DoorDash."),
                "items": {"type": "array", "items": {"type": "string"}, "description": "Menu item names."},
                "notes": _string("Optional notes."),
            },
            ["name", "restaurant", "items"],
        ),
        "function": save_usual_order,
    },
    {
        "name": "list_usual_orders",
        "description": "List Jay's saved usual food orders.",
        "input_schema": _schema(),
        "function": list_usual_orders,
    },
    {
        "name": "prepare_food_order",
        "description": "Step 1 of ordering food: build the DoorDash cart for a saved usual order and read the total. Spends nothing. Takes ~30 seconds.",
        "input_schema": _schema({"order_name": _string("Name of a saved usual order.")}, ["order_name"]),
        "function": prepare_food_order,
    },
    {
        "name": "checkout_food_order",
        "description": "Step 2 of ordering food: place the prepared order. Only call after prepare_food_order succeeded. Jay confirms with a button.",
        "input_schema": _schema(
            {"order_name": _string("Name of the order."), "expected_total": _number("Total from prepare_food_order, NZD.")},
            ["order_name", "expected_total"],
        ),
        "function": checkout_food_order,
        "requires_confirmation": True,
        "describe": lambda args: f"🍔 Order '{args['order_name']}' for NZ${args['expected_total']:.2f}",
    },
    # ---- Phase 3: Health ----
    {
        "name": "log_health",
        "description": (
            "Log one health measurement when Jay mentions it (call once per number). "
            "E.g. 'slept 6 hours, energy 5' → two calls. Metrics: "
            + "; ".join(f"{name} = {desc}" for name, (desc, _, _) in METRICS.items())
        ),
        "input_schema": _schema(
            {
                "metric": {"type": "string", "enum": list(METRICS)},
                "value": _number("The number."),
                "note": _string("Optional context Jay gave, e.g. 'woke at 3am'."),
                "date": _string("YYYY-MM-DD if he's logging a past day. Omit for today."),
            },
            ["metric", "value"],
        ),
        "function": log_health,
    },
    {
        "name": "get_health_summary",
        "description": "Jay's recent health logs compared to his OWN baseline.",
        "input_schema": _schema({"days": _integer("Window, default 7.")}),
        "function": get_health_summary,
    },
    # ---- Phase 8: Socrates ----
    {
        "name": "start_thinking_session",
        "description": "Start Socrates mode when Jay says 'think through this with me' or similar. You then question instead of answering.",
        "input_schema": _schema({"topic": _string("What he wants to think through.")}, ["topic"]),
        "function": start_thinking_session,
    },
    {
        "name": "end_thinking_session",
        "description": "End Socrates mode when Jay is done. Save an honest summary and the questions still open.",
        "input_schema": _schema(
            {"summary": _string("What he explored and where he landed."),
             "open_questions": _string("Questions still unresolved.")},
            ["summary"],
        ),
        "function": end_thinking_session,
    },
    # ---- Phase 7: Cooking and learning ----
    {
        "name": "log_learning",
        "description": "Log a practice session (a meal cooked, a workout, a repair) so difficulty can adapt over time.",
        "input_schema": _schema(
            {
                "domain": _string("e.g. cooking, fitness, diy, plants, coding"),
                "activity": _string("What he did, e.g. 'pan-seared salmon'"),
                "notes": _string("How it went, technique notes."),
                "self_rating": _integer("His rating 1-10, if given."),
                "difficulty": _string("easy / medium / hard"),
            },
            ["domain", "activity"],
        ),
        "function": log_learning,
    },
    {
        "name": "get_learning_history",
        "description": "Jay's learning history, optionally for one domain. Check before suggesting recipes or exercises.",
        "input_schema": _schema({"domain": _string("e.g. cooking. Omit for all.")}),
        "function": get_learning_history,
    },
    # ---- Phase 2: Bills ----
    {
        "name": "add_bill",
        "description": "Track a recurring bill or subscription. Alfred reminds Jay 3 days before it's due.",
        "input_schema": _schema(
            {
                "name": _string("e.g. 'power', 'netflix'"),
                "amount": _number("NZD."),
                "frequency": {"type": "string", "enum": list(FREQUENCIES)},
                "next_due": _string("YYYY-MM-DD"),
                "category": _string("e.g. utilities, entertainment"),
                "is_subscription": {"type": "boolean", "description": "True for subscriptions like Netflix."},
            },
            ["name", "amount", "frequency", "next_due"],
        ),
        "function": add_bill,
    },
    {
        "name": "list_bills",
        "description": "All tracked bills and subscriptions with due dates and monthly total.",
        "input_schema": _schema(),
        "function": list_bills,
    },
    {
        "name": "mark_bill_paid",
        "description": "Mark a bill paid; moves its due date to the next cycle.",
        "input_schema": _schema({"name": _string("Bill name.")}, ["name"]),
        "function": mark_bill_paid,
    },
    {
        "name": "remove_bill",
        "description": "Stop tracking a bill.",
        "input_schema": _schema({"name": _string("Bill name.")}, ["name"]),
        "function": remove_bill,
    },
    # ---- Phase 2: Banking (Akahu, read-only) ----
    {
        "name": "get_account_balances",
        "description": "Jay's bank account balances via Akahu.",
        "input_schema": _schema(),
        "function": get_account_balances,
    },
    {
        "name": "get_spending_report",
        "description": "Spending by category for a month vs the month before, via Akahu.",
        "input_schema": _schema({"month": _string("YYYY-MM. Omit for this month.")}),
        "function": get_spending_report,
    },
    {
        "name": "get_detected_subscriptions",
        "description": "Recurring charges Alfred detected in Jay's bank transactions.",
        "input_schema": _schema(),
        "function": get_detected_subscriptions,
    },
    # ---- Phase 4: Intelligence layer ----
    {
        "name": "what_alfred_knows",
        "description": "Answer 'what do you know about me', 'how accurate have you been', 'what don't you understand about me yet'.",
        "input_schema": _schema(),
        "function": what_alfred_knows,
    },
    {
        "name": "get_observations",
        "description": "Patterns Alfred has noticed. include_logged=true also shows quiet tier 1-2 ones.",
        "input_schema": _schema({"include_logged": {"type": "boolean", "description": "Include unsurfaced ones."}}),
        "function": get_observations,
    },
    {
        "name": "rate_observation",
        "description": "Record whether Jay thinks an observation was right. Use when he responds to one.",
        "input_schema": _schema(
            {"observation_id": _integer("The # number."),
             "accurate": {"type": "boolean", "description": "Did he say it was right?"},
             "note": _string("His comment.")},
            ["observation_id", "accurate"],
        ),
        "function": rate_observation,
    },
    {
        "name": "get_last_review",
        "description": "The most recent weekly, monthly or quarterly life review.",
        "input_schema": _schema({"period": {"type": "string", "enum": ["weekly", "monthly", "quarterly"]}}),
        "function": get_last_review,
    },
]

# name → tool entry, built once. This dict replaces the old elif chain.
TOOLS_BY_NAME = {tool["name"]: tool for tool in TOOLS}

# What gets sent to Claude: only the keys the API understands.
CLAUDE_TOOL_SCHEMAS = [
    {key: tool[key] for key in ("name", "description", "input_schema")}
    for tool in TOOLS
]
# Prompt caching: the tool list is identical on every request, so mark
# the end of it as cacheable. Later calls re-use it at ~10% of the cost.
CLAUDE_TOOL_SCHEMAS[-1]["cache_control"] = {"type": "ephemeral"}


def describe_action(name, tool_input):
    """Human-readable summary shown next to the Confirm button.
    Each gated tool supplies its own "describe" in TOOLS — same pattern as routing."""
    describe = TOOLS_BY_NAME.get(name, {}).get("describe")
    if describe:
        return describe(tool_input)
    return f"{name}: {tool_input}"


def run_tool(name, tool_input):
    """Run one tool call from Claude.

    Returns (result_text, is_error, pending_action_id).
    pending_action_id is set when the tool was parked for confirmation.
    """
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        return f"Unknown tool: {name}", True, None

    if tool.get("requires_confirmation"):
        action_id = request_confirmation(
            name, tool["function"], tool_input, describe_action(name, tool_input)
        )
        log_task(name, tool_input, "awaiting_confirmation")
        return (
            "NOT DONE YET. This action is waiting for Jay to tap Confirm under your message. "
            "Tell him what you've prepared and that it needs his confirmation. "
            "Do not say it has been done.",
            False,
            action_id,
        )

    try:
        result = tool["function"](**tool_input)
        return str(result), False, None
    except Exception as e:
        # Full details go to the log only. Claude gets the error TYPE (a
        # TypeError usually means it passed wrong arguments, so it can retry)
        # but never the raw message, which can contain paths or API internals.
        ref = uuid.uuid4().hex[:6]
        logging.exception(f"[ref {ref}] Tool {name} failed")
        log_task(name, tool_input, f"error ({type(e).__name__}, ref {ref})")
        return (
            f"The {name} tool failed ({type(e).__name__}, ref {ref}). "
            "Tell Jay it didn't work; don't guess at the result.",
            True,
            None,
        )
