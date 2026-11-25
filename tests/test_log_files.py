import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bms_drivers.base import BatteryReading
from log_files import find_log_files
from monitor import write_csv_log


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

    def test_csv_schema_includes_all_cell_voltages(self):
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
            old_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                log_path = write_csv_log(reading, "jbd")
                with Path(log_path).open(encoding="utf-8", newline="") as file:
                    headers = next(csv.reader(file, delimiter=";"))
            finally:
                os.chdir(old_cwd)

        self.assertIn("Zelle6_V", headers)


if __name__ == "__main__":
    unittest.main()
