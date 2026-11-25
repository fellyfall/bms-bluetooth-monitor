import asyncio
import csv
import os
from datetime import datetime
from bleak import BleakClient, BleakError

BATTERY_ADDRESS = os.environ.get("BATTERY_ADDRESS")
INTERVAL_SECONDS = 60

RX_CHAR_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
TX_CHAR_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

CMD_BASIC_INFO = bytes([0xDD, 0xA5, 0x03, 0x00, 0xFF, 0xFD, 0x77])
CMD_CELL_VOLTAGES = bytes([0xDD, 0xA5, 0x04, 0x00, 0xFF, 0xFC, 0x77])

response_buffer = bytearray()

def notification_handler(sender, data):
    global response_buffer
    response_buffer.extend(data)

async def send_command(client, cmd):
    global response_buffer
    response_buffer.clear()
    await client.write_gatt_char(TX_CHAR_UUID, cmd)
    await asyncio.sleep(1.0)
    return bytes(response_buffer)

def get_monthly_log_filename():
    return f"battery_log_{datetime.now().strftime('%Y-%m')}.csv"

def write_csv_log(row):
    log_file = get_monthly_log_filename()
    file_exists = os.path.isfile(log_file)
    with open(log_file, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        if not file_exists:
            writer.writerow([
                "Zeitstempel", "Status", "Spannung_V", "Strom_A", "Leistung_W",
                "SOC_Prozent", "Restkapazitaet_Ah", "Temp_C",
                "Zelle1_V", "Zelle2_V", "Zelle3_V", "Zelle4_V", "Drift_mV"
            ])
        writer.writerow(row)

def parse_and_log(basic_data, cell_data):
    now_full = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    now_short = datetime.now().strftime("%H:%M:%S")

    if len(basic_data) < 27 or not basic_data.startswith(b'\xdd\x03\x00'):
        print(f"[{now_short}] Ungültige Basisdaten ({len(basic_data)} Bytes), überspringe...")
        return

    voltage = int.from_bytes(basic_data[4:6], "big", signed=False) / 100.0
    current = int.from_bytes(basic_data[6:8], "big", signed=True) / 100.0
    power = round(voltage * current, 1)
    rem_cap = int.from_bytes(basic_data[8:10], "big", signed=False) / 100.0
    nom_cap = int.from_bytes(basic_data[10:12], "big", signed=False) / 100.0
    soc = basic_data[23]

    if current > 0.1:
        state = "LAEDT"
    elif current < -0.1:
        state = "ENTLAEDT"
    else:
        state = "RUHE"

    ntc_count = basic_data[26]
    temps = []
    for i in range(ntc_count):
        start = 27 + i * 2
        if len(basic_data) >= start + 2:
            raw_temp = int.from_bytes(basic_data[start:start + 2], "big", signed=False)
            temps.append(round((raw_temp - 2731) / 10.0, 1))
    main_temp = temps.pop(0) if temps else ""

    z1 = z2 = z3 = z4 = ""
    drift_mv = ""
    cells_str = ""
    if len(cell_data) >= 13 and cell_data.startswith(b'\xdd\x04\x00'):
        num_cells = min(cell_data[3] // 2, 4)
        parsed_cells = []
        for i in range(num_cells):
            start = 4 + i * 2
            raw_c = int.from_bytes(cell_data[start:start + 2], "big", signed=False)
            parsed_cells.append(round(raw_c / 1000.0, 3))

        if len(parsed_cells) >= 4:
            z1, z2, z3, z4 = parsed_cells[:4]
        drift_mv = round((max(parsed_cells) - min(parsed_cells)) * 1000)
        cells_formatted = " | ".join([f"Z{i+1}: {v:.3f}V" for i, v in enumerate(parsed_cells)])
        cells_str = f"\n  Zellen: {cells_formatted} (Drift: {drift_mv} mV)"

    write_csv_log([
        now_full, state, voltage, current, power,
        soc, rem_cap, main_temp,
        z1, z2, z3, z4, drift_mv
    ])

    print(f"\n[{now_short}] Status: {state} | {soc}% ({rem_cap:.1f}/{nom_cap:.0f} Ah) -> {get_monthly_log_filename()}")
    print(f"  Netz:   {voltage:.2f} V | {current:+.2f} A ({power:+.1f} W) | Temp: {main_temp}°C{cells_str}")

async def monitor_loop():
    print(f"Starte Langzeit-Überwachung (Intervall: {INTERVAL_SECONDS}s, Beenden mit Strg+C)...")
    while True:
        try:
            print(f"\nVerbinde mit {BATTERY_ADDRESS}...")
            async with BleakClient(BATTERY_ADDRESS, timeout=15.0) as client:
                print("Verbunden! Initialisiere Datenabruf...")
                await client.start_notify(RX_CHAR_UUID, notification_handler)
                await asyncio.sleep(0.8)

                while client.is_connected:
                    basic_data = await send_command(client, CMD_BASIC_INFO)
                    cell_data = await send_command(client, CMD_CELL_VOLTAGES)
                    parse_and_log(basic_data, cell_data)
                    await asyncio.sleep(INTERVAL_SECONDS)

        except (BleakError, asyncio.TimeoutError) as e:
            print(f"Verbindung unterbrochen ({e}). Neuer Versuch in 10 Sekunden...")
            await asyncio.sleep(10)
        except Exception as e:
            print(f"Unerwarteter Fehler: {e}. Warte 15 Sekunden...")
            await asyncio.sleep(15)

if __name__ == "__main__":
    if not BATTERY_ADDRESS:
        raise SystemExit(
            "Set the BATTERY_ADDRESS environment variable to your BMS Bluetooth address."
        )
    try:
        asyncio.run(monitor_loop())
    except KeyboardInterrupt:
        print("\nÜberwachung & Logging sauber beendet.")
