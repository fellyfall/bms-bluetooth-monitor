import asyncio

from bleak import BleakClient

from .base import BatteryReading


RX_CHAR_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
TX_CHAR_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

CMD_BASIC_INFO = bytes([0xDD, 0xA5, 0x03, 0x00, 0xFF, 0xFD, 0x77])
CMD_CELL_VOLTAGES = bytes([0xDD, 0xA5, 0x04, 0x00, 0xFF, 0xFC, 0x77])


class EcoWorthyDriver:
    def __init__(self) -> None:
        self._response_buffer = bytearray()

    def _notification_handler(self, sender: object, data: bytearray) -> None:
        self._response_buffer.extend(data)

    async def initialize(self, client: BleakClient) -> None:
        await client.start_notify(RX_CHAR_UUID, self._notification_handler)
        await asyncio.sleep(0.8)

    async def _send_command(self, client: BleakClient, command: bytes) -> bytes:
        self._response_buffer.clear()
        await client.write_gatt_char(TX_CHAR_UUID, command)
        await asyncio.sleep(1.0)
        return bytes(self._response_buffer)

    async def read(self, client: BleakClient) -> BatteryReading | None:
        basic_data = await self._send_command(client, CMD_BASIC_INFO)
        cell_data = await self._send_command(client, CMD_CELL_VOLTAGES)
        return self.parse_responses(basic_data, cell_data)

    @staticmethod
    def parse_responses(
        basic_data: bytes, cell_data: bytes
    ) -> BatteryReading | None:
        if len(basic_data) < 27 or not basic_data.startswith(b"\xdd\x03\x00"):
            print(f"Invalid basic data ({len(basic_data)} bytes); skipping reading.")
            return None

        voltage = int.from_bytes(basic_data[4:6], "big") / 100.0
        current = int.from_bytes(basic_data[6:8], "big", signed=True) / 100.0
        remaining_capacity = int.from_bytes(basic_data[8:10], "big") / 100.0
        nominal_capacity = int.from_bytes(basic_data[10:12], "big") / 100.0
        soc = basic_data[23]

        if current > 0.1:
            status = "LAEDT"
        elif current < -0.1:
            status = "ENTLAEDT"
        else:
            status = "RUHE"

        temperature_count = basic_data[26]
        temperatures = []
        for index in range(temperature_count):
            start = 27 + index * 2
            if len(basic_data) >= start + 2:
                raw_temperature = int.from_bytes(basic_data[start : start + 2], "big")
                temperatures.append(round((raw_temperature - 2731) / 10.0, 1))
        temperature = temperatures[0] if temperatures else None

        cells = []
        if len(cell_data) >= 5 and cell_data.startswith(b"\xdd\x04\x00"):
            declared_bytes = cell_data[3]
            available_cells = max(0, (len(cell_data) - 5) // 2)
            cell_count = min(declared_bytes // 2, available_cells)
            for index in range(cell_count):
                start = 4 + index * 2
                raw_voltage = int.from_bytes(cell_data[start : start + 2], "big")
                cells.append(round(raw_voltage / 1000.0, 3))

        drift = round((max(cells) - min(cells)) * 1000) if cells else None

        return BatteryReading(
            status=status,
            voltage_v=voltage,
            current_a=current,
            power_w=round(voltage * current, 1),
            soc_percent=soc,
            remaining_capacity_ah=remaining_capacity,
            nominal_capacity_ah=nominal_capacity,
            temperature_c=temperature,
            cell_voltages_v=tuple(cells),
            drift_mv=drift,
        )
