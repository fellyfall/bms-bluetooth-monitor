# BMS Bluetooth Monitor

A Bluetooth Low Energy (BLE) logger and dashboard for monitoring LiFePO4 battery management systems (BMS). The project reads battery telemetry, stores it locally as CSV, and presents it in either a web dashboard or a desktop plotting window.

The scripts have only been tested with an ECO-WORTHY 100 Ah LiFePO4 battery and its Bluetooth BMS. Other BMS models may use a different BLE protocol; they have not been tested and may require code changes.

## Live example

The linked dashboard is a feasibility study and an example setup using an ECO-WORTHY 100 Ah LiFePO4 battery, not a production service. View it at [Battery dashboard](http://glockenhof.asuscomm.com:3500/). The link uses HTTP; security, access controls, and availability of this independently hosted system are managed by its owner.

## Features

- Reads pack voltage, current, state of charge, remaining capacity, temperature, and cell voltages over BLE.
- Calculates power and cell-voltage drift.
- Writes timestamped measurements to monthly, driver-specific CSV files.
- Serves a local web dashboard with live status cards, interactive charts, and time-range filters.
- Provides a separate Matplotlib desktop plotter.
- Bundles Plotly.js locally so the web dashboard does not need to download the chart library at runtime.
- Includes Windows and Linux/Raspberry Pi start scripts and example `systemd` units.

## Requirements

- Python 3.11 or newer is required.
- A Bluetooth adapter and a supported BMS in BLE range are required for live measurements.
- The web dashboard can also display existing CSV logs without a connected BMS.

Python packages are listed in [`requirements.txt`](requirements.txt): `bleak`, `flask`, `pandas`, and `matplotlib`.

## BMS drivers

The BLE protocol is isolated in `bms_drivers/`; `monitor.py` and the dashboards consume a common `BatteryReading` format. To select a driver, copy [`config.example.toml`](config.example.toml) to a local `config.toml` and edit it:

```toml
[bms]
driver = "ecoworthy"
interval_seconds = 60
address = "AA:BB:CC:DD:EE:FF"
language = "en"
```

Replace the example address with your BMS Bluetooth address. On Windows, copy the file with `Copy-Item config.example.toml config.toml`; on Linux, use `cp config.example.toml config.toml`. `config.toml` is ignored by Git, so your address is not included in commits or release archives. The start scripts use the configured address and prompt only when it is blank; an address entered at the prompt is saved to `config.toml` for the next start. The `BATTERY_ADDRESS` environment variable, when set, takes precedence over the file and is not saved.

The dashboard supports English (`en`), German (`de`), Spanish (`es`), Russian (`ru`), and Simplified Chinese (`zh-CN`). `bms.language` sets the default language; English is used by default. A visitor's selection is remembered in that browser and does not change the server configuration.

To add a language, copy `locales/en.json` to a new file such as `locales/fr.json` and translate its values without changing the keys or placeholders. Then add the language code, display name, and locale to `locales/languages.json`. The dashboard loads translations from these files; no dashboard logic changes are needed. The test suite checks that every language file contains the same keys as English.

To add another BMS, implement the `BmsDriver` interface in a new module under `bms_drivers/` and register it in `bms_drivers/__init__.py`. Implement `initialize(client)` for BLE setup and `read(client)` to return the shared `BatteryReading` model, including its cell-voltage list. The logger, API, web chart, and desktop plotter handle a variable number of cells. At present, only the ECO-WORTHY driver is implemented and hardware-tested; a new driver still needs protocol details and testing with the target BMS.

## Install and run

Run commands from the project directory.

### Windows

Install Python, then create an environment and install dependencies in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

Run `start.bat`. It uses the address in `config.toml` (or prompts and saves it if none is set), starts the BLE logger and web server, and opens the dashboard at <http://localhost:5000>.

### Linux or Raspberry Pi

Install Python, pip, and Bluetooth support (Debian/Ubuntu/Raspberry Pi OS):

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv bluetooth bluez
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
chmod +x start.sh
./start.sh
```

`start.sh` uses the address in `config.toml` (or prompts and saves it if none is set), starts the logger and dashboard, and opens a browser when a desktop environment is available. The dashboard is at <http://localhost:5000>.

See [`setup_linux.md`](setup_linux.md) for Bluetooth permissions and optional `systemd` autostart instructions. The included service files use `/home/pi/battery-monitor` and the `pi` user by default; adjust them to match your installation. For `systemd`, set `BATTERY_ADDRESS` in `/etc/default/battery-monitor` as described in the setup guide.

## Configuration and individual programs

The logger reads the BMS address from `config.toml` or the `BATTERY_ADDRESS` environment variable. The local configuration file is ignored by Git; keep it private and do not commit it.

To run individual programs:

```text
monitor.py           BLE logger; requires BATTERY_ADDRESS
server_dashboard.py  Flask web server on port 5000
plotter.py           Matplotlib desktop plotter
```

For example, set the address in PowerShell before starting the logger directly:

```powershell
$env:BATTERY_ADDRESS = "AA:BB:CC:DD:EE:FF"
py monitor.py
```

On Linux, use `export BATTERY_ADDRESS="AA:BB:CC:DD:EE:FF"` before running `python3 monitor.py`.

The logger writes CSV files in its current working directory. Start the programs from the project directory so the logger, plotter, and dashboard use the same files.

## Dashboard and API

The Flask server listens on port `5000` and serves the dashboard at `/`. The `/api/data` endpoint returns the latest battery values and chart series. Optional `start` and `end` query parameters filter the time range; the API reduces the data resolution for longer ranges.

By default, the server binds to `0.0.0.0`, making it reachable from other devices on the local network. It has no authentication or TLS. Use it only on a trusted network; do not expose port `5000` directly to the public internet.

Release installations show their version and short Git revision in the dashboard footer. The **Releases** link opens the download page for manual updates; the dashboard does not update itself or modify local configuration and measurement files.

## Creating a release

Pushing a version tag such as `v0.3` from the intended release commit starts the GitHub Actions release workflow. It packages the committed files from that tagged commit and attaches the ZIP archive to a GitHub release with automatically generated release notes. To publish a release, create and push the tag:

```bash
git tag v0.3
git push origin v0.3
```

To build the archive locally for inspection, run `python pack_release.py v0.3` from the repository root. The ZIP is written to `dist/`. Local configuration (`config.toml` and `.env` files), measurement CSVs, logs, Python caches, and existing ZIP archives are excluded. Only files committed in `HEAD` are packaged.

## Data and privacy

Measurement logs contain timestamps and battery telemetry. They are kept locally and excluded from Git by `.gitignore`. Review your logs before sharing them publicly. Configure your own Bluetooth address locally; do not commit it to the repository.

## License

The project is licensed under the [GNU General Public License v3.0](LICENSE). The bundled Plotly.js library retains its own MIT license notice.
