import sqlite3
from config import DB_PATH


def get_connection():
    # The scheduler thread (5am pipeline, reminders) and the Telegram
    # handlers write to this file at the same time.
    # timeout / busy_timeout: wait up to 30s for a lock instead of failing
    #   instantly with "database is locked".
    # WAL: readers no longer block the writer (and vice versa). The setting
    #   is stored in the file itself, so it sticks after the first call.
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   timestamp TEXT,
                   user_message TEXT,
                   alfred_response TEXT
            )
        """
    )
    conn.commit()
    conn.close()

    init_preferences_table()
    init_task_history_table()
    init_watchlist_table()
    init_portfolio_table()
    init_hypothesis_table()
    init_usual_orders_table()
    init_market_briefs_table()
    init_life_tables()


def log_conversation(user_message, alfred_response):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO conversations (timestamp, user_message, alfred_response)
        VALUES (datetime('now'), ?, ?)
                   """,
        (user_message, alfred_response),
    )
    conn.commit()
    conn.close()


def get_recent_conversations(limit=6, max_age_minutes=60):
    """Last few exchanges, oldest first — Alfred's short-term memory.

    Only exchanges from the last `max_age_minutes` count, so a message
    from yesterday doesn't get treated as part of today's chat.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT user_message, alfred_response FROM conversations
        WHERE timestamp >= datetime('now', ?)
        ORDER BY id DESC LIMIT ?
        """,
        (f"-{max_age_minutes} minutes", limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return list(reversed(rows))


def init_preferences_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            value TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def save_preference(key, value):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO preferences (key, value, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(key) DO UPDATE SET
            value=excluded.value,
            updated_at=datetime('now')
        """,
        (key, value),
    )
    conn.commit()
    conn.close()


def get_preference(key):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT value FROM preferences WHERE key = ?
        """,
        (key,),
    )
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def get_all_preferences():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM preferences ORDER BY key")
    rows = cursor.fetchall()
    conn.close()
    return rows


def init_task_history_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS task_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            action TEXT,
            detail TEXT,
            status TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def log_task(action, detail, status):
    """Audit log — every action Alfred takes gets a timestamped row."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO task_history (timestamp, action, detail, status)
        VALUES (datetime('now'), ?, ?, ?)
        """,
        (action, str(detail)[:1000], status),
    )
    conn.commit()
    conn.close()


def init_watchlist_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        create table if not exists watchlist(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT UNIQUE,
        alert_threshold_percent REAL DEFAULT 5.0,
        date_added TEXT)
   """
    )
    conn.commit()
    conn.close()


def init_portfolio_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        create table if not exists portfolio(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT UNIQUE,
        shares REAL,
        avg_buy_price REAL,
        date_added TEXT)
   """
    )
    conn.commit()
    conn.close()


def init_hypothesis_table():
    """Every signal Alfred raises is logged here, then graded later.

    result_price / return_percent / accurate start as NULL and are
    filled in by evaluate_hypotheses() once the timeframe has passed.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS hypothesis_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            symbol TEXT,
            signal_type TEXT,
            direction TEXT,
            reasoning TEXT,
            confidence TEXT,
            timeframe_days INTEGER,
            entry_price REAL,
            result_price REAL,
            return_percent REAL,
            accurate INTEGER,
            evaluated_at TEXT,
            UNIQUE(date, symbol, signal_type)
        )
        """
    )
    conn.commit()
    conn.close()


def init_market_briefs_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS market_briefs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            content TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def save_market_brief(content):
    conn = get_connection()
    conn.execute(
        "INSERT INTO market_briefs (created_at, content) VALUES (datetime('now'), ?)",
        (content,),
    )
    conn.commit()
    conn.close()


def get_latest_market_brief(max_age_hours=20):
    conn = get_connection()
    row = conn.execute(
        """
        SELECT content FROM market_briefs
        WHERE created_at >= datetime('now', ?)
        ORDER BY id DESC LIMIT 1
        """,
        (f"-{max_age_hours} hours",),
    ).fetchone()
    conn.close()
    return row[0] if row else None


def init_life_tables():
    """Tables for the full-version phases (health, intelligence layer,
    Socrates, learning, bills, news). One function because they were
    all added together — each block says which phase it belongs to."""
    conn = get_connection()
    cursor = conn.cursor()

    # Phase 3 — health. One row per measurement, so new metrics
    # (and later Oura/Withings data via `source`) need no schema change.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS health_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            date TEXT,
            metric TEXT,
            value REAL,
            note TEXT,
            source TEXT DEFAULT 'manual'
        )
        """
    )

    # Phase 4 — the intelligence layer. Every observation is logged,
    # surfaced or not, with the prediction and whether it came true.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            observation TEXT,
            domains TEXT,
            data_points INTEGER,
            tier INTEGER,
            known_explanation TEXT,
            alternatives TEXT,
            actionable INTEGER,
            draft_message TEXT,
            prediction TEXT,
            status TEXT DEFAULT 'logged',
            surfaced_at TEXT,
            jay_rating INTEGER,
            jay_note TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            period TEXT,
            content TEXT
        )
        """
    )

    # Phase 8 — Socrates thinking sessions
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS thinking_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT,
            ended_at TEXT,
            topic TEXT,
            summary TEXT,
            open_questions TEXT
        )
        """
    )

    # Phase 7 — cooking and learning history
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS learning_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            domain TEXT,
            activity TEXT,
            notes TEXT,
            self_rating INTEGER,
            difficulty TEXT
        )
        """
    )

    # Phase 2 — bills and subscriptions
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            amount REAL,
            frequency TEXT,
            anchor_day INTEGER,
            next_due TEXT,
            category TEXT,
            is_subscription INTEGER DEFAULT 0,
            last_paid TEXT,
            reminded_for TEXT
        )
        """
    )

    # Phase 6 — news intelligence
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS news_items (
            id TEXT PRIMARY KEY,
            fetched_at TEXT,
            published TEXT,
            source TEXT,
            title TEXT,
            link TEXT,
            query TEXT,
            processed INTEGER DEFAULT 0,
            analysis TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def init_usual_orders_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS usual_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            restaurant TEXT,
            items TEXT,
            notes TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()
