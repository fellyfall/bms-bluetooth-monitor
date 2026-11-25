import glob
from datetime import datetime


def get_monthly_log_filename(driver_name: str) -> str:
    month = datetime.now().strftime("%Y-%m")
    if driver_name == "ecoworthy":
        return f"battery_log_{month}.csv"
    return f"battery_log_{driver_name}_{month}.csv"


def find_log_files(driver_name: str) -> list[str]:
    if driver_name == "ecoworthy":
        patterns = ("battery_log_????-??.csv", "battery_log_ecoworthy_*.csv")
    else:
        patterns = (f"battery_log_{driver_name}_*.csv",)

    return sorted({path for pattern in patterns for path in glob.glob(pattern)})
