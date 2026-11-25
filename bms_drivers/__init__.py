from .base import BmsDriver
from .ecoworthy import EcoWorthyDriver


DRIVERS: dict[str, type[BmsDriver]] = {
    "ecoworthy": EcoWorthyDriver,
}


def create_driver(name: str) -> BmsDriver:
    try:
        driver_type = DRIVERS[name]
    except KeyError as error:
        available = ", ".join(sorted(DRIVERS))
        raise ValueError(
            f"Unknown BMS driver {name!r}. Available drivers: {available}"
        ) from error
    return driver_type()
