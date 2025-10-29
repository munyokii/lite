# main.py
"""
Hacker Matrix Style Internet Speed Monitor
Features:
- Embedded Matplotlib charts (weekly/monthly)
- PDF export (charts included)
- Outage detection (alerts on consecutive failures)
- Auto-cleanup of old DB records
- Thread-safe UI updates (window.after)
- Dark, terminal-like hacker UI
"""

import time
import asyncio
import threading
from datetime import datetime
import sqlite3

import tkinter as tk
from tkinter import messagebox, filedialog

import schedule

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends.backend_pdf import PdfPages

import speedtest

from db_config import init_db, save_results, cleanup_old_records, count_consecutive_failures, get_db_name, upgrade_schema

# ---------------------- Config ----------------------
CLEANUP_DAYS = 90        # auto-delete records older than this
OUTAGE_THRESHOLD = 4     # number of consecutive failures before alert
SCHEDULE_HOURS = 3       # interval between automatic tests
# ----------------------------------------------------

# Globals that must be available to threads safely (but GUI access via after())
window = None
log_box = None
chart_frame = None
status_label = None

# ---------------------- Utility / UI-safe helpers ----------------------
def safe_call(func, *args, **kwargs):
    """
    If called from non-main thread, dispatch to main thread using window.after.
    If in main thread, call directly.
    """
    try:
        if threading.current_thread() is threading.main_thread():
            return func(*args, **kwargs)
        else:
            window.after(0, lambda: func(*args, **kwargs))
    except Exception:
        # If window isn't ready or other issues, fallback to direct call
        try:
            return func(*args, **kwargs)
        except Exception:
            pass

def log(msg):
    """Insert a line into the UI log (must be called from main thread or via safe_call)."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    log_box.insert(tk.END, line + "\n")
    log_box.see(tk.END)

def safe_log(msg):
    """Safely displaying log messages"""
    safe_call(log, msg)

def show_alert(title, message):
    """Displaying alerts"""
    safe_call(messagebox.showwarning, title, message)

# ---------------------- Speedtest core ----------------------
async def speed_test_async():
    """Run the speedtest in a background thread-safe manner and save results."""
    safe_log("Starting speed test...")
    try:
        test = speedtest.Speedtest(secure=False)
        # refresh server list
        await asyncio.to_thread(test.get_servers, [])
        await asyncio.to_thread(test.get_best_server)
        best = test.get_best_server()
        server_name = best.get("sponsor", "unknown")
        server_country = best.get("country", "unknown")

        safe_log("Testing download...")
        down = await asyncio.to_thread(test.download)
        down_mbps = round(down / 10**6, 2)

        safe_log("Testing upload...")
        up = await asyncio.to_thread(test.upload)
        up_mbps = round(up / 10**6, 2)

        ping = test.results.ping if hasattr(test, "results") else None

        safe_log(f"OK: D={down_mbps} Mbps U={up_mbps} Mbps P={ping} ms  Server={server_name}")
        await asyncio.to_thread(save_results, down_mbps,
                                up_mbps, ping, server_name,
                                server_country, 1)

        # after a success, check cleanup in background
        await asyncio.to_thread(cleanup_old_records, CLEANUP_DAYS)

    except Exception as e:
        # Save a failure row (success=0) so outage detection can detect this
        safe_log(f"Speedtest failed: {e}")
        try:
            await asyncio.to_thread(save_results, None, None, None, "n/a", "n/a", 0)
        except Exception:
            pass

        # Check for outage threshold
        try:
            fails = count_consecutive_failures(limit=OUTAGE_THRESHOLD)
            if fails >= OUTAGE_THRESHOLD:
                show_alert("Connection Alert", f"{fails} consecutive speedtest failures detected.")
        except Exception:
            pass

def run_test_threaded():
    """Start async speed test in a thread so UI remains responsive."""
    threading.Thread(target=lambda: asyncio.run(speed_test_async()), daemon=True).start()

# ---------------------- Charting ----------------------
def _build_weekly_df():
    db = get_db_name()
    conn = sqlite3.connect(db)
    df = pd.read_sql_query("SELECT * FROM speed_results", conn, parse_dates=["timestamp"])
    conn.close()
    if df.empty:
        return None
    # only include successful tests
    df = df[df["success"] == 1].copy()
    df["week"] = df["timestamp"].dt.strftime("%Y-W%U")
    weekly = df.groupby("week")[["download","upload"]].mean().reset_index()
    return weekly

def _build_monthly_df():
    db = get_db_name()
    conn = sqlite3.connect(db)
    df = pd.read_sql_query("SELECT * FROM speed_results", conn, parse_dates=["timestamp"])
    conn.close()
    if df.empty:
        return None
    df = df[df["success"] == 1].copy()
    df["month"] = df["timestamp"].dt.to_period("M").astype(str)
    monthly = df.groupby("month")[["download","upload"]].mean().reset_index()
    return monthly

def show_weekly_speed_trends():
    """
    Embed the weekly chart into chart_frame (must run in main thread).
    """
    safe_log("Rendering weekly chart...")
    weekly = _build_weekly_df()
    if weekly is None or weekly.empty:
        safe_log("No successful speed test data yet to plot.")
        messagebox.showinfo("No Data", "Not enough data to plot weekly chart.")
        return

    # build figure
    fig, ax = plt.subplots(figsize=(7,4), dpi=100)
    ax.plot(weekly['week'], weekly['download'], marker='o', label='Download')
    ax.plot(weekly['week'], weekly['upload'], marker='o', label='Upload')
    ax.set_title("Weekly Avg Speeds")
    ax.set_xlabel("Week")
    ax.set_ylabel("Mbps")
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.4)
    plt.xticks(rotation=45)

    # clear previous
    for w in chart_frame.winfo_children():
        w.destroy()

    canvas = FigureCanvasTkAgg(fig, master=chart_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)

def show_monthly_speed_trends():
    """Showing monthly speed trends"""
    safe_log("Rendering monthly chart...")
    monthly = _build_monthly_df()
    if monthly is None or monthly.empty:
        safe_log("No successful speed test data yet to plot.")
        messagebox.showinfo("No Data", "Not enough data to plot monthly chart.")
        return

    fig, ax = plt.subplots(figsize=(7,4), dpi=100)
    ax.plot(monthly['month'], monthly['download'], marker='o', label='Download')
    ax.plot(monthly['month'], monthly['upload'], marker='o', label='Upload')
    ax.set_title("Monthly Avg Speeds")
    ax.set_xlabel("Month")
    ax.set_ylabel("Mbps")
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.4)
    plt.xticks(rotation=45)

    for w in chart_frame.winfo_children():
        w.destroy()

    canvas = FigureCanvasTkAgg(fig, master=chart_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)

# ---------------------- PDF Export ----------------------
def export_pdf_report():
    """
    Exports weekly and monthly charts into a single PDF.
    """
    safe_log("Exporting PDF report...")
    weekly = _build_weekly_df()
    monthly = _build_monthly_df()
    if (weekly is None or weekly.empty) and (monthly is None or monthly.empty):
        messagebox.showinfo("No Data", "No data to export.")
        return

    # Ask user for destination
    path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")],
                                        title="Save PDF report as...")
    if not path:
        safe_log("PDF export cancelled.")
        return

    try:
        with PdfPages(path) as pdf:
            if weekly is not None and not weekly.empty:
                fig1, ax1 = plt.subplots(figsize=(8, 5), dpi=100)
                ax1.plot(weekly['week'], weekly['download'], marker='o', label='Download')
                ax1.plot(weekly['week'], weekly['upload'], marker='o', label='Upload')
                ax1.set_title("Weekly Avg Speeds")
                ax1.set_xlabel("Week")
                ax1.set_ylabel("Mbps")
                ax1.legend()
                ax1.grid(True)
                plt.xticks(rotation=45)
                pdf.savefig(fig1)
                plt.close(fig1)

            if monthly is not None and not monthly.empty:
                fig2, ax2 = plt.subplots(figsize=(8, 5), dpi=100)
                ax2.plot(monthly['month'], monthly['download'], marker='o', label='Download')
                ax2.plot(monthly['month'], monthly['upload'], marker='o', label='Upload')
                ax2.set_title("Monthly Avg Speeds")
                ax2.set_xlabel("Month")
                ax2.set_ylabel("Mbps")
                ax2.legend()
                ax2.grid(True)
                plt.xticks(rotation=45)
                pdf.savefig(fig2)
                plt.close(fig2)

        safe_log(f"PDF saved to: {path}")
        messagebox.showinfo("Export Complete", f"PDF report saved to:\n{path}")
    except Exception as e:
        safe_log(f"PDF export failed: {e}")
        messagebox.showerror("Export Error", f"Failed to generate PDF: {e}")

# ---------------------- Scheduler ----------------------
def scheduler_loop():
    """
    Run schedule.run_pending in a background thread.
    Scheduling jobs that need UI updates should dispatch to main thread using window.after.
    """
    while True:
        schedule.run_pending()
        time.sleep(1)

# ---------------------- UI Construction ----------------------
def build_ui():
    """BuIlding application UI"""
    global window, log_box, chart_frame, status_label

    window = tk.Tk()
    window.title("⚡ Internet-Speed Monitor")
    window.geometry("1000x700")
    bg = "#061013"
    panel = "#0a1b12"
    neon = "#39ff14"
    text_color = "#c7f7b6"

    window.configure(bg=bg)

    title = tk.Label(window, text="LIT3|SPEED — Internet Speed Monitor",
                     font=("Fira Sans Condensed", 20, "bold"), bg=bg, fg=neon)
    title.pack(pady=(8,4))

    # Buttons row
    btn_frame = tk.Frame(window, bg=bg)
    btn_frame.pack(pady=6)

    btn_run = tk.Button(btn_frame, text="▶ Run Test Now",
                        command=lambda: safe_call(run_test_threaded),
                        bg=panel, fg=neon, font=("Fira Sans Condensed", 11),
                        bd=0, padx=10, pady=6)
    btn_run.grid(row=0, column=0, padx=6)

    btn_week = tk.Button(btn_frame, text="🗓 Weekly Chart",
                         command=lambda: safe_call(show_weekly_speed_trends),
                         bg=panel, fg=neon, font=("Fira Sans Condensed", 11),
                         bd=0, padx=10, pady=6)
    btn_week.grid(row=0, column=1, padx=6)

    btn_month = tk.Button(btn_frame, text="📈 Monthly Chart",
                          command=lambda: safe_call(show_monthly_speed_trends),
                          bg=panel, fg=neon, font=("Fira Sans Condensed", 11),
                          bd=0, padx=10, pady=6)
    btn_month.grid(row=0, column=2, padx=6)

    btn_pdf = tk.Button(btn_frame, text="🖨 Export PDF",
                        command=lambda: safe_call(export_pdf_report),
                        bg=panel, fg=neon, font=("Fira Sans Condensed", 11),
                        bd=0, padx=10, pady=6)
    btn_pdf.grid(row=0, column=3, padx=6)

    btn_cleanup = tk.Button(btn_frame, text="🧹 Cleanup DB",
                            command=lambda: safe_call(manual_cleanup),
                            bg=panel, fg=neon, font=("Fira Sans Condensed", 11),
                            bd=0, padx=10, pady=6)
    btn_cleanup.grid(row=0, column=4, padx=6)

    # Main area: left = log, right = chart
    main = tk.Frame(window, bg=bg)
    main.pack(fill="both", expand=True, padx=8, pady=8)

    left = tk.Frame(main, bg=panel, width=420)
    left.pack(side="left", fill="both", expand=False, padx=(0,8), pady=8)

    right = tk.Frame(main, bg=panel)
    right.pack(side="right", fill="both", expand=True, padx=(8,0), pady=8)

    # Log area (green terminal style)
    lbl_log = tk.Label(left, text="SYSTEM LOG", bg=panel,
                       fg=neon, font=("Fira Sans Condensed", 12, "bold"))
    lbl_log.pack(anchor="w", pady=(6,0), padx=6)

    log_box_widget = tk.Text(left, bg="#001100", fg=neon, insertbackground=neon,
                             font=("Fira Sans Condensed", 10), wrap="word", bd=0)
    log_box_widget.pack(fill="both", expand=True, padx=6, pady=6)
    log_box_widget.insert(tk.END, "Initializing...\n")

    # small status below log
    status_label_widget = tk.Label(left,
                                   text="Status: idle", bg=panel,
                                   fg=text_color, font=("Fira Sans Condensed", 10))
    status_label_widget.pack(fill="x", padx=6, pady=(0,6))

    # Chart frame on right
    chart_frame_widget = tk.Frame(right, bg="#07120b")
    chart_frame_widget.pack(fill="both", expand=True, padx=6, pady=6)

    # attach globals
    log_box = log_box_widget
    chart_frame = chart_frame_widget
    status_label = status_label_widget

    # footer
    footer = tk.Label(window,
                      text="Press ▶ to run tests. Scheduler runs in background.",
                      bg=bg, fg="#6ef07a",
                      font=("Fira Sans Condensed", 9))
    footer.pack(pady=(0,8))

    return window

# ---------------------- Manual DB cleanup helper ----------------------
def manual_cleanup():
    """Manual Cleanup"""
    safe_log("Manual cleanup requested...")
    deleted = cleanup_old_records(CLEANUP_DAYS)
    safe_log(f"Cleanup complete. Deleted {deleted} old records.")

# ---------------------- Wiring scheduler tasks ----------------------
def schedule_jobs():
    """Sheduling Tasks to run automatically"""
    # Use schedule to trigger tests every SCHEDULE_HOURS hours.
    # Important: jobs that interact with UI must be dispatched to main thread via window.after
    schedule.clear()
    schedule.every(SCHEDULE_HOURS).hours.do(lambda: safe_call(run_test_threaded))
    schedule.every().monday.at("08:00").do(lambda: safe_call(show_weekly_speed_trends))
    # Periodic auto cleanup weekly
    schedule.every().sunday.at("03:00").do(lambda: safe_call(manual_cleanup))

# ---------------------- Program entrypoint ----------------------
def main():
    init_db()
    upgrade_schema()
    win = build_ui()

    # schedule tasks
    schedule_jobs()
    threading.Thread(target=scheduler_loop, daemon=True).start()

    # kick off one initial test at startup (non-blocking)
    safe_log("Launching initial startup test...")
    run_test_threaded()

    win.mainloop()

if __name__ == "__main__":
    main()
