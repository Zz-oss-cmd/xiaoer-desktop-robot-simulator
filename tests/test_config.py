import json
import unittest
from unittest.mock import patch

from robot_sim.config import VirtualDeviceConfig


class VirtualDeviceConfigTests(unittest.TestCase):
    def test_defaults_match_virtual_device_defaults(self) -> None:
        config = VirtualDeviceConfig()

        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 8765)
        self.assertEqual(config.max_queue_size, 128)

    def test_partial_mapping_uses_defaults(self) -> None:
        config = VirtualDeviceConfig.from_mapping({"port": 9000})

        self.assertEqual(config.port, 9000)
        self.assertEqual(config.link_timeout_ms, 3_000)

    def test_example_file_is_valid(self) -> None:
        config = VirtualDeviceConfig.load("config.example.json")

        self.assertEqual(config.port, 8765)
        self.assertEqual(config.max_connections, 8)

    def test_unknown_field_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown configuration fields"):
            VirtualDeviceConfig.from_mapping({"retry_forever": True})

    def test_invalid_values_are_rejected(self) -> None:
        invalid = [
            {"host": ""},
            {"port": 65_536},
            {"link_timeout_ms": 0},
            {"receive_size": True},
            {"poll_interval_s": float("nan")},
            {"max_connections": 0},
            {"max_queue_size": -1},
        ]
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(ValueError):
                VirtualDeviceConfig.from_mapping(values)

    def test_load_reads_utf8_json_object(self) -> None:
        payload = json.dumps({"host": "0.0.0.0", "port": 9001})
        with patch("pathlib.Path.read_text", return_value=payload):
            config = VirtualDeviceConfig.load("device.json")

        self.assertEqual(config.host, "0.0.0.0")
        self.assertEqual(config.port, 9001)

    def test_load_rejects_invalid_json_and_non_object_root(self) -> None:
        with patch("pathlib.Path.read_text", return_value="{"):
            with self.assertRaisesRegex(ValueError, "cannot load configuration"):
                VirtualDeviceConfig.load("invalid.json")
        with patch("pathlib.Path.read_text", return_value="[]"):
            with self.assertRaisesRegex(ValueError, "root must be a JSON object"):
                VirtualDeviceConfig.load("array.json")


if __name__ == "__main__":
    unittest.main()
