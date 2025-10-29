"""Database configurations"""
import sqlite3
from datetime import datetime, timedelta

DB_NAME = "speed_test.db"

def init_db():
    """Create DB and main table if not present; also create a meta table for app stats."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS speed_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        download REAL,
        upload REAL,
        ping REAL,
        server TEXT,
        server_country TEXT,
        timestamp TEXT,
        success INTEGER DEFAULT 1  -- 1 success, 0 failure
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS app_meta (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)

    conn.commit()
    conn.close()

def save_results(download, upload, ping, server, server_country, success=1):
    """Save a single result row to DB."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO speed_results (download, upload, ping, server, server_country, timestamp, success)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (download, upload, ping, server, server_country, datetime.now().isoformat(), success))
    conn.commit()
    conn.close()

def fetch_all():
    """Return all rows as list of dicts (useful for charts)."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, download, upload, ping, server, server_country, timestamp, success FROM speed_results ORDER BY timestamp;")
    rows = cur.fetchall()
    conn.close()
    return rows

def fetch_recent(n=50):
    """Fetching recent records"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM speed_results ORDER BY timestamp DESC LIMIT ?", (n,))
    rows = cur.fetchall()
    conn.close()
    return rows

def cleanup_old_records(days=90):
    """Delete records older than `days` days."""
    cutoff = datetime.now() - timedelta(days=days)
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM speed_results WHERE timestamp < ?", (cutoff.isoformat(),))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted

def count_consecutive_failures(limit=5):
    """Return number of consecutive failures from the latest rows (max limit)."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT success FROM speed_results ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    # rows like [(1,), (0,), ...]
    count = 0
    for r in rows:
        if r[0] == 0:
            count += 1
        else:
            break
    return count

def get_db_name():
    """Getting database name"""
    return DB_NAME

def upgrade_schema():
    """Upgrading database schema"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    columns_to_add = [
        ("server_country", "TEXT"),
        ("success", "INTEGER DEFAULT 1")
    ]

    for column, definition in columns_to_add:
        try:
            cur.execute(f"ALTER TABLE speed_results ADD COLUMN {column} {definition};")
        except Exception:
            pass  # Column already exists

    conn.commit()
    conn.close()

