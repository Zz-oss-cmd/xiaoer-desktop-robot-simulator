from __future__ import annotations

import argparse
import time

from robot_sim.controller import RobotController
from robot_sim.tcp_transport import RobotTcpServer


def main() -> None:
    parser = argparse.ArgumentParser(description="小二机器人TCP虚拟设备")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=8765, help="监听端口")
    args = parser.parse_args()

    controller = RobotController(
        lambda level, message: print(f"[{level}] {message}", flush=True)
    )
    with RobotTcpServer(controller, args.host, args.port) as server:
        host, port = server.address
        print(f"小二TCP虚拟设备已启动：{host}:{port}", flush=True)
        print("按 Ctrl+C 停止。", flush=True)
        try:
            while True:
                server.tick(0.1)
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n正在停止虚拟设备……", flush=True)


if __name__ == "__main__":
    main()
