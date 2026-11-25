import glob
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.animation import FuncAnimation

LOG_PATTERN = "battery_log*.csv"
UPDATE_INTERVAL_MS = 10000

plt.style.use("dark_background")
fig, axes = plt.subplots(4, 1, figsize=(12, 9), sharex=True)
fig.canvas.manager.set_window_title("ECO-WORTHY 100Ah - Langzeit- & Live-Monitor")

status_banner = fig.suptitle(
    "Lade Log-Daten...", fontsize=11, fontweight="bold", color="#00e5ff"
)

def load_all_logs():
    files = sorted(glob.glob(LOG_PATTERN))
    if not files:
        return pd.DataFrame()
    dfs = []
    for f in files:
        try:
            temp_df = pd.read_csv(f, sep=";")
            if not temp_df.empty:
                dfs.append(temp_df)
        except Exception:
            pass
    if not dfs:
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)
    df["Zeitstempel"] = pd.to_datetime(df["Zeitstempel"], errors="coerce")
    df = df.dropna(subset=["Zeitstempel"]).sort_values("Zeitstempel").drop_duplicates("Zeitstempel")
    return df

def downsample_by_zoom(df, span_days):
    if span_days <= 0.25:
        return df, "1 Min (Original)", "%H:%M:%S"
    elif span_days <= 3:
        rule, label, fmt = "15min", "15 Min (Tagesansicht)", "%d.%m. %H:%M"
    elif span_days <= 21:
        rule, label, fmt = "1h", "1 Std (Wochenansicht)", "%d.%m. %Hh"
    elif span_days <= 120:
        rule, label, fmt = "6h", "6 Std (Monatsansicht)", "%d.%m.%Y"
    else:
        rule, label, fmt = "1D", "1 Tag (Jahresansicht)", "%b %Y"

    df_resampled = (
        df.set_index("Zeitstempel")
        .resample(rule)
        .mean(numeric_only=True)
        .dropna(how="all")
        .reset_index()
    )
    return df_resampled, label, fmt

def update(frame):
    raw_df = load_all_logs()
    if raw_df.empty:
        status_banner.set_text("Warte auf Messdaten in 'battery_log*.csv'...")
        return

    latest = raw_df.iloc[-1]
    first_ts = raw_df["Zeitstempel"].iloc[0]
    last_ts = latest["Zeitstempel"]

    user_zoomed = fig.canvas.toolbar.mode != "" or getattr(update, "has_zoom", False)
    saved_xlim = axes[0].get_xlim() if user_zoomed else None

    if saved_xlim is not None:
        x_start, x_end = saved_xlim
        span_days = max(0.01, x_end - x_start)
        t_min = mdates.num2date(x_start).replace(tzinfo=None)
        t_max = mdates.num2date(x_end).replace(tzinfo=None)
        visible_df = raw_df[(raw_df["Zeitstempel"] >= t_min) & (raw_df["Zeitstempel"] <= t_max)]
        if len(visible_df) < 2:
            visible_df = raw_df
    else:
        span_days = max(0.01, (last_ts - first_ts).total_seconds() / 86400.0)
        visible_df = raw_df

    df, res_label, date_fmt = downsample_by_zoom(visible_df, span_days)

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

    colors = ["#69f0ae", "#40c4ff", "#ea80fc", "#ffab40"]
    for i in range(1, 5):
        col = f"Zelle{i}_V"
        if col in df.columns:
            axes[3].plot(t, df[col], color=colors[i - 1], linewidth=1.5, label=f"Zelle {i}")
    axes[3].set_ylabel("Zellen (V)")
    axes[3].legend(loc="upper left", ncol=4)

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
