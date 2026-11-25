import csv
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from bms_drivers.base import BatteryReading
from config import load_languages
from server_dashboard import VERSION_INFO, app, config, get_database


class DashboardApiTests(unittest.TestCase):
    def test_settings_api_returns_configured_default_language(self):
        response = app.test_client().get("/api/settings")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "default_language": config.language,
                "languages": load_languages(),
                "version": VERSION_INFO,
            },
        )
        self.assertIn("en", response.get_json()["languages"])

    def test_locale_translation_file_is_served(self):
        response = app.test_client().get("/locales/de.json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "Status")
        response.close()

    def test_api_returns_a_series_for_each_cell_column(self):
        headers = [
            "Zeitstempel", "Status", "Spannung_V", "Strom_A", "Leistung_W",
            "SOC_Prozent", "Restkapazitaet_Ah", "Temp_C",
            *(f"Zelle{index}_V" for index in range(1, 7)),
            "Drift_mV",
        ]
        row = [
            "2026-11-25 12:00:00", "RUHE", 13.1, 0, 0, 50, 50, 20,
            3.2, 3.2, 3.2, 3.2, 3.2, 3.2, 0,
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "battery_log_2026-11.csv"
            with log_path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file, delimiter=";")
                writer.writerow(headers)
                writer.writerow(row)

            old_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                response = app.test_client().get("/api/data")
            finally:
                os.chdir(old_cwd)

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["cells"]), 6)
        self.assertEqual(payload["cells"][5]["name"], "Cell 6")
        self.assertEqual(payload["cells"][5]["values"], [3.2])

    def test_api_filters_chart_range_but_keeps_latest_live_reading(self):
        reading = BatteryReading(
            status="ENTLAEDT",
            voltage_v=13.1,
            current_a=-1.0,
            power_w=-13.1,
            soc_percent=50,
            remaining_capacity_ah=50.0,
            nominal_capacity_ah=100.0,
            temperature_c=20.0,
            cell_voltages_v=(3.2, 3.2, 3.2, 3.2),
            drift_mv=1,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            old_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                database = get_database()
                database.insert_reading(
                    reading, config.driver, datetime(2026, 11, 25, 10, 0)
                )
                database.insert_reading(
                    reading, config.driver, datetime(2026, 11, 25, 10, 10)
                )
                database.insert_reading(
                    reading, config.driver, datetime(2026, 11, 25, 11, 0)
                )
                response = app.test_client().get(
                    "/api/data?start=2026-11-25T10:00:00"
                    "&end=2026-11-25T10:10:00"
                )
            finally:
                os.chdir(old_cwd)

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            payload["timestamps"],
            ["2026-11-25 10:00:00", "2026-11-25 10:10:00"],
        )
        self.assertEqual(payload["latest"]["zeit"], "25.11.2026 11:00:00")


if __name__ == "__main__":
    unittest.main()
