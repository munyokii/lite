"""Test your internet speed using lite"""
import time
import asyncio
import sqlite3
from datetime import datetime
import schedule
import speedtest as st
import matplotlib.pyplot as plt
import pandas as pd

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

async def speed_test_async():
    """Asynchronous speed test function using asyncio.to_thread"""
    print('Starting speed test...')

    test = st.Speedtest()

    await asyncio.to_thread(test.get_best_server)
    best_server = test.get_best_server()
    server_name = best_server['sponsor']

    print('Testing download speed...')
    down_speed = await asyncio.to_thread(test.download)
    down_speed_mbps = round(down_speed / 10**6, 2)
    print(f'Download Speed: {down_speed_mbps} Mbps')

    print('Testing upload speed...')
    up_speed = await asyncio.to_thread(test.upload)
    up_speed_mbps = round(up_speed / 10**6, 2)
    print(f'Upload Speed: {up_speed_mbps} Mbps')

    ping = test.results.ping
    print('Ping:', ping)

    await asyncio.to_thread(save_results, down_speed_mbps,
                            up_speed_mbps, ping, server_name)

def save_results(download, upload, ping, server):
    """Saving test results to database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO speed_results (download, upload, ping, server, timestamp)
                   VALUES(?, ?, ?, ?, ?)
    """, (download, upload, ping, server, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    print('Results saved successfully')

def show_weekly_speed_trends():
    """Visualize weekly average internet speeds using Matplotlib"""
    conn = sqlite3.connect(DB_NAME)

    df = pd.read_sql_query("SELECT * FROM speed_results", conn)
    conn.close()

    if df.empty:
        print("No data found in database.")
        return

    df['timestamp'] = pd.to_datetime(df['timestamp'])

    df['week'] = df['timestamp'].dt.strftime('%Y-W%U')

    weekly_avg = (
        df.groupby('week')[['download', 'upload']]
        .mean()
        .reset_index()
    )

    plt.figure(figsize=(10, 6))
    plt.plot(weekly_avg['week'], weekly_avg['download'], label='Download (Mbps)', marker='o')
    plt.plot(weekly_avg['week'], weekly_avg['upload'], label='Upload (Mbps)', marker='o')

    plt.title('Average Internet Speed per Week')
    plt.xlabel('Week')
    plt.ylabel('Speed (Mbps)')
    plt.xticks(rotation=45)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    plt.show()

def run_test():
    """Running speed test hourly"""
    asyncio.run(speed_test_async())

if __name__ == "__main__":
    init_db()
    show_weekly_speed_trends()
    schedule.every().hour.do(run_test)
    print("Running hourly speed test. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(1)
