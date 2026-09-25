"""
Phase 2 — Banking via Akahu (NZ open banking), READ-ONLY.

Setup (free personal app):
  1. my.akahu.nz → connect your bank accounts
  2. developers.akahu.nz → Developers page → copy the App ID Token and User Access Token
  3. .env:  AKAHU_APP_TOKEN=app_token_...   AKAHU_USER_TOKEN=user_token_...

API (developers.akahu.nz):
  base https://api.akahu.io/v1, headers  X-Akahu-Id: <app token>,
  Authorization: Bearer <user token>. GET /accounts, GET /transactions
  ?start=&end= (ISO dates), 100 per page, next page via ?cursor=<cursor.next>.
  amount < 0 = money out.

The analysis functions below are pure (list of transaction dicts in,
results out) so they're tested without a bank connection.
NOT YET VERIFIED against a live account.
"""
import logging
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean, median, pstdev
import httpx
from config import AKAHU_APP_TOKEN, AKAHU_USER_TOKEN

API = "https://api.akahu.io/v1"


def _tokens():
    return AKAHU_APP_TOKEN, AKAHU_USER_TOKEN


def akahu_connected():
    app, user = _tokens()
    return bool(app and user)


NOT_CONNECTED = (
    "Akahu isn't connected yet. Add AKAHU_APP_TOKEN and AKAHU_USER_TOKEN to .env "
    "(free personal app at developers.akahu.nz)."
)


def _get(path, params=None):
    app, user = _tokens()
    headers = {"X-Akahu-Id": app, "Authorization": f"Bearer {user}"}
    with httpx.Client(timeout=30) as client:
        response = client.get(f"{API}{path}", headers=headers, params=params)
        response.raise_for_status()
        return response.json()


def fetch_accounts():
    return _get("/accounts").get("items", [])


def fetch_transactions(start, end):
    """All transactions between start (exclusive) and end (inclusive), every page."""
    items, cursor = [], None
    while True:
        params = {"start": start, "end": end}
        if cursor:
            params["cursor"] = cursor
        page = _get("/transactions", params)
        items.extend(page.get("items", []))
        cursor = (page.get("cursor") or {}).get("next")
        if not cursor:
            return items


# ---------- pure analysis ----------

def merchant_name(txn):
    merchant = txn.get("merchant") or {}
    return (merchant.get("name") or txn.get("description") or "Unknown").strip()


def category_name(txn):
    category = txn.get("category") or {}
    groups = category.get("groups") or {}
    personal = groups.get("personal_finance") or {}
    return personal.get("name") or category.get("name") or "Uncategorised"


def spending_by_category(transactions):
    """Money OUT only, grouped by category, biggest first."""
    totals = defaultdict(float)
    for txn in transactions:
        if txn.get("amount", 0) < 0:
            totals[category_name(txn)] += -txn["amount"]
    return sorted(totals.items(), key=lambda item: item[1], reverse=True)


def detect_subscriptions(transactions, min_occurrences=3):
    """Same merchant, similar amount (±10%), roughly regular gaps.

    Returns [{merchant, amount, interval_days, last_date, next_expected}].
    """
    by_merchant = defaultdict(list)
    for txn in transactions:
        if txn.get("amount", 0) < 0:
            by_merchant[merchant_name(txn)].append(
                (date.fromisoformat(txn["date"][:10]), -txn["amount"])
            )

    found = []
    for merchant, charges in by_merchant.items():
        if len(charges) < min_occurrences:
            continue
        charges.sort()
        amounts = [a for _, a in charges]
        typical = median(amounts)
        if any(abs(a - typical) > 0.10 * typical for a in amounts[-min_occurrences:]):
            continue
        gaps = [(b[0] - a[0]).days for a, b in zip(charges, charges[1:])]
        interval = median(gaps)
        if interval < 6 or any(abs(g - interval) > max(3, 0.2 * interval) for g in gaps[-(min_occurrences - 1):]):
            continue
        last_date = charges[-1][0]
        found.append({
            "merchant": merchant,
            "amount": round(typical, 2),
            "interval_days": int(interval),
            "last_date": last_date.isoformat(),
            "next_expected": (last_date + timedelta(days=int(interval))).isoformat(),
        })
    return sorted(found, key=lambda s: s["next_expected"])


def unusual_transactions(history, recent, min_history=5):
    """Recent debits more than 3 standard deviations above what Jay
    normally spends in that category (his baseline, not anyone else's)."""
    by_category = defaultdict(list)
    for txn in history:
        if txn.get("amount", 0) < 0:
            by_category[category_name(txn)].append(-txn["amount"])
    flagged = []
    for txn in recent:
        if txn.get("amount", 0) >= 0:
            continue
        past = by_category.get(category_name(txn), [])
        if len(past) < min_history:
            continue
        threshold = mean(past) + 3 * pstdev(past)
        if -txn["amount"] > threshold:
            flagged.append((txn, round(threshold, 2)))
    return flagged


# ---------- tools ----------

def get_account_balances():
    if not akahu_connected():
        return NOT_CONNECTED
    try:
        lines = []
        for account in fetch_accounts():
            balance = account.get("balance") or {}
            current = balance.get("current")
            lines.append(f"{account.get('name', 'Account')}: ${current:,.2f}" if current is not None
                         else f"{account.get('name', 'Account')}: balance unavailable")
        return "\n".join(lines) or "No accounts found."
    except Exception as e:
        logging.exception("Akahu accounts failed")
        return f"Couldn't reach Akahu: {e}"


def get_spending_report(month=None):
    """month = 'YYYY-MM', default this month. Compares to the month before."""
    if not akahu_connected():
        return NOT_CONNECTED
    try:
        first = date.fromisoformat(f"{month}-01") if month else date.today().replace(day=1)
        prev_first = (first - timedelta(days=1)).replace(day=1)
        next_first = (first + timedelta(days=32)).replace(day=1)
        this_month = fetch_transactions((first - timedelta(days=1)).isoformat(), (next_first - timedelta(days=1)).isoformat())
        last_month = fetch_transactions((prev_first - timedelta(days=1)).isoformat(), (first - timedelta(days=1)).isoformat())
        now_totals = dict(spending_by_category(this_month))
        then_totals = dict(spending_by_category(last_month))
        lines = [f"Spending {first:%B %Y} (vs {prev_first:%B}):"]
        for category, amount in sorted(now_totals.items(), key=lambda i: -i[1]):
            before = then_totals.get(category, 0)
            change = f" ({amount - before:+,.0f})" if before else " (new)"
            lines.append(f"{category}: ${amount:,.2f}{change}")
        lines.append(f"Total out: ${sum(now_totals.values()):,.2f} vs ${sum(then_totals.values()):,.2f}")
        return "\n".join(lines)
    except Exception as e:
        logging.exception("Akahu spending report failed")
        return f"Couldn't build the spending report: {e}"


def get_detected_subscriptions():
    if not akahu_connected():
        return NOT_CONNECTED
    try:
        end = date.today()
        txns = fetch_transactions((end - timedelta(days=200)).isoformat(), end.isoformat())
        subs = detect_subscriptions(txns)
        if not subs:
            return "No regular subscriptions detected in the last 6 months."
        monthly = sum(s["amount"] * 30 / s["interval_days"] for s in subs)
        lines = [
            f"{s['merchant']}: ${s['amount']:.2f} every ~{s['interval_days']} days, next ~{s['next_expected']}"
            for s in subs
        ]
        lines.append(f"\n≈ ${monthly:,.2f}/month across {len(subs)} subscriptions.")
        return "\n".join(lines)
    except Exception as e:
        logging.exception("Akahu subscriptions failed")
        return f"Couldn't check subscriptions: {e}"


def daily_money_alerts(today=None):
    """For the daily job: subscriptions renewing in 3 days + unusual spending yesterday."""
    if not akahu_connected():
        return []
    today = today or date.today()
    alerts = []
    try:
        history = fetch_transactions((today - timedelta(days=200)).isoformat(), (today - timedelta(days=2)).isoformat())
        recent = fetch_transactions((today - timedelta(days=2)).isoformat(), today.isoformat())
        for sub in detect_subscriptions(history + recent):
            if sub["next_expected"] == (today + timedelta(days=3)).isoformat():
                alerts.append(f"{sub['merchant']} renews in ~3 days (${sub['amount']:.2f})")
        for txn, threshold in unusual_transactions(history, recent):
            alerts.append(
                f"Unusual: ${-txn['amount']:.2f} at {merchant_name(txn)} "
                f"(your usual max for {category_name(txn)} is ~${threshold:.0f})"
            )
    except Exception:
        logging.exception("Akahu daily alerts failed")
    return alerts
