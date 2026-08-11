import unittest

from robot_sim.controller import RobotController
from robot_sim.models import Priority, RobotState, TaskType


class RobotControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events: list[tuple[str, str]] = []
        self.robot = RobotController(lambda level, msg: self.events.append((level, msg)))

    def tick(self, seconds: float, step: float = 0.1) -> None:
        for _ in range(round(seconds / step)):
            self.robot.tick(step)

    def test_boot_to_idle(self) -> None:
        self.assertEqual(self.robot.state, RobotState.IDLE)

    def test_task_runs_and_completes(self) -> None:
        self.robot.add_task(TaskType.GREET, duration_s=0.5)
        self.tick(0.1)
        self.assertEqual(self.robot.state, RobotState.WORKING)
        self.tick(0.5)
        self.assertEqual(self.robot.state, RobotState.IDLE)
        self.assertIsNone(self.robot.current_task)

    def test_priority_queue(self) -> None:
        self.robot.add_task(TaskType.PATROL, Priority.LOW)
        self.robot.add_task(TaskType.GREET, Priority.HIGH)
        self.tick(0.1)
        self.assertEqual(self.robot.current_task.task_type, TaskType.GREET)

    def test_task_queue_rejects_items_at_capacity(self) -> None:
        robot = RobotController(max_queue_size=2)
        self.assertTrue(robot.add_task(TaskType.GREET))
        self.assertTrue(robot.add_task(TaskType.PATROL))
        self.assertFalse(robot.add_task(TaskType.DANCE))
        self.assertEqual(robot.queue_size, 2)

    def test_invalid_queue_capacity_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RobotController(max_queue_size=0)

    def test_text_command_reports_full_task_queue(self) -> None:
        robot = RobotController(max_queue_size=1)
        self.assertEqual(robot.command("你好"), "已接收任务：打招呼")
        self.assertEqual(robot.command("巡逻"), "任务队列已满，请稍后重试")
        self.assertEqual(robot.queue_size, 1)

    def test_invalid_task_duration_is_rejected_without_queue_mutation(self) -> None:
        for duration in (0.0, -1.0, float("inf"), float("nan"), True):
            with self.subTest(duration=duration):
                with self.assertRaises(ValueError):
                    self.robot.add_task(TaskType.GREET, duration_s=duration)
                self.assertEqual(self.robot.queue_size, 0)

    def test_invalid_tick_delta_is_rejected_without_state_mutation(self) -> None:
        original_state = self.robot.state
        for dt in (0.0, -0.1, float("inf"), float("nan"), True):
            with self.subTest(dt=dt):
                with self.assertRaises(ValueError):
                    self.robot.tick(dt)
                self.assertEqual(self.robot.state, original_state)

    def test_emergency_task_preempts_current_task(self) -> None:
        self.robot.add_task(TaskType.PATROL, Priority.NORMAL)
        self.tick(0.1)
        self.robot.add_task(TaskType.REST, Priority.EMERGENCY)
        self.tick(0.1)
        self.assertEqual(self.robot.current_task.task_type, TaskType.REST)

    def test_obstacle_triggers_avoidance(self) -> None:
        self.robot.add_task(TaskType.PATROL)
        self.tick(0.1)
        self.robot.update_sensor("distance_cm", 10.0)
        self.tick(0.1)
        self.assertEqual(self.robot.state, RobotState.AVOIDING)
        self.tick(1.3)
        self.assertEqual(self.robot.state, RobotState.WORKING)

    def test_low_battery_safe_state(self) -> None:
        self.robot.update_sensor("battery_pct", 10.0)
        self.tick(0.1)
        self.assertEqual(self.robot.state, RobotState.LOW_POWER)
        self.assertEqual(self.robot.speed, 0.0)

    def test_communication_timeout_causes_fault(self) -> None:
        self.robot.update_sensor("communication_ok", False)
        self.tick(0.3)
        self.assertEqual(self.robot.state, RobotState.FAULT)

    def test_sensor_timeout_causes_fault(self) -> None:
        self.robot.update_sensor("sensor_ok", False)
        self.tick(0.3)
        self.assertEqual(self.robot.state, RobotState.FAULT)

    def test_overtemperature_causes_fault(self) -> None:
        self.robot.update_sensor("temperature_c", 75.0)
        self.tick(0.1)
        self.assertEqual(self.robot.state, RobotState.FAULT)

    def test_recover_from_fault(self) -> None:
        self.robot.inject_fault("temperature")
        self.tick(0.1)
        self.robot.recover()
        self.assertEqual(self.robot.state, RobotState.IDLE)
        self.assertLess(self.robot.sensors.temperature_c, 70.0)

    def test_illegal_transition_is_rejected(self) -> None:
        result = self.robot.transition(RobotState.AVOIDING, "测试非法跳转")
        self.assertFalse(result)
        self.assertEqual(self.robot.state, RobotState.IDLE)

    def test_sleep_and_touch_wakeup(self) -> None:
        self.robot.IDLE_SLEEP_SECONDS = 0.2
        self.tick(0.3)
        self.assertEqual(self.robot.state, RobotState.SLEEPING)
        self.robot.sensors.touched = True
        self.tick(0.1)
        self.assertEqual(self.robot.state, RobotState.IDLE)


if __name__ == "__main__":
    unittest.main()
