import asyncio
import csv
import os
from datetime import datetime
from bleak import BleakClient, BleakError

from bms_drivers import create_driver
from bms_drivers.base import BatteryReading, BmsDriver
from config import MonitorConfig, load_config
from log_files import get_monthly_log_filename


def write_csv_log(reading: BatteryReading, driver_name: str) -> str:
    log_file = get_monthly_log_filename(driver_name)
    cells = reading.cell_voltages_v
    cell_count = max(len(cells), 4 if driver_name == "ecoworthy" else 0)
    cell_headers = [f"Zelle{index + 1}_V" for index in range(cell_count)]
    cell_values = [*cells, *("" for _ in range(cell_count - len(cells)))]
    fieldnames = [
        "Zeitstempel", "Status", "Spannung_V", "Strom_A", "Leistung_W",
        "SOC_Prozent", "Restkapazitaet_Ah", "Temp_C",
        *cell_headers, "Drift_mV",
    ]
    file_exists = os.path.isfile(log_file)
    if file_exists:
        with open(log_file, mode="r", newline="", encoding="utf-8") as f:
            existing_headers = next(csv.reader(f, delimiter=";"), [])
        if existing_headers != fieldnames:
            raise ValueError(
                f"Log schema in {log_file} does not match this driver's cell count."
            )

    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        reading.status,
        reading.voltage_v,
        reading.current_a,
        reading.power_w,
        reading.soc_percent,
        reading.remaining_capacity_ah,
        "" if reading.temperature_c is None else reading.temperature_c,
        *cell_values,
        "" if reading.drift_mv is None else reading.drift_mv,
    ]
    with open(log_file, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        if not file_exists:
            writer.writerow(fieldnames)
        writer.writerow(row)
    return log_file


def log_reading(reading: BatteryReading, driver_name: str) -> None:
    log_file = write_csv_log(reading, driver_name)
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
        f"-> {log_file}"
    )
    print(
        f"  Netz:   {reading.voltage_v:.2f} V | {reading.current_a:+.2f} A "
        f"({reading.power_w:+.1f} W) | Temp: {temperature}°C{cells_text}"
    )


async def monitor_loop(config: MonitorConfig, driver: BmsDriver) -> None:
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
                        log_reading(reading, config.driver)
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
