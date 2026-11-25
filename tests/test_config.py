import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import load_config, load_languages, save_address


class ConfigTests(unittest.TestCase):
    def test_loads_driver_and_interval_from_toml(self):
        config_path = Path(__file__).parents[1] / "config.example.toml"
        with patch.dict(os.environ, {"BMS_DRIVER": "", "BATTERY_ADDRESS": ""}):
            config = load_config(config_path)

        self.assertEqual(config.driver, "ecoworthy")
        self.assertEqual(config.interval_seconds, 60)
        self.assertEqual(config.language, "en")
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

    def test_save_address_creates_config_when_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            save_address("AA:BB:CC:DD:EE:FF", config_path)
            with patch.dict(os.environ, {"BMS_DRIVER": "", "BATTERY_ADDRESS": ""}):
                config = load_config(config_path)

        self.assertEqual(config.address, "AA:BB:CC:DD:EE:FF")

    def test_save_address_preserves_other_config_values_and_comments(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text(
                '[bms]\n# Keep this setting\n'
                'driver = "ecoworthy"\naddress = "" # BMS address\n'
                'language = "de"\n',
                encoding="utf-8",
            )
            save_address("AA:BB:CC:DD:EE:FF", config_path)
            saved_config = config_path.read_text(encoding="utf-8")
            with patch.dict(os.environ, {"BMS_DRIVER": "", "BATTERY_ADDRESS": ""}):
                config = load_config(config_path)

        self.assertIn("# Keep this setting", saved_config)
        self.assertIn("# BMS address", saved_config)
        self.assertEqual(config.address, "AA:BB:CC:DD:EE:FF")
        self.assertEqual(config.language, "de")

    def test_save_address_rejects_empty_address(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            with self.assertRaisesRegex(ValueError, "must not be empty"):
                save_address("  ", config_path)
            self.assertFalse(config_path.exists())

    def test_rejects_non_string_address(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text("[bms]\naddress = 123\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "bms.address must be a string"):
                load_config(config_path)

    def test_loads_supported_dashboard_language(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text('[bms]\nlanguage = "es"\n', encoding="utf-8")
            config = load_config(config_path)

        self.assertEqual(config.language, "es")

    def test_loads_every_registered_dashboard_language(self):
        for language in load_languages():
            with self.subTest(language=language):
                with tempfile.TemporaryDirectory() as temp_dir:
                    config_path = Path(temp_dir) / "config.toml"
                    config_path.write_text(
                        f'[bms]\nlanguage = "{language}"\n', encoding="utf-8"
                    )
                    config = load_config(config_path)

                self.assertEqual(config.language, language)

    def test_rejects_unsupported_dashboard_language(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text('[bms]\nlanguage = "xx"\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "bms.language"):
                load_config(config_path)

    def test_rejects_non_positive_interval(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.toml"
            config_path.write_text("[bms]\ninterval_seconds = 0\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "positive integer"):
                load_config(config_path)


if __name__ == "__main__":
    unittest.main()
