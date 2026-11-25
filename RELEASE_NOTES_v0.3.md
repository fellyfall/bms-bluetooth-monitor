# Release v0.3

## Highlights

- Store the BMS Bluetooth address in the local `config.toml` file.
- Keep `BATTERY_ADDRESS` as an environment-variable override.
- Prompt for the address at startup only when it is not configured.
- Keep the local configuration out of Git and release archives.

## Compatibility

Existing ECO-WORTHY monthly CSV logs from v0.1 remain compatible. The only implemented and hardware-tested driver is still ECO-WORTHY with a 100 Ah LiFePO4 battery; this release does not add support for other BMS models.

Python 3.11 or newer is required. See [README.md](README.md) for setup instructions.
