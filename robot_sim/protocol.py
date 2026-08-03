from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


HEADER = b"\xAA\x55"
VERSION = 0x01
MAX_PAYLOAD = 128
MAX_BUFFER = 512
PARTIAL_FRAME_TIMEOUT_MS = 100


class Command(IntEnum):
    HEARTBEAT = 0x01
    SENSOR_DATA = 0x10
    CONTROL = 0x20
    DEVICE_STATUS = 0x30


@dataclass(frozen=True, slots=True)
class ProtocolFrame:
    command: Command
    sequence: int
    payload: bytes = b""


@dataclass(slots=True)
class ProtocolStats:
    received_bytes: int = 0
    valid_frames: int = 0
    crc_errors: int = 0
    length_errors: int = 0
    version_errors: int = 0
    unknown_commands: int = 0
    discarded_noise_bytes: int = 0
    buffer_overflows: int = 0
    partial_timeouts: int = 0


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def encode_frame(frame: ProtocolFrame) -> bytes:
    payload = bytes(frame.payload)
    if len(payload) > MAX_PAYLOAD:
        raise ValueError(f"payload exceeds {MAX_PAYLOAD} bytes")
    if not 0 <= frame.sequence <= 0xFF:
        raise ValueError("sequence must be in range 0..255")

    body = bytes((VERSION, int(frame.command), frame.sequence))
    body += len(payload).to_bytes(2, "little") + payload
    crc = crc16_modbus(body)
    return HEADER + body + crc.to_bytes(2, "little")


class StreamParser:
    """Incremental framed-protocol parser for DMA-like byte chunks."""

    FIXED_PREFIX_SIZE = 7

    def __init__(self, max_buffer: int = MAX_BUFFER) -> None:
        if max_buffer < self.FIXED_PREFIX_SIZE:
            raise ValueError("max_buffer is too small")
        self.max_buffer = max_buffer
        self.stats = ProtocolStats()
        self._buffer = bytearray()
        self._partial_started_ms: int | None = None

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)

    def reset(self) -> None:
        self._buffer.clear()
        self._partial_started_ms = None

    def feed(self, data: bytes, now_ms: int) -> list[ProtocolFrame]:
        if now_ms < 0:
            raise ValueError("now_ms must be non-negative")
        if not data:
            return []

        was_empty = not self._buffer
        self.stats.received_bytes += len(data)
        self._buffer.extend(data)
        if was_empty:
            self._partial_started_ms = now_ms

        if len(self._buffer) > self.max_buffer:
            excess = len(self._buffer) - self.max_buffer
            del self._buffer[:excess]
            self.stats.buffer_overflows += 1
            self.stats.discarded_noise_bytes += excess

        frames = self._parse_available()
        if not self._buffer:
            self._partial_started_ms = None
        return frames

    def poll_timeout(self, now_ms: int) -> bool:
        if now_ms < 0:
            raise ValueError("now_ms must be non-negative")
        if self._partial_started_ms is None or not self._buffer:
            return False
        if now_ms - self._partial_started_ms < PARTIAL_FRAME_TIMEOUT_MS:
            return False

        self.stats.discarded_noise_bytes += len(self._buffer)
        self.stats.partial_timeouts += 1
        self.reset()
        return True

    def _parse_available(self) -> list[ProtocolFrame]:
        frames: list[ProtocolFrame] = []
        while True:
            header_index = self._buffer.find(HEADER)
            if header_index < 0:
                keep = 1 if self._buffer.endswith(HEADER[:1]) else 0
                discarded = len(self._buffer) - keep
                if discarded:
                    del self._buffer[:discarded]
                    self.stats.discarded_noise_bytes += discarded
                break

            if header_index:
                del self._buffer[:header_index]
                self.stats.discarded_noise_bytes += header_index

            if len(self._buffer) < self.FIXED_PREFIX_SIZE:
                break

            version = self._buffer[2]
            command_value = self._buffer[3]
            sequence = self._buffer[4]
            payload_length = int.from_bytes(self._buffer[5:7], "little")

            if payload_length > MAX_PAYLOAD:
                self.stats.length_errors += 1
                del self._buffer[0]
                continue

            frame_size = self.FIXED_PREFIX_SIZE + payload_length + 2
            if len(self._buffer) < frame_size:
                break

            body = bytes(self._buffer[2 : frame_size - 2])
            expected_crc = int.from_bytes(self._buffer[frame_size - 2 : frame_size], "little")
            if crc16_modbus(body) != expected_crc:
                self.stats.crc_errors += 1
                del self._buffer[0]
                continue

            payload = bytes(self._buffer[7 : frame_size - 2])
            del self._buffer[:frame_size]

            if version != VERSION:
                self.stats.version_errors += 1
                continue
            try:
                command = Command(command_value)
            except ValueError:
                self.stats.unknown_commands += 1
                continue

            frames.append(ProtocolFrame(command, sequence, payload))
            self.stats.valid_frames += 1
        return frames
