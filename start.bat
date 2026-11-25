@echo off
cd /d "%~dp0"
set "ADDRESS_WAS_PROMPTED="
if not defined BATTERY_ADDRESS (
  for /f "delims=" %%A in ('py config.py') do set "BATTERY_ADDRESS=%%A"
)
if not defined BATTERY_ADDRESS (
  set /p "BATTERY_ADDRESS=Bluetooth-MAC-Adresse des BMS: "
  if defined BATTERY_ADDRESS set "ADDRESS_WAS_PROMPTED=1"
)
if defined ADDRESS_WAS_PROMPTED (
  py config.py --save-address "%BATTERY_ADDRESS%"
  if errorlevel 1 (
    echo Fehler: Die Bluetooth-Adresse konnte nicht in config.toml gespeichert werden.
    exit /b 1
  )
  echo Bluetooth-Adresse in config.toml gespeichert.
)
if not defined BATTERY_ADDRESS (
  echo Fehler: Es wurde keine Bluetooth-Adresse eingegeben.
  exit /b 1
)
echo Starte Batterie-Logger und Web-Dashboard...
start "ECO-WORTHY Logger (Nicht schliessen)" cmd /k "py monitor.py"
timeout /t 2 /nobreak >nul
start "ECO-WORTHY Web-Server" cmd /k "py server_dashboard.py"
timeout /t 2 /nobreak >nul
start "" "http://localhost:5000"
