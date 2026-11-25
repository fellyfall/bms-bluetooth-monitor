from dataclasses import dataclass
from typing import Protocol

from bleak import BleakClient


@dataclass(frozen=True)
class BatteryReading:
    status: str
    voltage_v: float
    current_a: float
    power_w: float
    soc_percent: int
    remaining_capacity_ah: float
    nominal_capacity_ah: float
    temperature_c: float | None
    cell_voltages_v: tuple[float, ...]
    drift_mv: int | None


class BmsDriver(Protocol):
    async def initialize(self, client: BleakClient) -> None:
        ...

    async def read(self, client: BleakClient) -> BatteryReading | None:
        ...
