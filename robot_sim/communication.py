from __future__ import annotations

from dataclasses import dataclass

from .controller import RobotController
from .gateway import ProtocolGateway
from .protocol import StreamParser


@dataclass(slots=True)
class CommunicationStats:
    receive_calls: int = 0
    parsed_frames: int = 0
    handled_frames: int = 0
    link_timeouts: int = 0


class CommunicationService:
    """Owns the receive path from DMA-like byte chunks to controller actions."""

    def __init__(
        self,
        controller: RobotController,
        *,
        link_timeout_ms: int = 3_000,
        parser: StreamParser | None = None,
    ) -> None:
        if link_timeout_ms <= 0:
            raise ValueError("link_timeout_ms must be positive")
        self.controller = controller
        self.parser = parser or StreamParser()
        self.gateway = ProtocolGateway(controller)
        self.link_timeout_ms = link_timeout_ms
        self.stats = CommunicationStats()
        self._last_valid_frame_ms: int | None = None
        self._link_timed_out = False

    @property
    def online(self) -> bool:
        return self._last_valid_frame_ms is not None and not self._link_timed_out

    def receive(self, data: bytes, now_ms: int) -> int:
        """Process one receive chunk and return the number of accepted frames."""
        self.stats.receive_calls += 1
        frames = self.parser.feed(data, now_ms)
        self.stats.parsed_frames += len(frames)
        duplicates_before = self.gateway.stats.duplicate_frames
        handled = sum(self.gateway.handle(frame) for frame in frames)
        duplicate_received = self.gateway.stats.duplicate_frames > duplicates_before

        # Only accepted requests (or a retransmitted accepted request) prove that
        # the peer is alive. A well-framed packet with an invalid payload must not
        # keep a broken or hostile link online.
        if handled or duplicate_received:
            self._last_valid_frame_ms = now_ms
            self._link_timed_out = False
            self.controller.update_sensor("communication_ok", True)

        self.stats.handled_frames += handled
        return handled

    def poll(self, now_ms: int) -> None:
        """Expire partial frames and mark an established link offline on silence."""
        self.parser.poll_timeout(now_ms)
        if self._last_valid_frame_ms is None or self._link_timed_out:
            return
        if now_ms - self._last_valid_frame_ms >= self.link_timeout_ms:
            self._link_timed_out = True
            self.stats.link_timeouts += 1
            self.controller.update_sensor("communication_ok", False)

    def build_status(self, sequence: int) -> bytes:
        return self.gateway.build_status_frame(sequence)
