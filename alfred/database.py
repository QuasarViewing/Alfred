import sqlite3


DB_PATH = "alfred.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


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
        average_price REAL,
        date_added TEXT)
   """
    )
    conn.commit()
    conn.close()