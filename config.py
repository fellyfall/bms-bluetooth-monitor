import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.toml")
LANGUAGE_REGISTRY_PATH = Path(__file__).with_name("locales") / "languages.json"


@dataclass(frozen=True)
class MonitorConfig:
    driver: str
    address: str | None
    interval_seconds: int
    language: str


def load_languages() -> dict[str, dict[str, str]]:
    try:
        languages = json.loads(LANGUAGE_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Unable to load language registry: {error}") from error

    if not isinstance(languages, dict) or not languages:
        raise ValueError("The language registry must contain at least one language.")
    if "en" not in languages:
        raise ValueError("The language registry must include English (en) as a fallback.")
    for code, details in languages.items():
        if (
            not isinstance(code, str)
            or not code
            or not isinstance(details, dict)
            or not isinstance(details.get("name"), str)
            or not details["name"].strip()
            or not isinstance(details.get("locale"), str)
            or not details["locale"].strip()
        ):
            raise ValueError("Each language registry entry needs a code, name, and locale.")
    return languages


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

    languages = load_languages()
    language = bms_config.get("language", "en")
    if not isinstance(language, str) or language not in languages:
        raise ValueError(
            "bms.language must be one of: " + ", ".join(sorted(languages))
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
