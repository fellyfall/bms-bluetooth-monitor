import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.toml")
SUPPORTED_LANGUAGES = {"en", "de", "es", "ru", "zh-CN"}


@dataclass(frozen=True)
class MonitorConfig:
    driver: str
    address: str | None
    interval_seconds: int
    language: str


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> MonitorConfig:
    if path.exists():
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as error:
            raise ValueError(f"Invalid TOML configuration in {path}: {error}") from error
    else:
        data = {}

    bms_config = data.get("bms", {})
    if not isinstance(bms_config, dict):
        raise ValueError("The [bms] section in config.toml must be a table.")

    driver = os.environ.get("BMS_DRIVER") or bms_config.get("driver", "ecoworthy")
    if not isinstance(driver, str) or not driver.strip():
        raise ValueError("The BMS driver name must be a non-empty string.")

    interval_seconds = bms_config.get("interval_seconds", 60)
    if (
        isinstance(interval_seconds, bool)
        or not isinstance(interval_seconds, int)
        or interval_seconds <= 0
    ):
        raise ValueError("bms.interval_seconds must be a positive integer.")

    language = bms_config.get("language", "en")
    if not isinstance(language, str) or language not in SUPPORTED_LANGUAGES:
        raise ValueError(
            "bms.language must be one of: " + ", ".join(sorted(SUPPORTED_LANGUAGES))
        )

    address = os.environ.get("BATTERY_ADDRESS") or bms_config.get("address")
    if address is not None and not isinstance(address, str):
        raise ValueError("bms.address must be a string.")
    address = address.strip() if address and address.strip() else None

    return MonitorConfig(
        driver=driver.strip().lower(),
        address=address,
        interval_seconds=interval_seconds,
        language=language,
    )


if __name__ == "__main__":
    print(load_config().address or "")
