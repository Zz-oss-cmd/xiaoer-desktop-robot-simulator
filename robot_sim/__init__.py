"""Software-only desktop companion robot simulator."""

from .communication import CommunicationService
from .controller import RobotController
from .gateway import ControlAction, DeviceStatus, ProtocolGateway, decode_status_frame
from .models import RobotState, SensorData, TaskType
from .protocol import Command, ProtocolFrame, StreamParser, crc16_modbus, encode_frame
from .tcp_transport import RobotTcpServer

__all__ = [
    "Command",
    "CommunicationService",
    "ControlAction",
    "DeviceStatus",
    "ProtocolFrame",
    "ProtocolGateway",
    "RobotController",
    "RobotState",
    "RobotTcpServer",
    "SensorData",
    "StreamParser",
    "TaskType",
    "crc16_modbus",
    "decode_status_frame",
    "encode_frame",
]
