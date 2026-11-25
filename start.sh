#!/bin/bash
# Autostart-Skript fuer Batterie-Logger & Web-Dashboard unter Linux

# In das Verzeichnis des Skripts wechseln
cd "$(dirname "$0")"

if [ -z "${BATTERY_ADDRESS:-}" ]; then
    read -r -p "Bluetooth-MAC-Adresse des BMS: " BATTERY_ADDRESS
    export BATTERY_ADDRESS
fi
if [ -z "${BATTERY_ADDRESS:-}" ]; then
    echo "Fehler: Es wurde keine Bluetooth-Adresse eingegeben." >&2
    exit 1
fi

echo "=== Starte Batterie-Monitoring (Linux) ==="

# 1. BLE-Logger im Hintergrund starten
echo "Starte monitor.py..."
python3 monitor.py > monitor.log 2>&1 &
MONITOR_PID=$!
echo "monitor.py gestartet (PID: $MONITOR_PID)"

# 2. Flask Dashboard im Hintergrund starten
echo "Starte server_dashboard.py..."
python3 server_dashboard.py > server.log 2>&1 &
SERVER_PID=$!
echo "server_dashboard.py gestartet (PID: $SERVER_PID)"

# Kurze Pause fuer den Serverstart
sleep 2

# 3. Web-Dashboard im Browser oeffnen (falls GUI/Browser vorhanden)
URL="http://localhost:5000"
if command -v xdg-open > /dev/null 2>&1; then
    xdg-open "$URL" > /dev/null 2>&1 &
elif command -v open > /dev/null 2>&1; then
    open "$URL" > /dev/null 2>&1 &
else
    echo "Dashboard erreichbar unter: $URL"
fi

echo "Beide Dienste laufen im Hintergrund."
echo "Logs einsehen mit: tail -f monitor.log"
