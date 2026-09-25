"""
Phase 2 — Bills and subscriptions.

Power, internet, phone, Netflix... Alfred tracks when each is due,
reminds Jay 3 days before (once per due date), and moves the due date
forward when he says it's paid. Akahu (akahu_tool.py) can later
detect subscriptions automatically; this works without it.
"""
import calendar
from datetime import date, timedelta
from database import get_connection, log_task

FREQUENCIES = ("weekly", "fortnightly", "monthly", "quarterly", "yearly")
REMIND_DAYS_BEFORE = 3


def add_months(day, months, anchor_day):
    """Move `day` forward by `months`, landing on anchor_day or the last
    day of the month if that month is shorter (31st → 28 Feb → 31 Mar)."""
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(anchor_day, last_day))


def next_due_after(current, frequency, anchor_day):
    if frequency == "weekly":
        return current + timedelta(weeks=1)
    if frequency == "fortnightly":
        return current + timedelta(weeks=2)
    if frequency == "monthly":
        return add_months(current, 1, anchor_day)
    if frequency == "quarterly":
        return add_months(current, 3, anchor_day)
    if frequency == "yearly":
        return add_months(current, 12, anchor_day)
    raise ValueError(f"Unknown frequency {frequency}")


def add_bill(name, amount, frequency, next_due, category="", is_subscription=False):
    frequency = frequency.lower()
    if frequency not in FREQUENCIES:
        return f"Frequency must be one of: {', '.join(FREQUENCIES)}"
    due = date.fromisoformat(next_due)
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO bills (name, amount, frequency, anchor_day, next_due, category, is_subscription)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            amount = excluded.amount, frequency = excluded.frequency,
            anchor_day = excluded.anchor_day, next_due = excluded.next_due,
            category = excluded.category, is_subscription = excluded.is_subscription
        """,
        (name.lower(), amount, frequency, due.day, due.isoformat(), category, int(is_subscription)),
    )
    conn.commit()
    conn.close()
    return f"Tracking {name}: ${amount:.2f} {frequency}, next due {due:%d %b}."


def list_bills():
    conn = get_connection()
    rows = conn.execute(
        "SELECT name, amount, frequency, next_due, is_subscription FROM bills ORDER BY next_due"
    ).fetchall()
    conn.close()
    if not rows:
        return "No bills tracked yet."
    monthly_total = sum(monthly_equivalent(amount, freq) for _, amount, freq, _, _ in rows)
    lines = [
        f"{name}{' (sub)' if sub else ''}: ${amount:.2f} {freq}, due {due}"
        for name, amount, freq, due, sub in rows
    ]
    lines.append(f"\nRoughly ${monthly_total:,.2f} a month in total.")
    return "\n".join(lines)


def monthly_equivalent(amount, frequency):
    per_year = {"weekly": 52, "fortnightly": 26, "monthly": 12, "quarterly": 4, "yearly": 1}
    return amount * per_year[frequency] / 12


def mark_bill_paid(name, paid_on=None):
    conn = get_connection()
    row = conn.execute(
        "SELECT frequency, anchor_day, next_due FROM bills WHERE name = ?", (name.lower(),)
    ).fetchone()
    if not row:
        conn.close()
        return f"No bill called '{name}'."
    frequency, anchor_day, next_due = row
    new_due = next_due_after(date.fromisoformat(next_due), frequency, anchor_day)
    conn.execute(
        "UPDATE bills SET last_paid = ?, next_due = ?, reminded_for = NULL WHERE name = ?",
        (paid_on or date.today().isoformat(), new_due.isoformat(), name.lower()),
    )
    conn.commit()
    conn.close()
    log_task("bill_paid", name, "success")
    return f"{name} marked paid. Next due {new_due:%d %b %Y}."


def remove_bill(name):
    conn = get_connection()
    cursor = conn.execute("DELETE FROM bills WHERE name = ?", (name.lower(),))
    conn.commit()
    conn.close()
    return f"Stopped tracking {name}." if cursor.rowcount else f"No bill called '{name}'."


def bills_needing_reminder(today=None):
    """Bills due within REMIND_DAYS_BEFORE days (or overdue) that haven't
    been reminded about for this due date. Marks them reminded —
    so the daily job is idempotent."""
    today = today or date.today()
    horizon = (today + timedelta(days=REMIND_DAYS_BEFORE)).isoformat()
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT name, amount, next_due FROM bills
        WHERE next_due <= ? AND (reminded_for IS NULL OR reminded_for != next_due)
        """,
        (horizon,),
    ).fetchall()
    for name, _, next_due in rows:
        conn.execute("UPDATE bills SET reminded_for = ? WHERE name = ?", (next_due, name))
    conn.commit()
    conn.close()
    reminders = []
    for name, amount, next_due in rows:
        days = (date.fromisoformat(next_due) - today).days
        when = "is OVERDUE" if days < 0 else "is due today" if days == 0 else f"is due in {days} day(s)"
        reminders.append(f"{name} (${amount:.2f}) {when}")
    return reminders
