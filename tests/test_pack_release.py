import unittest

from pack_release import should_include


class ReleasePackagingTests(unittest.TestCase):
    def test_excludes_local_and_generated_files(self):
        excluded_paths = (
            "config.toml",
            "nested/config.toml",
            ".env",
            ".env.local",
            "battery_log_2026-11.csv",
            "battery_log_jbd_2026-11.csv",
            "battery_monitor.sqlite3",
            "battery_monitor.sqlite3-wal",
            "battery_monitor.sqlite3-shm",
            "nested/__pycache__/module.pyc",
            ".pytest_cache/v/cache/nodeids",
            "dist/bms-bluetooth-monitor-v0.3.zip",
            "old-release.zip",
        )

        for path in excluded_paths:
            with self.subTest(path=path):
                self.assertFalse(should_include(path))

    def test_includes_example_config_and_source_files(self):
        self.assertTrue(should_include("config.example.toml"))
        self.assertTrue(should_include("bms_drivers/ecoworthy.py"))


if __name__ == "__main__":
    unittest.main()
