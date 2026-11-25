import asyncio
from datetime import datetime
from bleak import BleakClient, BleakError

from bms_drivers import create_driver
from bms_drivers.base import BatteryReading, BmsDriver
from config import MonitorConfig, load_config
from database import BatteryDatabase


def log_reading(
    reading: BatteryReading, driver_name: str, database: BatteryDatabase
) -> None:
    database.insert_reading(reading, driver_name)
    now_short = datetime.now().strftime("%H:%M:%S")
    cells = " | ".join(
        f"Zelle {index + 1}: {voltage:.3f} V"
        for index, voltage in enumerate(reading.cell_voltages_v)
    )
    drift = "" if reading.drift_mv is None else f" (Drift: {reading.drift_mv} mV)"
    cells_text = f"\n  Zellen: {cells}{drift}" if cells else ""
    temperature = "-" if reading.temperature_c is None else f"{reading.temperature_c:.1f}"

    print(
        f"\n[{now_short}] Status: {reading.status} | {reading.soc_percent}% "
        f"({reading.remaining_capacity_ah:.1f}/{reading.nominal_capacity_ah:.0f} Ah) "
        f"-> {database.path}"
    )
    print(
        f"  Netz:   {reading.voltage_v:.2f} V | {reading.current_a:+.2f} A "
        f"({reading.power_w:+.1f} W) | Temp: {temperature}°C{cells_text}"
    )


async def monitor_loop(config: MonitorConfig, driver: BmsDriver) -> None:
    database = BatteryDatabase()
    imported_rows = database.import_csv_files(config.driver)
    if imported_rows:
        print(f"Imported {imported_rows} legacy CSV measurement(s) into {database.path}.")
    print(
        f"Starting {config.driver} monitor "
        f"(interval: {config.interval_seconds}s; stop with Ctrl+C)..."
    )
    while True:
        try:
            print(f"\nConnecting to {config.address}...")
            async with BleakClient(config.address, timeout=15.0) as client:
                print("Connected. Initializing driver...")
                await driver.initialize(client)

                while client.is_connected:
                    reading = await driver.read(client)
                    if reading is not None:
                        log_reading(reading, config.driver, database)
                    await asyncio.sleep(config.interval_seconds)

        except (BleakError, asyncio.TimeoutError) as e:
            print(f"Connection interrupted ({e}). Retrying in 10 seconds...")
            await asyncio.sleep(10)
        except ValueError:
            raise
        except Exception as e:
            print(f"Unexpected error: {e}. Retrying in 15 seconds...")
            await asyncio.sleep(15)


if __name__ == "__main__":
    config = load_config()
    if not config.address:
        raise SystemExit(
            "Set the BATTERY_ADDRESS environment variable before starting the monitor."
        )
    bms_driver = create_driver(config.driver)
    try:
        asyncio.run(monitor_loop(config, bms_driver))
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
