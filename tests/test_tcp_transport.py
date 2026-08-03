import socket
import struct
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from robot_sim.controller import RobotController
from robot_sim.protocol import Command, ProtocolFrame, StreamParser, encode_frame
from robot_sim.tcp_transport import RobotTcpServer


class TcpTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = RobotController()
        self.server = RobotTcpServer(self.controller, port=0, poll_interval_s=0.01)
        self.server.start()

    def tearDown(self) -> None:
        self.server.stop()

    def connect(self) -> socket.socket:
        connection = socket.create_connection(self.server.address, timeout=1.0)
        connection.settimeout(0.5)
        return connection

    def receive_frames(self, connection: socket.socket, count: int) -> list[ProtocolFrame]:
        parser = StreamParser()
        frames: list[ProtocolFrame] = []
        deadline = time.monotonic() + 1.0
        while len(frames) < count and time.monotonic() < deadline:
            frames.extend(parser.feed(connection.recv(512), int(time.monotonic() * 1000)))
        return frames

    def wait_until(self, predicate, timeout_s: float = 1.0) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.005)
        return False

    def test_heartbeat_receives_device_status(self) -> None:
        with self.connect() as connection:
            connection.sendall(encode_frame(ProtocolFrame(Command.HEARTBEAT, 1)))
            frames = self.receive_frames(connection, 1)

        self.assertEqual(len(frames), 1)
        self.assertIs(frames[0].command, Command.DEVICE_STATUS)
        self.assertEqual(self.server.stats.handled_frames, 1)

    def test_split_sensor_frame_crosses_real_socket(self) -> None:
        payload = struct.pack("<HHhH", 321, 755, 288, 640)
        encoded = encode_frame(ProtocolFrame(Command.SENSOR_DATA, 2, payload))
        with self.connect() as connection:
            connection.sendall(encoded[:4])
            time.sleep(0.02)
            connection.sendall(encoded[4:])
            self.assertEqual(len(self.receive_frames(connection, 1)), 1)

        self.assertEqual(self.controller.sensors.distance_cm, 32.1)
        self.assertEqual(self.controller.sensors.battery_pct, 75.5)

    def test_sticky_frames_produce_two_status_responses(self) -> None:
        first = encode_frame(ProtocolFrame(Command.HEARTBEAT, 3))
        second = encode_frame(ProtocolFrame(Command.CONTROL, 4, b"\x02"))
        with self.connect() as connection:
            connection.sendall(first + second)
            frames = self.receive_frames(connection, 2)

        self.assertEqual(len(frames), 2)
        self.assertEqual(self.controller.queue_size, 1)
        self.assertEqual(self.server.stats.status_frames_sent, 2)

    def test_corrupt_frame_recovers_to_following_frame(self) -> None:
        corrupt = bytearray(encode_frame(ProtocolFrame(Command.CONTROL, 5, b"\x03")))
        corrupt[-1] ^= 0xAA
        valid = encode_frame(ProtocolFrame(Command.CONTROL, 6, b"\x01"))
        with self.connect() as connection:
            connection.sendall(bytes(corrupt) + valid)
            self.assertEqual(len(self.receive_frames(connection, 1)), 1)

        self.assertEqual(self.controller.queue_size, 1)
        self.assertEqual(self.server.stats.handled_frames, 1)

    def test_disconnect_and_reconnect_update_link_state(self) -> None:
        first = self.connect()
        first.sendall(encode_frame(ProtocolFrame(Command.HEARTBEAT, 7)))
        self.receive_frames(first, 1)
        self.assertTrue(self.controller.sensors.communication_ok)
        first.close()
        self.assertTrue(self.wait_until(lambda: not self.controller.sensors.communication_ok))

        with self.connect() as second:
            second.sendall(encode_frame(ProtocolFrame(Command.HEARTBEAT, 8)))
            self.receive_frames(second, 1)
            self.assertTrue(self.controller.sensors.communication_ok)

        self.assertEqual(self.server.stats.accepted_connections, 2)

    def test_concurrent_clients_are_serialized_safely(self) -> None:
        def send_control(sequence: int) -> None:
            with self.connect() as connection:
                frame = encode_frame(
                    ProtocolFrame(Command.CONTROL, sequence, b"\x02")
                )
                connection.sendall(frame)
                self.assertEqual(len(self.receive_frames(connection, 1)), 1)

        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(send_control, range(10)))

        self.assertEqual(self.controller.queue_size, 10)
        self.assertEqual(self.server.stats.handled_frames, 10)

    def test_invalid_server_configuration_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RobotTcpServer(receive_size=0)
        with self.assertRaises(ValueError):
            RobotTcpServer(poll_interval_s=0)


if __name__ == "__main__":
    unittest.main()
