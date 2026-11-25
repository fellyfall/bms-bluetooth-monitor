import re
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.animation import FuncAnimation

from bms_drivers import create_driver
from config import load_config
from database import BatteryDatabase, resolution_for_span

config = load_config()
create_driver(config.driver)
database = BatteryDatabase()
imported_rows = database.import_csv_files(config.driver)
if imported_rows:
    print(f"Imported {imported_rows} legacy CSV measurement(s) into {database.path}.")
UPDATE_INTERVAL_MS = 10000
CELL_COLUMN_PATTERN = re.compile(r"^Zelle(\d+)_V$")

plt.style.use("dark_background")
fig, axes = plt.subplots(4, 1, figsize=(12, 9), sharex=True)
fig.canvas.manager.set_window_title(f"{config.driver} BMS - Live Monitor")

status_banner = fig.suptitle(
    "Lade Log-Daten...", fontsize=11, fontweight="bold", color="#00e5ff"
)

def date_format_for_span(span_days):
    if span_days <= 0.25:
        return "%H:%M:%S"
    if span_days <= 3:
        return "%d.%m. %H:%M"
    if span_days <= 21:
        return "%d.%m. %Hh"
    if span_days <= 120:
        return "%d.%m.%Y"
    return "%b %Y"

def update(frame):
    latest = database.get_latest(config.driver)
    first_ts, last_ts = database.get_bounds(config.driver)
    if latest is None or first_ts is None or last_ts is None:
        status_banner.set_text("Warte auf Messdaten in 'battery_monitor.sqlite3'...")
        return

    last_ts = latest["Zeitstempel"].to_pydatetime()

    user_zoomed = fig.canvas.toolbar.mode != "" or getattr(update, "has_zoom", False)
    saved_xlim = axes[0].get_xlim() if user_zoomed else None

    if saved_xlim is not None:
        x_start, x_end = saved_xlim
        span_days = max(0.01, x_end - x_start)
        t_min = mdates.num2date(x_start).replace(tzinfo=None)
        t_max = mdates.num2date(x_end).replace(tzinfo=None)
        if database.count_readings(config.driver, t_min, t_max) >= 2:
            bucket_seconds, res_label = resolution_for_span(span_days)
            df = database.read_dataframe(
                config.driver, t_min, t_max, bucket_seconds=bucket_seconds
            )
        else:
            span_days = max(0.01, (last_ts - first_ts).total_seconds() / 86400.0)
            bucket_seconds, res_label = resolution_for_span(span_days)
            df = database.read_dataframe(
                config.driver, bucket_seconds=bucket_seconds
            )
    else:
        span_days = max(0.01, (last_ts - first_ts).total_seconds() / 86400.0)
        bucket_seconds, res_label = resolution_for_span(span_days)
        df = database.read_dataframe(config.driver, bucket_seconds=bucket_seconds)
    if df.empty:
        return
    date_fmt = date_format_for_span(span_days)

    for ax in axes:
        ax.clear()
        ax.grid(True, linestyle="--", alpha=0.25)

    t = df["Zeitstempel"]

    axes[0].plot(t, df["Restkapazitaet_Ah"], color="#00e5ff", linewidth=2, label="Restkapazität (Ah)")
    axes[0].set_ylabel("Kapazität (Ah)", color="#00e5ff")
    axes[0].legend(loc="upper left")

    axes[1].plot(t, df["Spannung_V"], color="#ffd54f", linewidth=2, label="Gesamtspannung (V)")
    axes[1].set_ylabel("Spannung (V)", color="#ffd54f")
    axes[1].legend(loc="upper left")

    axes[2].plot(t, df["Leistung_W"], color="#ff5252", linewidth=2, label="Leistung (W)")
    axes[2].axhline(0, color="white", linewidth=0.8, alpha=0.4)
    axes[2].set_ylabel("Leistung (W)", color="#ff5252")
    axes[2].legend(loc="upper left")

    colors = ["#69f0ae", "#40c4ff", "#ea80fc", "#ffab40", "#00e5ff", "#ffd54f"]
    cell_columns = sorted(
        (col for col in df.columns if CELL_COLUMN_PATTERN.fullmatch(col)),
        key=lambda col: int(CELL_COLUMN_PATTERN.fullmatch(col).group(1)),
    )
    for i, col in enumerate(cell_columns):
        axes[3].plot(t, df[col], color=colors[i % len(colors)], linewidth=1.5, label=f"Cell {i + 1}")
    axes[3].set_ylabel("Zellen (V)")
    if cell_columns:
        axes[3].legend(loc="upper left", ncol=min(4, len(cell_columns)))

    axes[3].xaxis.set_major_formatter(mdates.DateFormatter(date_fmt))
    fig.autofmt_xdate()

    power = latest["Leistung_W"]
    rem_ah = latest["Restkapazitaet_Ah"]
    soc = latest["SOC_Prozent"]
    volt = latest["Spannung_V"]
    curr = latest["Strom_A"]
    drift = latest.get("Drift_mV", 0)
    temp = latest.get("Temp_C", "-")

    if curr < -0.1:
        eta_str = f"Rest: ~{rem_ah / abs(curr):.1f} h"
    elif curr > 0.1:
        eta_str = f"Voll in: ~{max(0, 100.0 - rem_ah) / curr:.1f} h"
    else:
        eta_str = "Ruhe"

    status_banner.set_text(
        f"LIVE ({last_ts.strftime('%d.%m. %H:%M')}) | {latest['Status']} | "
        f"{soc:.0f}% ({rem_ah:.2f} Ah) | {volt:.2f}V / {curr:+.2f}A ({power:+.1f}W) | "
        f"Drift: {drift:.0f}mV | {temp}°C | {eta_str}  ||  Zoom-Raster: {res_label}"
    )

    if saved_xlim is not None:
        axes[0].set_xlim(saved_xlim)

    plt.tight_layout(rect=[0, 0, 1, 0.95])

def on_scroll(event):
    if event.inaxes not in axes:
        return
    update.has_zoom = True
    x_start, x_end = axes[0].get_xlim()
    scale = 0.75 if event.button == "up" else 1.35
    xdata = event.xdata
    axes[0].set_xlim([xdata - (xdata - x_start) * scale, xdata + (x_end - xdata) * scale])
    update(0)
    fig.canvas.draw_idle()

def on_double_click(event):
    if event.dblclick:
        update.has_zoom = False
        update(0)
        fig.canvas.draw_idle()

fig.canvas.mpl_connect("scroll_event", on_scroll)
fig.canvas.mpl_connect("button_press_event", on_double_click)

ani = FuncAnimation(fig, update, interval=UPDATE_INTERVAL_MS, cache_frame_data=False)
update(0)
plt.show()
