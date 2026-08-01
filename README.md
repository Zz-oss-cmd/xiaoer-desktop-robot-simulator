# 小二 - 桌面陪伴机器人控制与仿真系统

一个完全不依赖实体硬件的桌面机器人软件项目。项目使用 Python 标准库和
Tkinter 实现机器人动画、行为状态机、优先级任务队列、虚拟传感器、二维运动、
故障注入、异常恢复和自动化测试。

![小二桌面机器人运行界面](assets/demo.png)

演示视频：[`demo_xiaoer_robot_60s.mp4`](demo_xiaoer_robot_60s.mp4)

## 功能

- 8 种状态：启动、待机、交互、执行任务、避障、低电量、休眠、故障
- 6 类任务：打招呼、巡逻、跳舞、休息、讲笑话、显示状态
- 带优先级的任务队列和紧急任务抢占
- 距离、电量、温度、光照、触摸、通信状态等虚拟输入
- 二维位置、方向、速度及边界碰撞仿真
- 障碍物检测、低电量保护、过温保护、通信超时和传感器失效处理
- 故障注入、系统恢复和可追溯运行日志
- 12 项控制器自动化测试

## 运行环境

- Windows 10/11
- Python 3.10 或更高版本
- Tkinter（Windows 官方 Python 通常自带）
- 不需要任何第三方 Python 包

## 启动

双击：

```text
run_robot.bat
```

或在项目目录执行：

```bash
python main.py
```

运行约1分钟自动演示：

```bash
python main.py --demo
```

## 测试

双击 `run_tests.bat`，或执行：

```bash
python -m unittest discover -s tests -v
```

## 操作方式

1. 点击“巡逻”观察机器人移动。
2. 将距离滑块调到 20 cm 以下，观察机器人进入避障状态。
3. 点击“通信断开”或“传感器失效”，连续检测后进入故障状态。
4. 点击“执行系统恢复”，清除异常并回到待机状态。
5. 在指令框输入“你好、巡逻、跳舞、休息、讲笑话、状态、唤醒、复位”。
6. 普通任务执行期间点击“紧急返回待机”，观察任务抢占。

## 项目结构

```text
desktop_robot_simulator/
├─ main.py
├─ run_robot.bat
├─ run_tests.bat
├─ requirements.txt
├─ README.md
├─ RESUME.md
├─ robot_sim/
│  ├─ __init__.py
│  ├─ models.py
│  ├─ controller.py
│  └─ ui.py
└─ tests/
   └─ test_controller.py
```

## 设计说明

控制器与 GUI 分离。`RobotController` 不依赖 Tkinter，因此状态机、任务队列、
故障检测和恢复逻辑可以独立测试。GUI 每 100 ms 调用一次 `tick()`，相当于
嵌入式系统中的周期任务。

状态机限制非法跳转；任务队列使用优先级堆实现；连续通信或传感器异常达到阈值
后进入故障状态；恢复动作统一清除异常计数并恢复安全参数。

## 后续扩展

- 使用 SQLite 保存历史运行记录
- 添加 TCP/UDP 虚拟设备通信
- 使用 JSON 配置任务和传感器阈值
- 增加语音识别或本地自然语言命令
- 使用 PyInstaller 打包为 Windows EXE
