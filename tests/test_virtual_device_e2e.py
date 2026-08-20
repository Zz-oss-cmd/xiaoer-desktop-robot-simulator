import os
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path

from robot_sim.protocol import Command, ProtocolFrame, StreamParser, encode_frame


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class VirtualDeviceEndToEndTests(unittest.TestCase):
    def test_json_config_starts_reachable_protocol_server(self) -> None:
        port = self._reserve_local_port()
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(PROJECT_ROOT / "virtual_device.py"),
                "--config",
                str(PROJECT_ROOT / "config.example.json"),
                "--port",
                str(port),
            ],
            cwd=PROJECT_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        try:
            with self._connect_when_ready(process, port) as connection:
                connection.sendall(
                    encode_frame(ProtocolFrame(Command.HEARTBEAT, 1))
                )
                response = connection.recv(512)

            frames = StreamParser().feed(response, int(time.monotonic() * 1000))
            self.assertEqual(len(frames), 1)
            self.assertIs(frames[0].command, Command.DEVICE_STATUS)
        finally:
            process.terminate()
            try:
                process.communicate(timeout=3.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=3.0)

    def _connect_when_ready(
        self, process: subprocess.Popen[bytes], port: int
    ) -> socket.socket:
        deadline = time.monotonic() + 5.0
        last_error: OSError | None = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output = process.communicate()[0]
                self.fail(f"virtual device exited before startup: {output!r}")
            try:
                connection = socket.create_connection(
                    ("127.0.0.1", port), timeout=0.25
                )
                connection.settimeout(1.0)
                return connection
            except OSError as exc:
                last_error = exc
                time.sleep(0.05)
        self.fail(f"virtual device did not listen on port {port}: {last_error}")

    @staticmethod
    def _reserve_local_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            return int(probe.getsockname()[1])


if __name__ == "__main__":
    unittest.main()
