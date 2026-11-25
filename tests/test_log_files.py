import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from bms_drivers.base import BatteryReading
from database import BatteryDatabase
from log_files import find_log_files


class LogFileTests(unittest.TestCase):
    def test_driver_log_search_does_not_mix_batteries(self):
        matching_paths = {
            "battery_log_????-??.csv": ["battery_log_2026-11.csv"],
            "battery_log_ecoworthy_*.csv": ["battery_log_ecoworthy_2026-10.csv"],
            "battery_log_jbd_*.csv": ["battery_log_jbd_2026-11.csv"],
        }
        with patch("log_files.glob.glob", side_effect=lambda pattern: matching_paths[pattern]):
            self.assertEqual(
                find_log_files("ecoworthy"),
                ["battery_log_2026-11.csv", "battery_log_ecoworthy_2026-10.csv"],
            )
            self.assertEqual(find_log_files("jbd"), ["battery_log_jbd_2026-11.csv"])

    def test_database_and_csv_export_include_all_cell_voltages(self):
        reading = BatteryReading(
            status="RUHE",
            voltage_v=13.1,
            current_a=0.0,
            power_w=0.0,
            soc_percent=50,
            remaining_capacity_ah=50.0,
            nominal_capacity_ah=100.0,
            temperature_c=20.0,
            cell_voltages_v=(3.2, 3.2, 3.2, 3.2, 3.2, 3.2),
            drift_mv=0,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            database = BatteryDatabase(Path(temp_dir) / "measurements.sqlite3")
            database.insert_reading(
                reading, "jbd", datetime(2026, 11, 25, 12, 0)
            )
            exported = database.export_csv_files("jbd", Path(temp_dir) / "export")
            with exported[0].open(encoding="utf-8", newline="") as file:
                headers = next(csv.reader(file, delimiter=";"))

        self.assertIn("Zelle6_V", headers)


if __name__ == "__main__":
    unittest.main()
