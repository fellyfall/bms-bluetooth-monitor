import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import load_config


class ConfigTests(unittest.TestCase):
    def test_loads_driver_and_interval_from_toml(self):
        config_path = Path(__file__).parents[1] / "config.example.toml"
        with patch.dict(os.environ, {"BMS_DRIVER": "", "BATTERY_ADDRESS": ""}):
            config = load_config(config_path)

        self.assertEqual(config.driver, "ecoworthy")
        self.assertEqual(config.interval_seconds, 60)
        self.assertIsNone(config.address)

    def test_environment_address_overrides_local_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(
                '[bms]\naddress = "11:22:33:44:55:66"\n', encoding="utf-8"
            )
            with patch.dict(
                os.environ,
                {"BMS_DRIVER": "ecoworthy", "BATTERY_ADDRESS": "AA:BB:CC:DD:EE:FF"},
            ):
                config = load_config(config_path)

        self.assertEqual(config.address, "AA:BB:CC:DD:EE:FF")

    def test_loads_local_address_from_toml(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(
                '[bms]\naddress = " 11:22:33:44:55:66 "\n', encoding="utf-8"
            )
            with patch.dict(os.environ, {"BATTERY_ADDRESS": ""}):
                config = load_config(config_path)

        self.assertEqual(config.address, "11:22:33:44:55:66")

    def test_rejects_non_string_address(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text("[bms]\naddress = 123\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "bms.address must be a string"):
                load_config(config_path)

    def test_rejects_non_positive_interval(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text("[bms]\ninterval_seconds = 0\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "positive integer"):
                load_config(config_path)


if __name__ == "__main__":
    unittest.main()
