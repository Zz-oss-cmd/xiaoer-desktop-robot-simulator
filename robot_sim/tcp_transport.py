from __future__ import annotations

import socket
import socketserver
import threading
import time
from dataclasses import dataclass

from .communication import CommunicationService
from .controller import RobotController


def monotonic_ms() -> int:
    return time.monotonic_ns() // 1_000_000


@dataclass(slots=True)
class TcpServerStats:
    accepted_connections: int = 0
    received_bytes: int = 0
    handled_frames: int = 0
    status_frames_sent: int = 0
    socket_errors: int = 0


class _RobotRequestHandler(socketserver.BaseRequestHandler):
    server: "RobotTcpServer"

    def setup(self) -> None:
        self.service = CommunicationService(
            self.server.controller,
            link_timeout_ms=self.server.link_timeout_ms,
        )
        self.request.settimeout(self.server.poll_interval_s)
        self.server._connection_opened()

    def handle(self) -> None:
        response_sequence = 0
        while not self.server.stopping:
            try:
                data = self.request.recv(self.server.receive_size)
            except socket.timeout:
                with self.server.controller_lock:
                    self.service.poll(monotonic_ms())
                continue
            except OSError:
                self.server._increment("socket_errors")
                break

            if not data:
                break
            self.server._increment("received_bytes", len(data))
            with self.server.controller_lock:
                handled = self.service.receive(data, monotonic_ms())
                responses = [
                    self.service.build_status((response_sequence + offset) & 0xFF)
                    for offset in range(handled)
                ]
            self.server._increment("handled_frames", handled)

            for response in responses:
                try:
                    self.request.sendall(response)
                except OSError:
                    self.server._increment("socket_errors")
                    return
                response_sequence = (response_sequence + 1) & 0xFF
                self.server._increment("status_frames_sent")

    def finish(self) -> None:
        self.server._connection_closed()


class RobotTcpServer(socketserver.ThreadingTCPServer):
    """Threaded localhost server that exposes the robot binary protocol over TCP."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        controller: RobotController | None = None,
        host: str = "127.0.0.1",
        port: int = 0,
        *,
        link_timeout_ms: int = 3_000,
        receive_size: int = 256,
        poll_interval_s: float = 0.05,
    ) -> None:
        if receive_size <= 0:
            raise ValueError("receive_size must be positive")
        if poll_interval_s <= 0:
            raise ValueError("poll_interval_s must be positive")
        self.controller = controller or RobotController()
        self.link_timeout_ms = link_timeout_ms
        self.receive_size = receive_size
        self.poll_interval_s = poll_interval_s
        self.stats = TcpServerStats()
        self._stats_lock = threading.Lock()
        self.controller_lock = threading.RLock()
        self._active_connections = 0
        self._thread: threading.Thread | None = None
        self.stopping = False
        self._closed = False
        super().__init__((host, port), _RobotRequestHandler)

    @property
    def address(self) -> tuple[str, int]:
        host, port = self.server_address
        return str(host), int(port)

    def start(self) -> tuple[str, int]:
        if self._closed:
            raise RuntimeError("server cannot be restarted after stop")
        if self._thread and self._thread.is_alive():
            return self.address
        self.stopping = False
        self._thread = threading.Thread(
            target=self.serve_forever,
            name="xiaoer-tcp-server",
            daemon=True,
        )
        self._thread.start()
        return self.address

    def stop(self) -> None:
        if self._closed:
            return
        self.stopping = True
        if self._thread and self._thread.is_alive():
            self.shutdown()
        self.server_close()
        if self._thread:
            self._thread.join(timeout=1.0)
        self._closed = True

    def _increment(self, field: str, amount: int = 1) -> None:
        with self._stats_lock:
            setattr(self.stats, field, getattr(self.stats, field) + amount)

    def _connection_opened(self) -> None:
        with self._stats_lock:
            self._active_connections += 1
            self.stats.accepted_connections += 1

    def _connection_closed(self) -> None:
        with self._stats_lock:
            self._active_connections = max(0, self._active_connections - 1)
            offline = self._active_connections == 0
        if offline:
            with self.controller_lock:
                self.controller.update_sensor("communication_ok", False)

    def tick(self, dt: float) -> None:
        """Advance the controller without racing network request handlers."""
        with self.controller_lock:
            self.controller.tick(dt)

    def __enter__(self) -> "RobotTcpServer":
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()
