# Linux & Raspberry Pi Setup-Anleitung für das Batterie-Monitoring

Dieses Dokument beschreibt die Einrichtung des BLE-Batterie-Loggers (`monitor.py`) und des Web-Dashboards (`server_dashboard.py`) auf einem Linux-System (z. B. Raspberry Pi OS, Debian, Ubuntu).

---

## 1. Voraussetzungen & Pakete installieren

Installiere Python 3, Pip und Bluetooth-Tools:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv bluetooth bluez
```

Installiere die benötigten Python-Bibliotheken:

```bash
python3 -m pip install -r requirements.txt
```

---

## 2. Bluetooth-Berechtigungen (ohne sudo)

Damit `bleak` ohne `sudo` auf den Bluetooth-Adapter zugreifen kann, vergebe die entsprechenden Capabilities an den Python-Interpreter und füge deinen Benutzer zur `bluetooth`-Gruppe hinzu:

```bash
# Python-Interpreter berechtigen
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python3))

# Benutzer zur Gruppe 'bluetooth' hinzufügen
sudo usermod -aG bluetooth $USER
```

*Hinweis:* Melde dich danach einmal ab und wieder an (oder starte den Pi neu), damit die Gruppenänderung aktiv wird.

---

## 3. Manuelles Starten per `start.sh`

Mache das Start-Skript ausführbar:

```bash
chmod +x start.sh
./start.sh
```

Beim Start fragt das Skript nach der Bluetooth-MAC-Adresse des BMS. Alternativ kannst du sie vorher setzen:

```bash
export BATTERY_ADDRESS="AA:BB:CC:DD:EE:FF"
./start.sh
```

---

## 4. 24/7 Autostart einrichten (`systemd`)

Wenn der Logger und das Dashboard automatisch beim Systemstart laufen sollen:

1. **Dateien kopieren**:
   ```bash
   sudo cp battery-monitor.service /etc/systemd/system/
   sudo cp battery-dashboard.service /etc/systemd/system/
   ```

   *(Falls dein Projektpfad oder Benutzer abweicht, passe `User` und `WorkingDirectory` in den `.service`-Dateien an.)*

2. **Bluetooth-Adresse konfigurieren**:
   ```bash
   echo 'BATTERY_ADDRESS=AA:BB:CC:DD:EE:FF' | sudo tee /etc/default/battery-monitor
   sudo chmod 600 /etc/default/battery-monitor
   ```

3. **Dienste aktivieren und starten**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now battery-monitor.service
   sudo systemctl enable --now battery-dashboard.service
   ```

4. **Status & Logs prüfen**:
   ```bash
   sudo systemctl status battery-monitor.service
   sudo systemctl status battery-dashboard.service
   
   # Live-Logs ansehen:
   journalctl -u battery-monitor.service -f
   ```

---

## 5. Zugriff im Netzwerk

Das Web-Dashboard ist nach dem Start unter `http://<IP-des-Raspberry-Pi>:5000` im gesamten lokalen Netzwerk erreichbar.
