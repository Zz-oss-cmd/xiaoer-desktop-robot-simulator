from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum, auto


class RobotState(Enum):
    BOOT = "启动"
    IDLE = "待机"
    INTERACTING = "交互"
    WORKING = "执行任务"
    AVOIDING = "避障"
    LOW_POWER = "低电量"
    SLEEPING = "休眠"
    FAULT = "故障"


class TaskType(Enum):
    GREET = "打招呼"
    PATROL = "巡逻"
    DANCE = "跳舞"
    REST = "休息"
    TELL_JOKE = "讲笑话"
    SHOW_STATUS = "显示状态"


class Priority(IntEnum):
    EMERGENCY = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass(slots=True)
class SensorData:
    distance_cm: float = 100.0
    battery_pct: float = 85.0
    temperature_c: float = 30.0
    light_pct: float = 60.0
    touched: bool = False
    communication_ok: bool = True
    sensor_ok: bool = True


@dataclass(slots=True)
class RobotTask:
    task_type: TaskType
    priority: Priority = Priority.NORMAL
    duration_s: float = 3.0
    elapsed_s: float = 0.0
    retries: int = 0
    max_retries: int = 1

    @property
    def complete(self) -> bool:
        return self.elapsed_s >= self.duration_s
