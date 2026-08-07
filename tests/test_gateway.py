import struct
import unittest

from robot_sim.controller import RobotController
from robot_sim.gateway import ControlAction, ProtocolGateway, decode_status_frame
from robot_sim.models import Priority, RobotState, TaskType
from robot_sim.protocol import Command, ProtocolFrame, StreamParser


class GatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = RobotController()
        self.gateway = ProtocolGateway(self.controller)

    def test_heartbeat_restores_communication_flag(self) -> None:
        self.controller.update_sensor("communication_ok", False)
        self.assertTrue(self.gateway.handle(ProtocolFrame(Command.HEARTBEAT, 1)))
        self.assertTrue(self.controller.sensors.communication_ok)

    def test_sensor_payload_updates_four_values(self) -> None:
        payload = struct.pack("<HHhH", 199, 755, 283, 420)
        self.assertTrue(self.gateway.handle(ProtocolFrame(Command.SENSOR_DATA, 1, payload)))
        self.assertEqual(self.controller.sensors.distance_cm, 19.9)
        self.assertEqual(self.controller.sensors.battery_pct, 75.5)
        self.assertEqual(self.controller.sensors.temperature_c, 28.3)
        self.assertEqual(self.controller.sensors.light_pct, 42.0)

    def test_bad_sensor_length_is_rejected_without_mutation(self) -> None:
        before = self.controller.sensors.distance_cm
        self.assertFalse(self.gateway.handle(ProtocolFrame(Command.SENSOR_DATA, 1, b"short")))
        self.assertEqual(self.controller.sensors.distance_cm, before)

    def test_out_of_range_sensor_value_is_rejected(self) -> None:
        payload = struct.pack("<HHhH", 100, 1001, 300, 500)
        self.assertFalse(self.gateway.handle(ProtocolFrame(Command.SENSOR_DATA, 1, payload)))

    def test_control_frame_adds_priority_task(self) -> None:
        payload = bytes((ControlAction.PATROL, Priority.HIGH))
        self.assertTrue(self.gateway.handle(ProtocolFrame(Command.CONTROL, 1, payload)))
        self.controller.tick(0.1)
        self.assertEqual(self.controller.current_task.task_type, TaskType.PATROL)
        self.assertEqual(self.controller.current_task.priority, Priority.HIGH)

    def test_full_task_queue_rejects_control_and_allows_retry(self) -> None:
        controller = RobotController(max_queue_size=1)
        gateway = ProtocolGateway(controller)
        first = ProtocolFrame(Command.CONTROL, 1, bytes((ControlAction.GREET,)))
        retryable = ProtocolFrame(Command.CONTROL, 2, bytes((ControlAction.PATROL,)))

        self.assertTrue(gateway.handle(first))
        self.assertFalse(gateway.handle(retryable))
        self.assertEqual(controller.queue_size, 1)
        self.assertEqual(gateway.stats.queue_rejections, 1)
        self.assertEqual(gateway.stats.rejected_payloads, 1)

        controller.tick(0.1)
        self.assertTrue(gateway.handle(retryable))
        self.assertEqual(controller.queue_size, 1)

    def test_recover_action_clears_fault(self) -> None:
        self.controller.inject_fault("temperature")
        self.controller.tick(0.1)
        self.assertEqual(self.controller.state, RobotState.FAULT)
        payload = bytes((ControlAction.RECOVER,))
        self.assertTrue(self.gateway.handle(ProtocolFrame(Command.CONTROL, 1, payload)))
        self.assertEqual(self.controller.state, RobotState.IDLE)

    def test_duplicate_sequence_is_rejected(self) -> None:
        frame = ProtocolFrame(Command.CONTROL, 5, bytes((ControlAction.GREET,)))
        self.assertTrue(self.gateway.handle(frame))
        self.assertFalse(self.gateway.handle(frame))
        self.assertEqual(self.gateway.stats.duplicate_frames, 1)

    def test_status_frame_can_be_parsed(self) -> None:
        encoded = self.gateway.build_status_frame(9)
        frames = StreamParser().feed(encoded, 0)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].command, Command.DEVICE_STATUS)

        status = decode_status_frame(frames[0])
        self.assertEqual(status.state, self.controller.state)
        self.assertEqual(status.battery_pct, self.controller.sensors.battery_pct)
        state, battery, temperature, queue_size = struct.unpack("<BHhB", frames[0].payload)
        self.assertEqual(state, list(RobotState).index(RobotState.IDLE))
        self.assertEqual(battery, 850)
        self.assertEqual(temperature, 300)
        self.assertEqual(queue_size, 0)

    def test_invalid_status_frame_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            decode_status_frame(ProtocolFrame(Command.HEARTBEAT, 1))
        with self.assertRaises(ValueError):
            decode_status_frame(ProtocolFrame(Command.DEVICE_STATUS, 1, b"\x00"))
        bad_state = struct.pack("<BHhB", 255, 800, 250, 0)
        with self.assertRaises(ValueError):
            decode_status_frame(ProtocolFrame(Command.DEVICE_STATUS, 1, bad_state))


if __name__ == "__main__":
    unittest.main()
