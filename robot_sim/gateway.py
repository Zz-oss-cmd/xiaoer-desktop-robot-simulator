from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum

from .controller import RobotController
from .models import Priority, RobotState, TaskType
from .protocol import Command, ProtocolFrame, encode_frame


class ControlAction(IntEnum):
    GREET = 1
    PATROL = 2
    DANCE = 3
    REST = 4
    TELL_JOKE = 5
    SHOW_STATUS = 6
    RECOVER = 7


ACTION_TO_TASK = {
    ControlAction.GREET: TaskType.GREET,
    ControlAction.PATROL: TaskType.PATROL,
    ControlAction.DANCE: TaskType.DANCE,
    ControlAction.REST: TaskType.REST,
    ControlAction.TELL_JOKE: TaskType.TELL_JOKE,
    ControlAction.SHOW_STATUS: TaskType.SHOW_STATUS,
}


@dataclass(slots=True)
class GatewayStats:
    handled_frames: int = 0
    rejected_payloads: int = 0
    duplicate_frames: int = 0
    queue_rejections: int = 0


@dataclass(frozen=True, slots=True)
class DeviceStatus:
    state: RobotState
    battery_pct: float
    temperature_c: float
    queue_size: int


def decode_status_frame(frame: ProtocolFrame) -> DeviceStatus:
    if frame.command is not Command.DEVICE_STATUS:
        raise ValueError("frame is not a device status response")
    expected_size = struct.calcsize(ProtocolGateway.STATUS_FORMAT)
    if len(frame.payload) != expected_size:
        raise ValueError("invalid device status payload length")
    state_code, battery, temperature, queue_size = struct.unpack(
        ProtocolGateway.STATUS_FORMAT, frame.payload
    )
    states = list(RobotState)
    if state_code >= len(states):
        raise ValueError("invalid robot state code")
    return DeviceStatus(states[state_code], battery / 10.0, temperature / 10.0, queue_size)


class ProtocolGateway:
    """Validates protocol payloads before changing controller state."""

    SENSOR_FORMAT = "<HHhH"
    SENSOR_PAYLOAD_SIZE = struct.calcsize(SENSOR_FORMAT)
    STATUS_FORMAT = "<BHhB"

    def __init__(self, controller: RobotController) -> None:
        self.controller = controller
        self.stats = GatewayStats()
        self._last_sequence: dict[Command, int] = {}

    def handle(self, frame: ProtocolFrame) -> bool:
        if self._last_sequence.get(frame.command) == frame.sequence:
            self.stats.duplicate_frames += 1
            return False

        handled = False
        if frame.command is Command.HEARTBEAT:
            handled = self._handle_heartbeat(frame.payload)
        elif frame.command is Command.SENSOR_DATA:
            handled = self._handle_sensor_data(frame.payload)
        elif frame.command is Command.CONTROL:
            handled = self._handle_control(frame.payload)

        if handled:
            self._last_sequence[frame.command] = frame.sequence
            self.stats.handled_frames += 1
        else:
            self.stats.rejected_payloads += 1
        return handled

    def build_status_frame(self, sequence: int) -> bytes:
        state_code = list(RobotState).index(self.controller.state)
        battery_tenths = round(self.controller.sensors.battery_pct * 10)
        temperature_tenths = round(self.controller.sensors.temperature_c * 10)
        queue_size = min(self.controller.queue_size, 0xFF)
        payload = struct.pack(
            self.STATUS_FORMAT,
            state_code,
            battery_tenths,
            temperature_tenths,
            queue_size,
        )
        return encode_frame(ProtocolFrame(Command.DEVICE_STATUS, sequence, payload))

    def _handle_heartbeat(self, payload: bytes) -> bool:
        if payload:
            return False
        self.controller.update_sensor("communication_ok", True)
        return True

    def _handle_sensor_data(self, payload: bytes) -> bool:
        if len(payload) != self.SENSOR_PAYLOAD_SIZE:
            return False
        distance, battery, temperature, light = struct.unpack(self.SENSOR_FORMAT, payload)
        if distance > 50_000 or battery > 1_000 or not -400 <= temperature <= 1_250 or light > 1_000:
            return False

        self.controller.update_sensor("distance_cm", distance / 10.0)
        self.controller.update_sensor("battery_pct", battery / 10.0)
        self.controller.update_sensor("temperature_c", temperature / 10.0)
        self.controller.update_sensor("light_pct", light / 10.0)
        self.controller.update_sensor("sensor_ok", True)
        return True

    def _handle_control(self, payload: bytes) -> bool:
        if len(payload) not in {1, 2}:
            return False
        try:
            action = ControlAction(payload[0])
            priority = Priority(payload[1]) if len(payload) == 2 else Priority.NORMAL
        except ValueError:
            return False

        if action is ControlAction.RECOVER:
            self.controller.recover()
            return True
        accepted = self.controller.add_task(ACTION_TO_TASK[action], priority)
        if not accepted:
            self.stats.queue_rejections += 1
        return accepted
