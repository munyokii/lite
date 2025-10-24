"""Test your internet speed using lite"""
import asyncio
import sqlite3
from datetime import datetime
import speedtest as st

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

if __name__ == "__main__":
    init_db()
    asyncio.run(speed_test_async())
