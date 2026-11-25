import unittest

from bms_drivers import create_driver
from bms_drivers.ecoworthy import EcoWorthyDriver


class EcoWorthyDriverTests(unittest.TestCase):
    def test_parses_basic_and_variable_cell_data(self):
        basic_data = bytearray(29)
        basic_data[:3] = b"\xdd\x03\x00"
        basic_data[4:6] = (1309).to_bytes(2, "big")
        basic_data[6:8] = (-288).to_bytes(2, "big", signed=True)
        basic_data[8:10] = (6421).to_bytes(2, "big")
        basic_data[10:12] = (10000).to_bytes(2, "big")
        basic_data[23] = 64
        basic_data[26] = 1
        basic_data[27:29] = (2935).to_bytes(2, "big")

        cell_data = bytearray(b"\xdd\x04\x00\x0c")
        for voltage in (3274, 3275, 3274, 3275, 3276, 3273):
            cell_data.extend(voltage.to_bytes(2, "big"))
        cell_data.extend((0, 0x77))

        reading = EcoWorthyDriver.parse_responses(bytes(basic_data), bytes(cell_data))

        self.assertIsNotNone(reading)
        self.assertEqual(reading.voltage_v, 13.09)
        self.assertEqual(reading.current_a, -2.88)
        self.assertEqual(reading.status, "ENTLAEDT")
        self.assertEqual(
            reading.cell_voltages_v,
            (3.274, 3.275, 3.274, 3.275, 3.276, 3.273),
        )
        self.assertEqual(reading.drift_mv, 3)

    def test_invalid_basic_frame_is_skipped(self):
        self.assertIsNone(EcoWorthyDriver.parse_responses(b"bad", b""))

    def test_unknown_driver_has_clear_error(self):
        with self.assertRaisesRegex(ValueError, "Available drivers: ecoworthy"):
            create_driver("unknown")


if __name__ == "__main__":
    unittest.main()
