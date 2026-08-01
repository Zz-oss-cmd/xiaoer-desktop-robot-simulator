"""Software-only desktop companion robot simulator."""

from .controller import RobotController
from .models import RobotState, SensorData, TaskType

__all__ = ["RobotController", "RobotState", "SensorData", "TaskType"]
