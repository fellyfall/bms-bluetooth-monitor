import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from bms_drivers.base import BatteryReading
from database import BatteryDatabase


class BatteryDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.database = BatteryDatabase(self.root / "measurements.sqlite3")

    @staticmethod
    def reading(
        voltage=13.1,
        cell_voltages=(3.2, 3.2, 3.2, 3.2),
    ):
        return BatteryReading(
            status="ENTLAEDT",
            voltage_v=voltage,
            current_a=-2.0,
            power_w=-26.2,
            soc_percent=50,
            remaining_capacity_ah=50.0,
            nominal_capacity_ah=100.0,
            temperature_c=20.0,
            cell_voltages_v=cell_voltages,
            drift_mv=1,
        )

    def test_records_and_variable_cell_counts_round_trip(self):
        timestamp = datetime(2026, 11, 25, 12, 0)
        self.database.insert_reading(
            self.reading(cell_voltages=(3.2, 3.21, 3.19, 3.2, 3.22, 3.18)),
            "jbd",
            timestamp,
        )

        frame = self.database.read_dataframe("jbd")
        latest = self.database.get_latest("jbd")

        self.assertEqual(len(frame), 1)
        self.assertAlmostEqual(frame.iloc[0]["Zelle6_V"], 3.18)
        self.assertEqual(latest["Status"], "ENTLAEDT")
        self.assertEqual(latest["Zeitstempel"], timestamp)

    def test_legacy_csv_import_is_idempotent_and_preserves_cells(self):
        csv_path = self.root / "battery_log_jbd_2026-11.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(
                [
                    "Zeitstempel", "Status", "Spannung_V", "Strom_A",
                    "Leistung_W", "SOC_Prozent", "Restkapazitaet_Ah",
                    "Temp_C", "Zelle1_V", "Zelle2_V", "Drift_mV",
                ]
            )
            writer.writerow(
                ["2026-11-25 12:00:00", "RUHE", "13.1", "0", "0", "50",
                 "50", "20", "3.2", "3.21", "1"]
            )

        self.assertEqual(self.database.import_csv_files("jbd", [str(csv_path)]), 1)
        self.assertEqual(self.database.import_csv_files("jbd", [str(csv_path)]), 0)
        frame = self.database.read_dataframe("jbd")

        self.assertEqual(len(frame), 1)
        self.assertAlmostEqual(frame.iloc[0]["Zelle2_V"], 3.21)

    def test_sql_downsampling_averages_measurements_and_cells(self):
        self.database.insert_reading(
            self.reading(voltage=13.0, cell_voltages=(3.1, 3.2)),
            "jbd",
            datetime(2026, 11, 25, 12, 0),
        )
        self.database.insert_reading(
            self.reading(voltage=14.0, cell_voltages=(3.3, 3.4)),
            "jbd",
            datetime(2026, 11, 25, 12, 5),
        )

        frame = self.database.read_dataframe("jbd", bucket_seconds=900)

        self.assertEqual(len(frame), 1)
        self.assertEqual(frame.iloc[0]["Zeitstempel"], datetime(2026, 11, 25, 12, 0))
        self.assertAlmostEqual(frame.iloc[0]["Spannung_V"], 13.5)
        self.assertAlmostEqual(frame.iloc[0]["Zelle1_V"], 3.2)

    def test_csv_export_can_be_reimported_and_refuses_overwrite(self):
        self.database.insert_reading(
            self.reading(cell_voltages=(3.2, 3.21, 3.19, 3.2, 3.22)),
            "jbd",
            datetime(2026, 11, 25, 12, 0),
        )
        export_dir = self.root / "csv-export"
        exported = self.database.export_csv_files("jbd", export_dir)
        restored = BatteryDatabase(self.root / "restored.sqlite3")

        self.assertEqual(len(exported), 1)
        self.assertEqual(restored.import_csv_files("jbd", [str(exported[0])]), 1)
        self.assertAlmostEqual(restored.read_dataframe("jbd").iloc[0]["Zelle5_V"], 3.22)
        with self.assertRaises(FileExistsError):
            self.database.export_csv_files("jbd", export_dir)


if __name__ == "__main__":
    unittest.main()
