"""Test your internet speed using lite"""
import time
import asyncio
import sqlite3
import threading
import pandas as pd
import tkinter as tk

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import speedtest as st
import schedule

from tkinter import ttk, messagebox

from db_config import DB_NAME, init_db, save_results

def log(message):
    """Function for displaying log messages"""
    log_box.insert(tk.END, message + "\n")
    log_box.see(tk.END)

def safe_log(message):
    try:
        window.after(0, log, message)
    except:
        pass

async def speed_test_async():
    """Asynchronous speed test function using asyncio.to_thread"""
    safe_log('Starting speed test...')

    try:
        test = st.Speedtest(secure=False)

        await asyncio.to_thread(test.get_servers, [])
        await asyncio.to_thread(test.get_best_server)
        best_server = test.get_best_server()
        server_name = best_server['sponsor']

        safe_log('Testing download speed...')
        down_speed = await asyncio.to_thread(test.download)
        down_speed_mbps = round(down_speed / 10**6, 2)

        safe_log('Testing upload speed...')
        up_speed = await asyncio.to_thread(test.upload)
        up_speed_mbps = round(up_speed / 10**6, 2)

        ping = test.results.ping
        safe_log(f"Download: {down_speed_mbps} Mbps | Upload: {up_speed_mbps} Mbps | Ping: {ping} ms")

        await asyncio.to_thread(save_results, down_speed_mbps,
                                up_speed_mbps, ping, server_name)
    except Exception as e:
        safe_log(f"Speedtest failed: {e}")


def show_weekly_speed_trends():
    """Visualize weekly average internet speeds using Matplotlib"""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM speed_results", conn)
    conn.close()

    if df.empty:
        messagebox.showinfo("No Data", "No speed test data available yet!")
        return

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['week'] = df['timestamp'].dt.strftime('%Y-W%U')
    weekly_avg = df.groupby('week')[['download', 'upload']].mean().reset_index()

    fig, ax = plt.subplots(figsize=(6, 4), dpi=100)
    ax.plot(weekly_avg['week'], weekly_avg['download'], marker='o', label='Download')
    ax.plot(weekly_avg['week'], weekly_avg['upload'], marker='o', label='Upload')
    ax.set_title("Weekly Average Internet Speeds")
    ax.set_xlabel("Week")
    ax.set_ylabel("Speed (Mbps)")
    ax.legend()
    ax.grid(True)

    for widget in chart_frame.winfo_children():
        widget.destroy()

    canvas = FigureCanvasTkAgg(fig, master=chart_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)


def run_test_threaded():
    threading.Thread(target=lambda: asyncio.run(speed_test_async())).start()

def show_trends_threaded():
    """Multi-threading to allow running of multiple tasks"""
    threading.Thread(target=show_weekly_speed_trends).start()

def scheduler_loop():
    """Scheduling the loop while condition is true"""
    while True:
        schedule.run_pending()
        time.sleep(1)


init_db()

window = tk.Tk()
window.title("Internet Speed Monitor")
window.geometry("900x600")

title_label = ttk.Label(window, text="Internet Speed Monitor Dashboard", font=("Fira Sans Condensed", 18))
title_label.pack(pady=10)

button_frame = ttk.Frame(window)
button_frame.pack(pady=5)

test_button = ttk.Button(button_frame, text="Run Speed Test Now", command=run_test_threaded)
test_button.grid(row=0, column=0, padx=10)

chart_button = ttk.Button(button_frame, text="Show Weekly Trend", command=show_weekly_speed_trends)
chart_button.grid(row=0, column=1, padx=10)

main_frame = ttk.Frame(window)
main_frame.pack(fill="both", expand=True, pady=10)

log_frame = ttk.LabelFrame(main_frame, text="Activity Log")
log_frame.pack(side="left", fill="both", expand=True, padx=10)

log_box = tk.Text(log_frame, height=20, width=50, wrap=tk.WORD)
log_box.pack(fill="both", expand=True)

chart_frame = ttk.LabelFrame(main_frame, text="Weekly Speed Chart")
chart_frame.pack(side="right", fill="both", expand=True, padx=10)

schedule.every(3).hours.do(lambda: window.after(0, run_test_threaded))
schedule.every().monday.at("08:00").do(lambda: window.after(0, show_weekly_speed_trends))

threading.Thread(target=scheduler_loop, daemon=True).start()

safe_log("Scheduler started. Running hourly tests + weekly chart updates")

window.mainloop()
