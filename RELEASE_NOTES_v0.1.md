# Release Notes — Version v0.1

**Release Date:** 25. November 2026  
**Project:** ECO-WORTHY LiFePO4 Bluetooth BMS Monitor & Dashboard

---

## 🚀 Overview / Übersicht

Version **v0.1** marks the initial consolidated release of the **LiFePO4 BLE Battery Monitor & Web Dashboard**. This release brings together a complete end-to-end telemetry system for monitoring 12V LiFePO4 smart batteries (specifically ECO-WORTHY 100Ah with Bluetooth BMS) across both **Windows** and **Linux / Raspberry Pi** environments.

---

## ✨ Features & Components in v0.1

### 1. 📡 BLE Telemetry Logger (`monitor.py`)
- **Bluetooth Low Energy (BLE)** connectivity via `bleak`.
- Queries total voltage, current, power, SOC (%), remaining capacity (Ah), temperature, and individual 4-cell voltages every 60 seconds.
- Automatically calculates cell drift in millivolts ($mV$) and determines operational status (`LAEDT`, `ENTLAEDT`, `RUHE`).
- Log rotation into monthly CSV files (`battery_log_YYYY-MM.csv`) with semicolon delimiters.

### 2. 🌐 Flask Backend & REST API (`server_dashboard.py`)
- Local web server listening on port `5000`.
- Endpoint `/api/data` with **dynamic time-series downsampling** (1-minute resolution up to 1-day averages for annual views).
- Serves static assets directly (including offline `plotly.min.js`).

### 3. 📊 Web Dashboard Frontend (`index.html`)
- Interactive Plotly.js charts displaying SOC, Voltage, Current, Power, and 4-cell voltage curves.
- Live KPI status tiles with automatic 10-second polling.
- Fully offline-capable local JS integration.

### 4. 🖥️ Desktop GUI (`plotter.py`)
- Dark-mode Matplotlib desktop window with 4 synchronized stacked subplots.
- Interactive mouse-wheel zooming and double-click reset.
- Integrated remaining runtime / charge time estimator.

### 5. 🐧 Linux & Raspberry Pi Support
- One-click launcher `start.sh`.
- Native `systemd` unit files (`battery-monitor.service`, `battery-dashboard.service`) for autostarting 24/7 background services upon boot.
- Socket capability instructions (`setcap`) for non-root Bluetooth access.

### 6. 🪟 Windows Support
- One-click launcher `start.bat` for parallel execution of logger and dashboard.

---

## 📂 OS Compatibility Matrix

| File | Type | Windows | Linux / RasPi | Description |
| :--- | :--- | :---: | :---: | :--- |
| `monitor.py` | Python Script | ✅ | ✅ | BLE Data Logger |
| `server_dashboard.py` | Python Script | ✅ | ✅ | Flask Backend & REST API |
| `plotter.py` | Python Script | ✅ | ✅ | Desktop Matplotlib GUI |
| `index.html` | Web Frontend | ✅ | ✅ | Plotly Web Dashboard |
| `start.bat` | Batch Script | ✅ | ❌ | Windows One-Click Starter |
| `start.sh` | Shell Script | ❌ | ✅ | Linux One-Click Starter |
| `battery-monitor.service` | systemd Unit | ❌ | ✅ | 24/7 Logger Autostart Service |
| `battery-dashboard.service` | systemd Unit | ❌ | ✅ | 24/7 Server Autostart Service |
| `requirements.txt` | Python Dependencies | ✅ | ✅ | Required Python packages |
| `LICENSE` | GPL-3.0 | ✅ | ✅ | Project license |
| `info.md` / `setup_linux.md` | Documentation | ✅ | ✅ | Project and setup guides |

---

## 📦 Release archive

The release archive contains the application source, dashboard assets, setup guides, and GPL-3.0 license. Battery measurement logs and device-specific Bluetooth addresses are not included.

---

## 🤝 Open Source & Contributions
- Licensed under the **GNU General Public License v3.0 (GPL-3.0)**.
