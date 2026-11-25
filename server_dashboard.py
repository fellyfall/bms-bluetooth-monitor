import json
import os
import re
from threading import Lock
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

from bms_drivers import create_driver
from config import load_config, load_languages
from database import BatteryDatabase, DATABASE_FILENAME, resolution_for_span
from log_files import find_log_files

app = Flask(__name__)
config = load_config()
create_driver(config.driver)
VERSION_INFO_PATH = Path(__file__).with_name("version.json")
CELL_COLUMN_PATTERN = re.compile(r"^Zelle(\d+)_V$")


def load_version_info():
    if not VERSION_INFO_PATH.exists():
        return {"version": "development", "revision": "unpackaged"}
    try:
        version_info = json.loads(VERSION_INFO_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Unable to load version metadata: {error}") from error
    if (
        not isinstance(version_info, dict)
        or not isinstance(version_info.get("version"), str)
        or not version_info["version"].strip()
        or not isinstance(version_info.get("revision"), str)
        or not version_info["revision"].strip()
    ):
        raise ValueError("version.json must contain version and revision strings.")
    return version_info


VERSION_INFO = load_version_info()
DATABASES = {}
DATABASES_LOCK = Lock()


def get_database():
    path = (Path.cwd() / DATABASE_FILENAME).resolve()
    with DATABASES_LOCK:
        if path not in DATABASES:
            DATABASES[path] = BatteryDatabase(path)
        return DATABASES[path]

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
        "version": VERSION_INFO,
    })

@app.route("/api/data")
def api_data():
    database = get_database()
    database.import_csv_files(config.driver, find_log_files(config.driver))
    first_ts, last_ts = database.get_bounds(config.driver)
    if first_ts is None or last_ts is None:
        return jsonify({"empty": True})

    latest = database.get_latest(config.driver)
    latest_timestamp = pd.to_datetime(latest["Zeitstempel"])
    latest_info = {
        "zeit": latest_timestamp.strftime("%d.%m.%Y %H:%M:%S"),
        "status": str(latest.get("Status", "-")),
        "spannung": float(latest.get("Spannung_V", 0)),
        "strom": float(latest.get("Strom_A", 0)),
        "leistung": float(latest.get("Leistung_W", 0)),
        "soc": float(latest.get("SOC_Prozent", 0)),
        "kapazitaet": float(latest.get("Restkapazitaet_Ah", 0)),
        "temp": float(latest["Temp_C"]) if pd.notna(latest.get("Temp_C")) else 0,
        "drift": float(latest["Drift_mV"]) if pd.notna(latest.get("Drift_mV")) else 0,
    }

    start_param = request.args.get("start")
    end_param = request.args.get("end")
    query_start = first_ts
    query_end = last_ts
    if start_param and end_param:
        t_min = pd.to_datetime(start_param, errors="coerce")
        t_max = pd.to_datetime(end_param, errors="coerce")
        if pd.notna(t_min) and t_min.tzinfo is not None:
            t_min = t_min.tz_convert(None)
        if pd.notna(t_max) and t_max.tzinfo is not None:
            t_max = t_max.tz_convert(None)
        if pd.notna(t_min) and pd.notna(t_max):
            if t_max >= t_min and database.count_readings(config.driver, t_min, t_max) >= 2:
                query_start, query_end = t_min, t_max

    span_days = max(0.01, (query_end - query_start).total_seconds() / 86400.0)
    bucket_seconds, res_label = resolution_for_span(span_days)
    df = database.read_dataframe(
        config.driver,
        start=query_start,
        end=query_end,
        bucket_seconds=bucket_seconds,
    )
    if df.empty:
        return jsonify({"empty": True})

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
