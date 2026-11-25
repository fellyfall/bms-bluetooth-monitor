# Release v0.2

**Release date:** 2026-11-25

## Highlights

- Extracted the BLE protocol into a driver interface under `bms_drivers/`.
- Added local TOML configuration for driver selection and polling interval.
- Added per-driver CSV logging (preserving existing ECO-WORTHY log paths) and variable cell-count support in the API, web dashboard, and desktop plotter.
- Kept the ECO-WORTHY driver as the only implemented and hardware-tested driver.
- Added tests for configuration, protocol parsing, CSV logging, and the dashboard API.

## Compatibility

The scripts have only been tested with an ECO-WORTHY 100 Ah LiFePO4 battery and its Bluetooth BMS. This release adds the structure for future drivers; it does not add support for other BMS models.

Python 3.11 or newer is required. See [README.md](README.md) for setup and usage instructions.

## Privacy and license

The release archive does not include local configuration, battery measurement logs, or device-specific Bluetooth addresses. The project is licensed under GPL-3.0; the bundled Plotly.js library retains its MIT license notice.
