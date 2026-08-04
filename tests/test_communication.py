import struct
import unittest

from robot_sim.communication import CommunicationService
from robot_sim.controller import RobotController
from robot_sim.models import RobotState
from robot_sim.protocol import Command, ProtocolFrame, encode_frame


class CommunicationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = RobotController()
        self.service = CommunicationService(self.controller, link_timeout_ms=300)

    def test_split_sensor_frame_updates_controller(self) -> None:
        payload = struct.pack("<HHhH", 245, 876, 253, 420)
        encoded = encode_frame(ProtocolFrame(Command.SENSOR_DATA, 1, payload))

        self.assertEqual(self.service.receive(encoded[:5], 10), 0)
        self.assertEqual(self.service.receive(encoded[5:], 20), 1)
        self.assertEqual(self.controller.sensors.distance_cm, 24.5)
        self.assertEqual(self.controller.sensors.battery_pct, 87.6)
        self.assertTrue(self.service.online)

    def test_sticky_heartbeat_and_control_are_both_handled(self) -> None:
        heartbeat = encode_frame(ProtocolFrame(Command.HEARTBEAT, 1))
        control = encode_frame(ProtocolFrame(Command.CONTROL, 2, b"\x02"))

        self.assertEqual(self.service.receive(heartbeat + control, 50), 2)
        self.assertEqual(self.controller.queue_size, 1)
        self.assertEqual(self.service.stats.parsed_frames, 2)

    def test_corrupt_frame_does_not_block_following_valid_frame(self) -> None:
        corrupt = bytearray(encode_frame(ProtocolFrame(Command.CONTROL, 3, b"\x03")))
        corrupt[-1] ^= 0xFF
        valid = encode_frame(ProtocolFrame(Command.CONTROL, 4, b"\x01"))

        self.assertEqual(self.service.receive(bytes(corrupt) + valid, 60), 1)
        self.assertEqual(self.controller.queue_size, 1)
        self.assertEqual(self.service.parser.stats.crc_errors, 1)

    def test_duplicate_control_is_not_executed_twice(self) -> None:
        frame = encode_frame(ProtocolFrame(Command.CONTROL, 9, b"\x02"))

        self.assertEqual(self.service.receive(frame + frame, 70), 1)
        self.assertEqual(self.controller.queue_size, 1)
        self.assertEqual(self.service.gateway.stats.duplicate_frames, 1)

    def test_invalid_payload_cannot_keep_link_online(self) -> None:
        heartbeat = encode_frame(ProtocolFrame(Command.HEARTBEAT, 1))
        invalid_sensor = encode_frame(
            ProtocolFrame(Command.SENSOR_DATA, 2, b"invalid")
        )
        self.service.receive(heartbeat, 0)
        self.assertEqual(self.service.receive(invalid_sensor, 250), 0)

        self.service.poll(300)
        self.assertFalse(self.service.online)
        self.assertFalse(self.controller.sensors.communication_ok)

    def test_duplicate_accepted_frame_still_proves_link_liveness(self) -> None:
        heartbeat = encode_frame(ProtocolFrame(Command.HEARTBEAT, 1))
        self.service.receive(heartbeat, 0)
        self.service.receive(heartbeat, 250)

        self.service.poll(300)
        self.assertTrue(self.service.online)
        self.assertTrue(self.controller.sensors.communication_ok)

    def test_silent_established_link_times_out_and_recovers(self) -> None:
        heartbeat = encode_frame(ProtocolFrame(Command.HEARTBEAT, 1))
        self.service.receive(heartbeat, 100)

        self.service.poll(399)
        self.assertTrue(self.service.online)
        self.service.poll(400)
        self.assertFalse(self.service.online)
        self.assertFalse(self.controller.sensors.communication_ok)
        self.assertEqual(self.service.stats.link_timeouts, 1)

        self.service.receive(encode_frame(ProtocolFrame(Command.HEARTBEAT, 2)), 450)
        self.assertTrue(self.service.online)
        self.assertTrue(self.controller.sensors.communication_ok)

    def test_repeated_offline_ticks_drive_controller_to_fault(self) -> None:
        heartbeat = encode_frame(ProtocolFrame(Command.HEARTBEAT, 1))
        self.service.receive(heartbeat, 0)
        self.service.poll(300)

        for _ in range(self.controller.COMM_TIMEOUT_LIMIT):
            self.controller.tick(0.1)
        self.assertEqual(self.controller.state, RobotState.FAULT)

    def test_invalid_configuration_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CommunicationService(self.controller, link_timeout_ms=0)


if __name__ == "__main__":
    unittest.main()
