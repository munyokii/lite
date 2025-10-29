"""Database Configuration"""
import sqlite3
from datetime import datetime

DB_NAME = 'speed_test.db'

def init_db():
    """Initialize the SQLITE database and create the table if it doesn't exist"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS speed_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            download REAL,
            upload REAL,
            ping REAL,
            server TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_results(download, upload, ping, server):
    """Saving test results to database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO speed_results (download, upload, ping, server, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (download, upload, ping, server, datetime.now().isoformat()))
    conn.commit()
    conn.close()
