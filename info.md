# LiFePO4 BMS Monitoring & Dashboard System (Revision v0.1)

Vollständiges Open-Source-System zur 24/7-Überwachung und Visualisierung von Smart-Batterien / BMS (z. B. ECO-WORTHY 100Ah LiFePO4 Akkus mit Bluetooth BLE).

---

## 🖥️ Betriebssystem-Matrix (OS Compatibility)

| Datei / Komponente | Typ | Windows | Linux / RasPi | Beschreibung |
| :--- | :--- | :---: | :---: | :--- |
| `monitor.py` | Python 3 | ✅ | ✅ | BLE-Logger zur Datenabfrage alle 60s & CSV-Speicherung |
| `server_dashboard.py` | Flask Webserver | ✅ | ✅ | Backend mit Downsampling-API (`/api/data`) |
| `plotter.py` | Matplotlib GUI | ✅ | ✅ | Desktop-GUI mit 4 gestapelten Live-Graphen & Zoom |
| `index.html` | HTML5 / Plotly | ✅ | ✅ | Web-Frontend mit Live-KPI-Kacheln |
| `plotly.min.js` | JS-Bibliothek | ✅ | ✅ | Lokale Plotly.js für 100% Offline-Betrieb |
| `requirements.txt` | Python-Deps | ✅ | ✅ | Paketliste für pip (`bleak`, `flask`, `pandas`, `matplotlib`) |
| `start.bat` | Windows Batch | ✅ | ❌ | Ein-Klick Starter für Windows (CMD) |
| `start.sh` | Shell Skript | ❌ | ✅ | Ein-Klick Starter für Linux / macOS Terminal |
| `battery-monitor.service` | systemd Unit | ❌ | ✅ | Autostart-Dienst für 24/7-Logger auf Raspberry Pi |
| `battery-dashboard.service`| systemd Unit | ❌ | ✅ | Autostart-Dienst für 24/7-Webserver auf Raspberry Pi |

---

## ⚙️ Schnellstart

Der Logger benötigt die Bluetooth-MAC-Adresse des BMS. `start.bat` und `start.sh` fragen sie beim Start ab; sie wird nicht im Quellcode gespeichert.

### 🪟 Windows:
1. `pip install -r requirements.txt`
2. Doppelklick auf **`start.bat`**

### 🐧 Linux / Raspberry Pi:
1. `pip install -r requirements.txt`
2. `chmod +x start.sh && ./start.sh`
3. 24/7 Autostart via systemd:
   ```bash
   sudo cp *.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now battery-monitor.service battery-dashboard.service
   ```
