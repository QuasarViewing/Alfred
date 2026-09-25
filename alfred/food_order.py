"""
Milestone 8 — Alfred orders food (Playwright browser automation).

SAFETY MODEL — three layers:
  1. prepare_food_order() only builds a cart. No money moves.
  2. checkout_food_order() is behind the confirmation gate — Jay must
     tap ✅ in Telegram before it runs.
  3. ALFRED_ORDER_DRY_RUN=true (the default) stops one click short of
     "Place order". And any cart over ALFRED_ORDER_MAX_NZD is refused.

FIRST-TIME SETUP (once):
    py food_order.py login
A real browser window opens. Log in to DoorDash by hand. The session
is saved in browser_profile/, so Alfred never sees or stores your password.

CALIBRATION:
Websites change their HTML all the time. Every page element Alfred
looks for lives in SELECTORS below. When something breaks, run
    py food_order.py test "<usual order name>"
which runs the cart-building step with a visible browser and saves
screenshots to screenshots/ so you can see where it got stuck.
"""
import json
import logging
import re
import sys
from datetime import datetime
from config import BROWSER_PROFILE_DIR, SCREENSHOT_DIR, ORDER_DRY_RUN, ORDER_MAX_NZD
from database import get_connection, log_task

DOORDASH_URL = "https://www.doordash.com"

# Text-based selectors survive redesigns better than CSS class names.
# NOT yet verified against the live NZ site — calibrate with `test`.
SELECTORS = {
    "search_box": "input[placeholder*='Search' i]",
    "store_result": "a[href*='/store/']",
    "item_by_name": "[data-anchor-id='MenuItem']",
    "add_to_cart_button": "button:has-text('Add to cart')",
    "cart_button": "[data-testid='OrderCartIconButton'], button:has-text('Cart')",
    "checkout_button": "a:has-text('Checkout'), button:has-text('Checkout')",
    "order_total": "[data-testid='OrderTotal'], :text('Total') >> xpath=..",
    "place_order_button": "button:has-text('Place Order')",
}


# ---------- Saved "usual" orders (SQLite) ----------

def save_usual_order(name, restaurant, items, notes=""):
    """items: list of item names exactly as they appear on the menu."""
    try:
        if isinstance(items, str):
            items = [i.strip() for i in items.split(",") if i.strip()]
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO usual_orders (name, restaurant, items, notes, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(name) DO UPDATE SET
                restaurant = excluded.restaurant,
                items = excluded.items,
                notes = excluded.notes,
                updated_at = datetime('now')
            """,
            (name.lower(), restaurant, json.dumps(items), notes),
        )
        conn.commit()
        conn.close()
        return f"Saved usual order '{name}': {', '.join(items)} from {restaurant}."
    except Exception as e:
        return f"Error saving usual order: {e}"


def get_usual_order(name):
    conn = get_connection()
    row = conn.execute(
        "SELECT name, restaurant, items, notes FROM usual_orders WHERE name = ?",
        (name.lower(),),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {"name": row[0], "restaurant": row[1], "items": json.loads(row[2]), "notes": row[3]}


def list_usual_orders():
    conn = get_connection()
    rows = conn.execute("SELECT name, restaurant, items FROM usual_orders ORDER BY name").fetchall()
    conn.close()
    if not rows:
        return "No usual orders saved yet."
    return "\n".join(f"{n}: {', '.join(json.loads(i))} from {r}" for n, r, i in rows)


# ---------- Helpers ----------

def parse_price(text):
    """'Total NZ$34.50' → 34.5. Returns None if no price is found."""
    match = re.search(r"(\d{1,4}(?:,\d{3})*\.\d{2})", text or "")
    return float(match.group(1).replace(",", "")) if match else None


def _screenshot(page, label):
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-{label}.png"
    page.screenshot(path=str(path), full_page=False)
    return path


def _open_browser(playwright, headless=True):
    # A persistent context keeps cookies between runs — that's what
    # keeps Alfred logged in after the one-time manual login.
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        str(BROWSER_PROFILE_DIR),
        headless=headless,
        viewport={"width": 1280, "height": 900},
    )


def _read_total(page):
    page.locator(SELECTORS["cart_button"]).first.click()
    page.locator(SELECTORS["checkout_button"]).first.click()
    page.wait_for_load_state("networkidle")
    total_text = page.locator(SELECTORS["order_total"]).first.inner_text(timeout=15000)
    return parse_price(total_text)


# ---------- The two tool functions ----------

def prepare_food_order(order_name, headless=True):
    """Build the cart for a saved usual order and report the total. Spends nothing."""
    order = get_usual_order(order_name)
    if not order:
        return f"No usual order called '{order_name}'. Saved orders:\n{list_usual_orders()}"

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = _open_browser(p, headless=headless)
        page = browser.pages[0] if browser.pages else browser.new_page()
        try:
            page.goto(DOORDASH_URL, wait_until="domcontentloaded")
            page.locator(SELECTORS["search_box"]).first.fill(order["restaurant"])
            page.keyboard.press("Enter")
            page.locator(SELECTORS["store_result"]).first.click(timeout=20000)
            page.wait_for_load_state("domcontentloaded")

            missing = []
            for item in order["items"]:
                match = page.locator(SELECTORS["item_by_name"]).filter(has_text=item).first
                if match.count() == 0:
                    missing.append(item)
                    continue
                match.click()
                page.locator(SELECTORS["add_to_cart_button"]).first.click(timeout=10000)
                page.wait_for_timeout(1000)

            total = _read_total(page)
            shot = _screenshot(page, "cart")
        except Exception as e:
            shot = _screenshot(page, "error")
            log_task("prepare_food_order", f"{order_name}: {e}", "failed")
            return f"Couldn't build the cart ({e}). Screenshot saved to {shot.name}."
        finally:
            browser.close()

    log_task("prepare_food_order", f"{order_name} total={total}", "success")
    lines = [f"Cart ready: {', '.join(order['items'])} from {order['restaurant']}."]
    if missing:
        lines.append(f"Couldn't find on the menu: {', '.join(missing)}.")
    lines.append(f"Total: NZ${total:.2f}" if total else "Couldn't read the total.")
    if total and total > ORDER_MAX_NZD:
        lines.append(f"That's over your NZ${ORDER_MAX_NZD:.0f} limit, so I won't check out.")
    return "\n".join(lines)


def checkout_food_order(order_name, expected_total):
    """Place the order already sitting in the cart. GATED — only runs after Jay taps Confirm."""
    if expected_total > ORDER_MAX_NZD:
        return f"Refused: NZ${expected_total:.2f} is over the NZ${ORDER_MAX_NZD:.0f} limit."

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = _open_browser(p)
        page = browser.pages[0] if browser.pages else browser.new_page()
        try:
            page.goto(DOORDASH_URL, wait_until="domcontentloaded")
            total = _read_total(page)
            # The cart might have changed since Jay confirmed — prices,
            # fees, someone else's phone. Never charge more than he agreed to.
            if total is None or total > expected_total + 0.50:
                return f"Stopped: cart total is now {total}, not the NZ${expected_total:.2f} you confirmed."
            if ORDER_DRY_RUN:
                shot = _screenshot(page, "dry-run-checkout")
                log_task("checkout_food_order", f"{order_name} NZ${total} DRY RUN", "dry_run")
                return (
                    f"Dry run: everything was ready to order {order_name} for NZ${total:.2f}, "
                    f"but I stopped before 'Place order'. Screenshot: {shot.name}. "
                    "Set ALFRED_ORDER_DRY_RUN=false in .env to go live."
                )
            page.locator(SELECTORS["place_order_button"]).first.click()
            page.wait_for_load_state("networkidle")
            shot = _screenshot(page, "order-placed")
            log_task("checkout_food_order", f"{order_name} NZ${total} url={page.url}", "success")
            return f"Order placed: {order_name}, NZ${total:.2f}. Tracking: {page.url}"
        except Exception as e:
            _screenshot(page, "checkout-error")
            log_task("checkout_food_order", f"{order_name}: {e}", "failed")
            return f"Checkout failed ({e}). Nothing was ordered."
        finally:
            browser.close()


# ---------- Command line: login and calibration ----------

def login():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = _open_browser(p, headless=False)
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto(DOORDASH_URL)
        input("Log in to DoorDash in the browser window, then press Enter here...")
        browser.close()
    print(f"Session saved to {BROWSER_PROFILE_DIR}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from database import init_db
    init_db()
    if len(sys.argv) >= 2 and sys.argv[1] == "login":
        login()
    elif len(sys.argv) >= 3 and sys.argv[1] == "test":
        print(prepare_food_order(sys.argv[2], headless=False))
    else:
        print('Usage: py food_order.py login | py food_order.py test "<order name>"')
