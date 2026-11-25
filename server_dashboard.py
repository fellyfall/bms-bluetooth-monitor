import os
import re
import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

from bms_drivers import create_driver
from config import load_config, load_languages
from log_files import find_log_files

app = Flask(__name__)
config = load_config()
create_driver(config.driver)
CELL_COLUMN_PATTERN = re.compile(r"^Zelle(\d+)_V$")

def load_all_logs():
    files = find_log_files(config.driver)
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

def cell_column_number(column):
    match = CELL_COLUMN_PATTERN.fullmatch(column)
    return int(match.group(1)) if match else -1

@app.route("/")
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "index.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), filename)

@app.route("/api/settings")
def api_settings():
    return jsonify({
        "default_language": config.language,
        "languages": load_languages(),
    })

@app.route("/api/data")
def api_data():
    df = load_all_logs()
    if df.empty:
        return jsonify({"empty": True})

    # Aktuellster Echtzeit-Datensatz für die Live-Kacheln
    latest = df.iloc[-1]
    latest_info = {
        "zeit": latest["Zeitstempel"].strftime("%d.%m.%Y %H:%M:%S"),
        "status": str(latest.get("Status", "-")),
        "spannung": float(latest.get("Spannung_V", 0)),
        "strom": float(latest.get("Strom_A", 0)),
        "leistung": float(latest.get("Leistung_W", 0)),
        "soc": float(latest.get("SOC_Prozent", 0)),
        "kapazitaet": float(latest.get("Restkapazitaet_Ah", 0)),
        "temp": float(latest.get("Temp_C", 0)) if pd.notna(latest.get("Temp_C")) else 0,
        "drift": float(latest.get("Drift_mV", 0)) if pd.notna(latest.get("Drift_mV")) else 0,
    }

    # Zeitfilter (falls im Frontend gezoomt oder ein Zeitraum gewählt wurde)
    start_param = request.args.get("start")
    end_param = request.args.get("end")
    if start_param and end_param:
        t_min = pd.to_datetime(start_param, errors="coerce")
        t_max = pd.to_datetime(end_param, errors="coerce")
        if pd.notna(t_min) and pd.notna(t_max):
            sub_df = df[(df["Zeitstempel"] >= t_min) & (df["Zeitstempel"] <= t_max)]
            if len(sub_df) >= 2:
                df = sub_df

    # Dynamisches Downsampling anhand der sichtbaren Zeitspanne
    span_days = max(0.01, (df["Zeitstempel"].max() - df["Zeitstempel"].min()).total_seconds() / 86400.0)

    if span_days <= 0.25:
        rule, res_label = None, "1 Min (Original)"
    elif span_days <= 3:
        rule, res_label = "15min", "15 Min (Tagesansicht)"
    elif span_days <= 21:
        rule, res_label = "1h", "1 Std (Wochenansicht)"
    elif span_days <= 120:
        rule, res_label = "6h", "6 Std (Monatsansicht)"
    else:
        rule, res_label = "1D", "1 Tag (Jahresansicht)"

    if rule:
        df = (
            df.set_index("Zeitstempel")
            .resample(rule)
            .mean(numeric_only=True)
            .dropna(how="all")
            .reset_index()
        )

    # NaN-Werte sauber für JSON ersetzen
    df = df.fillna(0)
    cell_columns = sorted(
        (column for column in df.columns if CELL_COLUMN_PATTERN.fullmatch(column)),
        key=cell_column_number,
    )

    return jsonify({
        "empty": False,
        "latest": latest_info,
        "resolution": res_label,
        "timestamps": df["Zeitstempel"].dt.strftime("%Y-%m-%d %H:%M:%S").tolist(),
        "kapazitaet": df["Restkapazitaet_Ah"].round(2).tolist(),
        "spannung": df["Spannung_V"].round(2).tolist(),
        "leistung": df["Leistung_W"].round(1).tolist(),
        "cells": [
            {
                "name": f"Cell {cell_column_number(column)}",
                "values": df[column].round(3).tolist(),
            }
            for column in cell_columns
        ],
        "z1": df["Zelle1_V"].round(3).tolist() if "Zelle1_V" in df else [],
        "z2": df["Zelle2_V"].round(3).tolist() if "Zelle2_V" in df else [],
        "z3": df["Zelle3_V"].round(3).tolist() if "Zelle3_V" in df else [],
        "z4": df["Zelle4_V"].round(3).tolist() if "Zelle4_V" in df else [],
    })

if __name__ == "__main__":
    print("Web-Dashboard gestartet! Öffne im Browser: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
