import csv
import os
import tempfile
import unittest
from pathlib import Path

from config import load_languages
from server_dashboard import VERSION_INFO, app, config


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


if __name__ == "__main__":
    unittest.main()
