from __future__ import annotations

import datetime as dt
import tkinter as tk
from tkinter import ttk

from .controller import RobotController
from .models import Priority, RobotState, TaskType


class RobotApp:
    TICK_MS = 100

    def __init__(self, demo: bool = False) -> None:
        self.root = tk.Tk()
        self.root.title("小二 - 桌面陪伴机器人控制与仿真系统")
        self.root.geometry("1120x720")
        self.root.minsize(980, 650)
        self.root.configure(bg="#0f172a")
        self._configure_style()

        self.controller = RobotController(self._append_log)
        self.command_var = tk.StringVar()
        self.response_var = tk.StringVar(value="你好，我是小二。")
        self.state_var = tk.StringVar()
        self.task_var = tk.StringVar()
        self.queue_var = tk.StringVar()

        self.distance_var = tk.DoubleVar(value=self.controller.sensors.distance_cm)
        self.battery_var = tk.DoubleVar(value=self.controller.sensors.battery_pct)
        self.temperature_var = tk.DoubleVar(value=self.controller.sensors.temperature_c)
        self.light_var = tk.DoubleVar(value=self.controller.sensors.light_pct)

        self._build_ui()
        self._render()
        self.root.after(self.TICK_MS, self._loop)
        if demo:
            self.root.after(1200, self._start_demo)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Panel.TFrame", background="#172033")
        style.configure(
            "Title.TLabel",
            background="#0f172a",
            foreground="#e2e8f0",
            font=("Microsoft YaHei UI", 18, "bold"),
        )
        style.configure(
            "PanelTitle.TLabel",
            background="#172033",
            foreground="#7dd3fc",
            font=("Microsoft YaHei UI", 11, "bold"),
        )
        style.configure(
            "Data.TLabel",
            background="#172033",
            foreground="#e2e8f0",
            font=("Microsoft YaHei UI", 10),
        )
        style.configure(
            "Accent.TButton",
            font=("Microsoft YaHei UI", 9, "bold"),
            background="#0ea5e9",
            foreground="white",
            padding=6,
        )
        style.configure(
            "Safe.TButton",
            font=("Microsoft YaHei UI", 9),
            background="#16a34a",
            foreground="white",
            padding=5,
        )
        style.configure(
            "Danger.TButton",
            font=("Microsoft YaHei UI", 9),
            background="#dc2626",
            foreground="white",
            padding=5,
        )

    def _build_ui(self) -> None:
        header = ttk.Frame(self.root, style="Panel.TFrame")
        header.pack(fill="x", padx=14, pady=(12, 8))
        ttk.Label(
            header,
            text="小二 · 桌面陪伴机器人控制与仿真系统",
            style="Title.TLabel",
        ).pack(side="left", padx=12, pady=10)
        ttk.Label(
            header,
            textvariable=self.response_var,
            style="Data.TLabel",
        ).pack(side="right", padx=16)

        body = ttk.Frame(self.root, style="Panel.TFrame")
        body.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body, style="Panel.TFrame")
        right = ttk.Frame(body, style="Panel.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)

        ttk.Label(left, text="机器人与运动仿真", style="PanelTitle.TLabel").pack(
            anchor="w", pady=(0, 6)
        )
        self.canvas = tk.Canvas(
            left, bg="#09111f", highlightthickness=1, highlightbackground="#334155"
        )
        self.canvas.pack(fill="both", expand=True)

        status = ttk.Frame(left, style="Panel.TFrame")
        status.pack(fill="x", pady=(8, 0))
        for variable in (self.state_var, self.task_var, self.queue_var):
            ttk.Label(status, textvariable=variable, style="Data.TLabel").pack(
                side="left", padx=(0, 22)
            )

        self._build_command_panel(right)
        self._build_sensor_panel(right)
        self._build_fault_panel(right)

        log_panel = ttk.Frame(self.root, style="Panel.TFrame")
        log_panel.pack(fill="x", padx=14, pady=(0, 12))
        ttk.Label(log_panel, text="运行日志", style="PanelTitle.TLabel").pack(
            anchor="w", padx=8, pady=(6, 2)
        )
        self.log_text = tk.Text(
            log_panel,
            height=8,
            bg="#09111f",
            fg="#cbd5e1",
            insertbackground="white",
            relief="flat",
            font=("Consolas", 9),
        )
        self.log_text.pack(fill="x", padx=8, pady=(0, 8))

    def _build_command_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Panel.TFrame")
        panel.pack(fill="x", pady=(0, 10))
        ttk.Label(panel, text="指令与任务", style="PanelTitle.TLabel").pack(anchor="w")
        row = ttk.Frame(panel, style="Panel.TFrame")
        row.pack(fill="x", pady=6)
        entry = ttk.Entry(row, textvariable=self.command_var)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda _event: self._send_command())
        ttk.Button(row, text="发送", style="Accent.TButton", command=self._send_command).pack(
            side="left", padx=(6, 0)
        )

        tasks = ttk.Frame(panel, style="Panel.TFrame")
        tasks.pack(fill="x")
        for i, task in enumerate(TaskType):
            ttk.Button(
                tasks,
                text=task.value,
                command=lambda t=task: self.controller.add_task(t),
            ).grid(row=i // 3, column=i % 3, sticky="ew", padx=2, pady=2)
        for col in range(3):
            tasks.columnconfigure(col, weight=1)
        ttk.Button(
            panel,
            text="紧急返回待机",
            style="Danger.TButton",
            command=lambda: self.controller.add_task(
                TaskType.REST, Priority.EMERGENCY, duration_s=1.0
            ),
        ).pack(fill="x", pady=(6, 0))

    def _build_sensor_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Panel.TFrame")
        panel.pack(fill="x", pady=(0, 10))
        ttk.Label(panel, text="虚拟传感器", style="PanelTitle.TLabel").pack(anchor="w")
        sensors = (
            ("距离 / cm", self.distance_var, 0, 200, "distance_cm"),
            ("电量 / %", self.battery_var, 0, 100, "battery_pct"),
            ("温度 / ℃", self.temperature_var, 20, 90, "temperature_c"),
            ("光照 / %", self.light_var, 0, 100, "light_pct"),
        )
        for label, variable, low, high, name in sensors:
            row = ttk.Frame(panel, style="Panel.TFrame")
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label, width=11, style="Data.TLabel").pack(side="left")
            scale = ttk.Scale(
                row,
                from_=low,
                to=high,
                variable=variable,
                command=lambda value, n=name: self.controller.update_sensor(n, float(value)),
            )
            scale.pack(side="left", fill="x", expand=True, padx=6)
            value_label = ttk.Label(row, textvariable=variable, width=6, style="Data.TLabel")
            value_label.pack(side="right")
        ttk.Button(
            panel,
            text="模拟触摸/唤醒",
            style="Safe.TButton",
            command=self._touch,
        ).pack(fill="x", pady=(6, 0))

    def _build_fault_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Panel.TFrame")
        panel.pack(fill="x")
        ttk.Label(panel, text="故障注入与恢复", style="PanelTitle.TLabel").pack(anchor="w")
        faults = ttk.Frame(panel, style="Panel.TFrame")
        faults.pack(fill="x", pady=6)
        items = (
            ("通信断开", "communication"),
            ("传感器失效", "sensor"),
            ("过温", "temperature"),
            ("低电量", "low_battery"),
        )
        for i, (label, fault) in enumerate(items):
            ttk.Button(
                faults,
                text=label,
                style="Danger.TButton",
                command=lambda f=fault: self._inject_fault(f),
            ).grid(row=i // 2, column=i % 2, sticky="ew", padx=2, pady=2)
        faults.columnconfigure(0, weight=1)
        faults.columnconfigure(1, weight=1)
        ttk.Button(
            panel,
            text="执行系统恢复",
            style="Safe.TButton",
            command=self._recover,
        ).pack(fill="x")

    def _send_command(self) -> None:
        result = self.controller.command(self.command_var.get())
        self.response_var.set(result)
        self.command_var.set("")

    def _touch(self) -> None:
        self.controller.sensors.touched = True
        self._append_log("SENSOR", "检测到虚拟触摸事件")

    def _inject_fault(self, fault: str) -> None:
        self.controller.inject_fault(fault)
        self._sync_sliders()

    def _recover(self) -> None:
        self.controller.recover()
        self._sync_sliders()

    def _demo_action(self, message: str, action) -> None:
        self.response_var.set("演示：" + message)
        self._append_log("DEMO", message)
        action()

    def _start_demo(self) -> None:
        """Schedule a repeatable one-minute demonstration for recording/interviews."""
        steps = [
            (0, "接收打招呼任务", lambda: self.controller.add_task(TaskType.GREET)),
            (4500, "开始巡逻，观察二维位置变化", lambda: self.controller.add_task(TaskType.PATROL)),
            (9500, "距离降至10cm，触发自动避障", lambda: self.distance_var.set(10.0)),
            (9600, "同步障碍物传感器", lambda: self.controller.update_sensor("distance_cm", 10.0)),
            (17000, "紧急休息任务抢占当前任务", lambda: self.controller.add_task(TaskType.REST, Priority.EMERGENCY, 2.5)),
            (23000, "注入通信断开故障", lambda: self.controller.inject_fault("communication")),
            (29000, "执行系统恢复", self._recover),
            (35000, "注入低电量保护场景", lambda: self.controller.inject_fault("low_battery")),
            (41000, "恢复电量并返回待机", self._recover),
            (47000, "执行跳舞任务", lambda: self.controller.add_task(TaskType.DANCE)),
            (54500, "演示结束：状态机、任务调度、故障恢复均已验证", lambda: None),
        ]
        for delay, message, action in steps:
            self.root.after(
                delay,
                lambda m=message, a=action: self._demo_action(m, a),
            )

    def _sync_sliders(self) -> None:
        sensors = self.controller.sensors
        self.distance_var.set(sensors.distance_cm)
        self.battery_var.set(sensors.battery_pct)
        self.temperature_var.set(sensors.temperature_c)
        self.light_var.set(sensors.light_pct)

    def _append_log(self, level: str, message: str) -> None:
        if not hasattr(self, "log_text"):
            return
        timestamp = dt.datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"{timestamp} [{level:<5}] {message}\n")
        self.log_text.see("end")

    def _loop(self) -> None:
        self.controller.tick(self.TICK_MS / 1000.0)
        self._sync_sliders()
        self._render()
        self.root.after(self.TICK_MS, self._loop)

    def _render(self) -> None:
        c = self.controller
        self.state_var.set(f"状态：{c.state.value}")
        current = c.current_task.task_type.value if c.current_task else "无"
        self.task_var.set(f"任务：{current}")
        self.queue_var.set(f"队列：{c.queue_size}")

        canvas = self.canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 540)
        height = max(canvas.winfo_height(), 330)
        canvas.create_text(
            14,
            12,
            anchor="nw",
            fill="#94a3b8",
            font=("Microsoft YaHei UI", 9),
            text="二维运动区域 · 调低距离传感器可触发避障",
        )
        for x in range(40, width, 40):
            canvas.create_line(x, 38, x, height, fill="#132238")
        for y in range(40, height, 40):
            canvas.create_line(0, y, width, y, fill="#132238")

        rx = min(width - 45, max(45, c.x / 520.0 * (width - 80) + 40))
        ry = min(height - 45, max(65, c.y / 320.0 * (height - 90) + 45))
        color = {
            RobotState.IDLE: "#38bdf8",
            RobotState.WORKING: "#22c55e",
            RobotState.AVOIDING: "#f59e0b",
            RobotState.LOW_POWER: "#f97316",
            RobotState.SLEEPING: "#818cf8",
            RobotState.FAULT: "#ef4444",
            RobotState.INTERACTING: "#d946ef",
            RobotState.BOOT: "#64748b",
        }[c.state]

        canvas.create_oval(rx - 34, ry - 30, rx + 34, ry + 30, fill=color, outline="#e2e8f0", width=2)
        eye_y = ry - 7
        if c.state == RobotState.SLEEPING:
            canvas.create_line(rx - 20, eye_y, rx - 7, eye_y, fill="#07111f", width=3)
            canvas.create_line(rx + 7, eye_y, rx + 20, eye_y, fill="#07111f", width=3)
        else:
            canvas.create_oval(rx - 20, eye_y - 5, rx - 10, eye_y + 5, fill="#07111f")
            canvas.create_oval(rx + 10, eye_y - 5, rx + 20, eye_y + 5, fill="#07111f")
        if c.state == RobotState.FAULT:
            canvas.create_line(rx - 14, ry + 14, rx + 14, ry + 14, fill="#07111f", width=3)
        else:
            canvas.create_arc(
                rx - 15,
                ry + 2,
                rx + 15,
                ry + 21,
                start=200,
                extent=140,
                style="arc",
                outline="#07111f",
                width=3,
            )

        canvas.create_text(
            rx,
            ry + 43,
            text=f"小二 · {c.state.value}",
            fill="#e2e8f0",
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        canvas.create_text(
            width - 12,
            12,
            anchor="ne",
            fill="#cbd5e1",
            font=("Consolas", 9),
            text=(
                f"X={c.x:5.1f}  Y={c.y:5.1f}  Heading={c.heading_deg:5.1f}°\n"
                f"Distance={c.sensors.distance_cm:5.1f}cm  Battery={c.sensors.battery_pct:4.1f}%"
            ),
        )

    def run(self) -> None:
        self.root.mainloop()
