from __future__ import annotations

import heapq
import math
from collections.abc import Callable

from .models import Priority, RobotState, RobotTask, SensorData, TaskType


EventCallback = Callable[[str, str], None]


class RobotController:
    """Deterministic robot controller independent from the GUI."""

    LOW_BATTERY = 15.0
    HIGH_TEMPERATURE = 70.0
    OBSTACLE_DISTANCE = 20.0
    COMM_TIMEOUT_LIMIT = 3
    SENSOR_TIMEOUT_LIMIT = 3
    IDLE_SLEEP_SECONDS = 30.0

    def __init__(self, on_event: EventCallback | None = None) -> None:
        self.state = RobotState.BOOT
        self.sensors = SensorData()
        self.x = 160.0
        self.y = 150.0
        self.heading_deg = 0.0
        self.speed = 0.0
        self.current_task: RobotTask | None = None
        self._queue: list[tuple[int, int, RobotTask]] = []
        self._sequence = 0
        self._comm_failures = 0
        self._sensor_failures = 0
        self._idle_seconds = 0.0
        self._avoid_seconds = 0.0
        self._on_event = on_event or (lambda _level, _message: None)
        self.transition(RobotState.IDLE, "系统初始化完成")

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    def log(self, level: str, message: str) -> None:
        self._on_event(level, message)

    def transition(self, new_state: RobotState, reason: str) -> bool:
        allowed = {
            RobotState.BOOT: {RobotState.IDLE, RobotState.FAULT},
            RobotState.IDLE: {
                RobotState.INTERACTING,
                RobotState.WORKING,
                RobotState.SLEEPING,
                RobotState.LOW_POWER,
                RobotState.FAULT,
            },
            RobotState.INTERACTING: {
                RobotState.IDLE,
                RobotState.WORKING,
                RobotState.LOW_POWER,
                RobotState.FAULT,
            },
            RobotState.WORKING: {
                RobotState.IDLE,
                RobotState.AVOIDING,
                RobotState.LOW_POWER,
                RobotState.FAULT,
            },
            RobotState.AVOIDING: {
                RobotState.WORKING,
                RobotState.IDLE,
                RobotState.LOW_POWER,
                RobotState.FAULT,
            },
            RobotState.LOW_POWER: {RobotState.IDLE, RobotState.FAULT},
            RobotState.SLEEPING: {RobotState.IDLE, RobotState.LOW_POWER, RobotState.FAULT},
            RobotState.FAULT: {RobotState.IDLE},
        }
        if new_state == self.state:
            return True
        if new_state not in allowed[self.state]:
            self.log("WARN", f"拒绝非法状态切换：{self.state.value} -> {new_state.value}")
            return False
        old = self.state
        self.state = new_state
        self.log("STATE", f"{old.value} -> {new_state.value}：{reason}")
        return True

    def add_task(
        self,
        task_type: TaskType,
        priority: Priority = Priority.NORMAL,
        duration_s: float | None = None,
    ) -> None:
        durations = {
            TaskType.GREET: 2.0,
            TaskType.PATROL: 7.0,
            TaskType.DANCE: 5.0,
            TaskType.REST: 4.0,
            TaskType.TELL_JOKE: 3.0,
            TaskType.SHOW_STATUS: 2.0,
        }
        task = RobotTask(task_type, priority, duration_s or durations[task_type])
        self._sequence += 1
        heapq.heappush(self._queue, (int(priority), self._sequence, task))
        self.log("TASK", f"任务入队：{task_type.value}，优先级 {priority.name}")

        if (
            self.current_task
            and priority < self.current_task.priority
            and self.state not in {RobotState.FAULT, RobotState.LOW_POWER}
        ):
            interrupted = self.current_task
            self.current_task = None
            self._sequence += 1
            heapq.heappush(
                self._queue, (int(interrupted.priority), self._sequence, interrupted)
            )
            self.log("TASK", f"高优先级任务抢占：暂停{interrupted.task_type.value}")

    def update_sensor(self, name: str, value: float | bool) -> None:
        if not hasattr(self.sensors, name):
            raise ValueError(f"未知传感器字段：{name}")
        setattr(self.sensors, name, value)
        self._idle_seconds = 0.0

    def command(self, text: str) -> str:
        text = text.strip().lower()
        commands = {
            "你好": TaskType.GREET,
            "打招呼": TaskType.GREET,
            "巡逻": TaskType.PATROL,
            "跳舞": TaskType.DANCE,
            "休息": TaskType.REST,
            "讲笑话": TaskType.TELL_JOKE,
            "状态": TaskType.SHOW_STATUS,
        }
        if text in {"唤醒", "醒来"} and self.state == RobotState.SLEEPING:
            self.transition(RobotState.IDLE, "收到唤醒指令")
            return "机器人已唤醒"
        if text == "复位":
            self.recover()
            return "已执行恢复流程"
        task = commands.get(text)
        if task is None:
            self.log("WARN", f"无法识别指令：{text or '<空>'}")
            return "无法识别，请输入：你好、巡逻、跳舞、休息、讲笑话、状态、唤醒或复位"
        self.add_task(task)
        return f"已接收任务：{task.value}"

    def inject_fault(self, fault: str) -> None:
        if fault == "communication":
            self.sensors.communication_ok = False
            self.log("FAULT", "已注入通信断开故障")
        elif fault == "sensor":
            self.sensors.sensor_ok = False
            self.log("FAULT", "已注入传感器失效故障")
        elif fault == "temperature":
            self.sensors.temperature_c = 85.0
            self.log("FAULT", "已注入过温故障")
        elif fault == "low_battery":
            self.sensors.battery_pct = 8.0
            self.log("FAULT", "已注入低电量故障")
        else:
            raise ValueError(f"未知故障类型：{fault}")

    def recover(self) -> None:
        self.sensors.communication_ok = True
        self.sensors.sensor_ok = True
        self.sensors.temperature_c = min(self.sensors.temperature_c, 35.0)
        self.sensors.battery_pct = max(self.sensors.battery_pct, 60.0)
        self._comm_failures = 0
        self._sensor_failures = 0
        self.current_task = None
        self.speed = 0.0
        if self.state == RobotState.FAULT:
            self.transition(RobotState.IDLE, "故障条件已清除，恢复完成")
        elif self.state == RobotState.LOW_POWER:
            self.transition(RobotState.IDLE, "电量恢复")
        else:
            self.log("INFO", "传感器和通信状态已复位")

    def tick(self, dt: float) -> None:
        self._monitor_health()
        if self.state == RobotState.FAULT:
            self.speed = 0.0
            return

        if self.state == RobotState.LOW_POWER:
            self.speed = 0.0
            if self.sensors.battery_pct > 30.0:
                self.transition(RobotState.IDLE, "电量已恢复")
            return

        if self.state == RobotState.SLEEPING:
            if self.sensors.touched:
                self.sensors.touched = False
                self.transition(RobotState.IDLE, "触摸唤醒")
            return

        if self.state == RobotState.AVOIDING:
            self._avoid_seconds += dt
            self.heading_deg = (self.heading_deg + 120.0 * dt) % 360.0
            self.speed = 24.0
            self._move(dt)
            if self._avoid_seconds >= 1.2:
                self._avoid_seconds = 0.0
                self.sensors.distance_cm = max(self.sensors.distance_cm, 45.0)
                next_state = RobotState.WORKING if self.current_task else RobotState.IDLE
                self.transition(next_state, "避障动作完成")
            return

        if self.sensors.distance_cm < self.OBSTACLE_DISTANCE and self.current_task:
            self.speed = 0.0
            self.transition(RobotState.AVOIDING, "检测到近距离障碍物")
            return

        if self.current_task is None and self._queue:
            _, _, self.current_task = heapq.heappop(self._queue)
            self.transition(RobotState.WORKING, f"开始{self.current_task.task_type.value}")

        if self.current_task:
            self._run_current_task(dt)
            self._idle_seconds = 0.0
        else:
            self.speed = 0.0
            if self.state != RobotState.IDLE:
                self.transition(RobotState.IDLE, "任务队列为空")
            self._idle_seconds += dt
            if self._idle_seconds >= self.IDLE_SLEEP_SECONDS:
                self.transition(RobotState.SLEEPING, "长时间无操作")

    def _monitor_health(self) -> None:
        self._comm_failures = 0 if self.sensors.communication_ok else self._comm_failures + 1
        self._sensor_failures = 0 if self.sensors.sensor_ok else self._sensor_failures + 1

        if self.sensors.temperature_c >= self.HIGH_TEMPERATURE:
            if self.state != RobotState.FAULT:
                self.transition(RobotState.FAULT, "温度超过安全阈值")
            return
        if self._comm_failures >= self.COMM_TIMEOUT_LIMIT:
            if self.state != RobotState.FAULT:
                self.transition(RobotState.FAULT, "通信连续超时")
            return
        if self._sensor_failures >= self.SENSOR_TIMEOUT_LIMIT:
            if self.state != RobotState.FAULT:
                self.transition(RobotState.FAULT, "传感器连续失效")
            return
        if (
            self.sensors.battery_pct <= self.LOW_BATTERY
            and self.state not in {RobotState.LOW_POWER, RobotState.FAULT}
        ):
            self.current_task = None
            self.transition(RobotState.LOW_POWER, "电量低于安全阈值")

    def _run_current_task(self, dt: float) -> None:
        assert self.current_task is not None
        task = self.current_task
        task.elapsed_s += dt

        if task.task_type == TaskType.PATROL:
            self.speed = 35.0
            self._move(dt)
            self.sensors.battery_pct = max(0.0, self.sensors.battery_pct - 0.05 * dt)
        elif task.task_type == TaskType.DANCE:
            self.speed = 0.0
            self.heading_deg = (self.heading_deg + 220.0 * dt) % 360.0
        elif task.task_type == TaskType.REST:
            self.speed = 0.0
            self.sensors.battery_pct = min(100.0, self.sensors.battery_pct + 1.5 * dt)
        else:
            self.speed = 0.0

        if task.complete:
            self.log("TASK", f"任务完成：{task.task_type.value}")
            self.current_task = None
            self.transition(RobotState.IDLE, "当前任务执行完成")

    def _move(self, dt: float) -> None:
        radians = math.radians(self.heading_deg)
        self.x += math.cos(radians) * self.speed * dt
        self.y += math.sin(radians) * self.speed * dt
        if self.x < 20 or self.x > 500:
            self.heading_deg = (180.0 - self.heading_deg) % 360.0
        if self.y < 20 or self.y > 300:
            self.heading_deg = (-self.heading_deg) % 360.0
        self.x = min(500.0, max(20.0, self.x))
        self.y = min(300.0, max(20.0, self.y))
